from logging import getLogger
from typing import Optional, List

from adaptix import P
from adaptix.conversion import impl_converter, link

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    is_supported, get_hw, get_breed,
)
from annet.adapters.netbox.common.query import NetboxQuery
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage
from . import api_models
from .client import NetboxV37

logger = getLogger(__name__)


@impl_converter(recipe=[
    link(P[api_models.Device].name, P[models.NetboxDevice].hostname),
    link(P[api_models.Device].name, P[models.NetboxDevice].fqdn),
])
def extend_device_base(
        device: api_models.Device,
        interfaces: List[models.Interface],
        hw: Optional[HardwareView],
        breed: str,
        neighbours_ids: List[int],
) -> models.NetboxDevice:
    ...


def extend_device(
        device: api_models.Device,
) -> models.NetboxDevice:
    return extend_device_base(
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
        neighbours_ids=[],
    )


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

    def resolve_object_ids_by_query(self, query: NetboxQuery):
        return [
            d.id for d in self._load_devices(query)
        ]

    def resolve_fdnds_by_query(self, query: NetboxQuery):
        return [
            d.name for d in self._load_devices(query)
        ]

    def make_devices(
            self,
            query: NetboxQuery,
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> List[models.NetboxDevice]:
        device_ids = {
            device.id: extend_device(device=device)
            for device in self._load_devices(query)
        }
        if not device_ids:
            return []

        interfaces = self._load_interfaces(list(device_ids))
        for interface in interfaces:
            device_ids[interface.device.id].interfaces.append(interface)
        return list(device_ids.values())

    def _load_devices(self, query: NetboxQuery) -> List[api_models.Device]:
        return [
            device
            for device in self.netbox.all_devices(
                name__ic=query.globs,
            ).results
            if _match_query(query, device)
            if is_supported(device.device_type.manufacturer.name)
        ]

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
        res = extend_device(device=device)
        res.interfaces = self._load_interfaces([device.id])
        return res

    def flush_perf(self):
        pass


def _match_query(query: NetboxQuery, device_data: api_models.Device) -> bool:
    for subquery in query.globs:
        if subquery.strip() in device_data.name:
            return True
    return False
