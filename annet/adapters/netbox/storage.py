import operator
import os
from typing import Optional

import urllib3
from requests import Session

from annet.storage import Storage
from .client import Netbox
from .models import Device


class NetboxStorageOpts:
    def __init__(self, url: str):
        self.url = url

    @classmethod
    def from_cli_opts(cls, cli_opts):
        return cls(
            url=os.getenv("NETBOX_URL", "http://localhost").rstrip("/"),
        )


class NetboxStorage(Storage):
    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        session = Session()
        session.verify = False
        urllib3.disable_warnings()
        self.netbox = Netbox(
            f"{opts.url}/api/",
            session,
        )

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        pass

    def resolve_object_ids_by_query(self, query):
        return []

    def resolve_fdnds_by_query(self, query):
        return []

    def make_devices(
            self,
            query,
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ):
        # TODO pass query to netbox
        all_requested = False
        device_ids = {
            device.id: device
            for device in self.netbox.all_devices().results
            if _match_query(query, device)
        }
        if device_ids:
            if all_requested:
                interfaces = self.netbox.all_interfaces()
            else:
                interfaces = self.netbox.all_interfaces(
                    device_id=list(device_ids))
            for iface in interfaces.results:
                device_ids[iface.device.id].interfaces.append(iface)
        else:
            interfaces = []

        interface_ids = {i.id: i for i in interfaces.results}
        if interface_ids:
            if all_requested:
                ips = self.netbox.all_ip_addresses()
            else:
                ips = self.netbox.all_ip_addresses(
                    interface_id=list(interface_ids))
            for ip in ips.results:
                interface_ids[ip.assigned_object_id].ip_addreses.append(ip)
        return list(device_ids.values())

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> Device:
        device = self.netbox.get_device(obj_id)
        interfaces = self.netbox.all_interfaces(device_id=[obj_id])
        interface_ids = {i.id: i for i in interfaces.results}
        if interface_ids:
            ips = self.netbox.all_ip_addresses(
                interface_id=list(interface_ids))
            for ip in ips.results:
                interface_ids[ip.assigned_object_id].ip_addreses.append(ip)
        return device

    def flush_perf(self):
        pass


def _match_query(query, device_data) -> bool:
    for subquery in query.globs:
        matches = []
        for field_filter in subquery.split("@"):
            if "=" in field_filter:
                field, value = field_filter.split("=")
                field = field.strip()
                value = value.strip()
                op = operator.eq
            else:
                field = "name"
                value = field_filter.strip()
                op = operator.contains
            if op(getattr(device_data, field, None), value):
                matches.append(True)
            else:
                matches.append(False)
        if all(matches):
            return True
    return False
