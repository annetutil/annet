from logging import getLogger
from typing import Optional, List

from adaptix import P
from adaptix.conversion import impl_converter, link

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    is_supported, get_hw, get_breed,
)
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.adapters.netbox.query import NetboxQuery
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage
from . import api_models
from .client import NetboxV37

logger = getLogger(__name__)


@impl_converter(recipe=[
    link(P[api_models.Device].name, P[models.NetboxDevice].hostname),
    link(P[api_models.Device].name, P[models.NetboxDevice].fqdn),
])
def extend_device(
        device: api_models.Device,
        interfaces: List[models.Interface],
        hw: Optional[HardwareView],
        breed: str,
) -> models.NetboxDevice:
    ...


@impl_converter
def extend_interface(
        interface: api_models.Interface, ip_addresses: List[models.IpAddress],
) -> models.Interface:
    ...


class NetboxStorageV37(Storage):
    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        self.netbox = NetboxV37(
            url=opts.url,
            token=opts.token,
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
    ) -> List[models.NetboxDevice]:
        device_ids = {
            device.id: extend_device(
                device=device,
                interfaces=[],
                breed=get_breed(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                ),
                hw=get_hw(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                ),
            )
            for device in self.netbox.all_devices(
                name__ic=query.globs,
            ).results
            if is_supported(device.device_type.manufacturer.name)
            if _match_query(query, device)
        }
        if device_ids:
            interfaces = self._load_interfaces(list(device_ids))
            for interface in interfaces:
                device_ids[interface.device.id].interfaces.append(interface)
        return list(device_ids.values())

    def _load_interfaces(self, device_ids: List[int]) -> List[
        models.Interface]:
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
    ) -> models.NetboxDevice:
        device = self.netbox.get_device(obj_id)
        return extend_device(
            device=device,
            interfaces=self._load_interfaces([device.id]),
            breed=get_breed(
                device.device_type.manufacturer.name,
                device.device_type.model,
            ),
            hw=get_hw(
                device.device_type.manufacturer.name,
                device.device_type.model,
            ),
        )

    def flush_perf(self):
        pass


def _match_query(query: NetboxQuery, device_data: api_models.Device) -> bool:
    for subquery in query.globs:
        if subquery.strip() in device_data.name:
            return True
    return False
