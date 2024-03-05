import operator
import os
from typing import Optional, List

import urllib3
from adaptix.conversion import impl_converter
from requests import Session

from annet.adapters.netbox.common_models import IpAddress
from annet.adapters.netbox.models import (
    Device as DeviceExt,
    Interface as InterfaceExt,
)
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage
from .client import Netbox
from .models import Device, Interface


class NetboxStorageOpts:
    def __init__(self, url: str):
        self.url = url

    @classmethod
    def from_cli_opts(cls, cli_opts):
        return cls(
            url=os.getenv("NETBOX_URL", "http://localhost").rstrip("/"),
        )


@impl_converter
def extend_device(
        device: Device, interfaces: List[InterfaceExt],
        fqdn: str, hostname: str, hw: Optional[HardwareView], breed: str,
) -> DeviceExt:
    ...


@impl_converter
def extend_interface(
        interface: Interface, ip_addresses: List[IpAddress],
) -> InterfaceExt:
    ...


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
    ) -> list[DeviceExt]:
        # TODO pass query to netbox
        device_ids = {
            device.id: extend_device(
                device=device,
                interfaces=[],
                breed=get_breed(device),
                hostname=device.name,
                hw=get_hw(device),
                fqdn=device.name,
            )
            for device in self.netbox.all_devices().results
            if _match_query(query, device)
        }
        if device_ids:
            interfaces = self._load_interfaces(list(device_ids))
            for interface in interfaces:
                device_ids[interface.device.id].interfaces.append(interface)
        return list(device_ids.values())

    def _load_interfaces(self, device_ids: List[int]) -> List[InterfaceExt]:
        interfaces = self.netbox.all_interfaces(device_id=device_ids)
        extended_ifaces = {
            interface.id: extend_interface(interface, [])
            for interface in interfaces.results
        }

        ips = self.netbox.all_ip_addresses(interface_id=list(extended_ifaces))
        for ip in ips.results:
            extended_ifaces[ip.assigned_object_id].ip_addresses.append(ip)
        return list(extended_ifaces.values())

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> DeviceExt:
        device = self.netbox.get_device(obj_id)
        return extend_device(
            device=device,
            interfaces=self._load_interfaces([device.id]),
            breed=get_breed(device),
            hostname=device.name,
            hw=get_hw(device),
            fqdn=device.name,
        )

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


def get_hw(device: Device):
    manufacturer = device.device_type.manufacturer.name
    model_name = device.device_type.model
    # by some reason Netbox calls Mellanox SN as MSN, so we fix them here
    if manufacturer == "Mellanox" and model_name.startswith("MSN"):
        model_name = model_name.replace("MSN", "SN", 1)
    hw = _vendor_to_hw(manufacturer + " " + model_name)
    if not hw:
        raise ValueError(f"unsupported manufacturer {manufacturer}")
    return hw


def get_breed(device: Device):
    manufacturer = device.device_type.manufacturer.name
    model_name = device.device_type.model
    if manufacturer == "Huawei" and model_name.startswith("CE"):
        return "vrp85"
    elif manufacturer == "Huawei" and model_name.startswith("NE"):
        return "vrp85"
    elif manufacturer == "Huawei":
        return "vrp55"
    elif manufacturer == "Mellanox":
        return "cuml2"
    elif manufacturer == "Juniper":
        return "jun10"
    elif manufacturer == "Cisco":
        return "ios12"
    elif manufacturer == "Adva":
        return "adva8"
    elif manufacturer == "Arista":
        return "eos4"
    raise ValueError(f"unsupported manufacturer {manufacturer}")


def _vendor_to_hw(vendor):
    hw = HardwareView(
        {
            "cisco": "Cisco",
            "catalyst": "Cisco Catalyst",
            "nexus": "Cisco Nexus",
            "huawei": "Huawei",
            "juniper": "Juniper",
            "arista": "Arista",
            "pc": "PC",
            "nokia": "Nokia",
            "aruba": "Aruba",
            "routeros": "RouterOS",
            "ribbon": "Ribbon",
        }.get(vendor.lower(), vendor),
        None,
    )
    return hw
