from logging import getLogger
from typing import Optional, List

from adaptix import P
from adaptix.conversion import impl_converter, link

from annet.adapters.netbox import models
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.adapters.netbox.common_models import IpAddress
from annet.adapters.netbox.query import NetboxQuery
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage
from . import api_models
from .client import NetboxV37

logger = getLogger(__name__)


@impl_converter(recipe=[
    link(P[api_models.Device].name, P[models.Device].hostname),
    link(P[api_models.Device].name, P[models.Device].fqdn),
])
def extend_device(
        device: api_models.Device,
        interfaces: List[models.Interface],
        hw: Optional[HardwareView],
        breed: str,
) -> models.Device:
    ...


@impl_converter
def extend_interface(
        interface: api_models.Interface, ip_addresses: List[IpAddress],
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
    ) -> List[models.Device]:
        device_ids = {
            device.id: extend_device(
                device=device,
                interfaces=[],
                breed=get_breed(device),
                hw=get_hw(device),
            )
            for device in self.netbox.all_devices(
                name__ic=query.globs,
            ).results
            if is_supported(device) and _match_query(query, device)
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
    ) -> models.Device:
        device = self.netbox.get_device(obj_id)
        return extend_device(
            device=device,
            interfaces=self._load_interfaces([device.id]),
            breed=get_breed(device),
            hw=get_hw(device),
        )

    def flush_perf(self):
        pass


def _match_query(query: NetboxQuery, device_data: api_models.Device) -> bool:
    for subquery in query.globs:
        if subquery.strip() in device_data.name:
            return True
    return False


def get_hw(device: api_models.Device):
    manufacturer = device.device_type.manufacturer.name
    model_name = device.device_type.model
    # by some reason Netbox calls Mellanox SN as MSN, so we fix them here
    if manufacturer == "Mellanox" and model_name.startswith("MSN"):
        model_name = model_name.replace("MSN", "SN", 1)
    hw = _vendor_to_hw(manufacturer + " " + model_name)
    if not hw:
        raise ValueError(f"unsupported manufacturer {manufacturer}")
    return hw


def get_breed(device: api_models.Device):
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


def is_supported(device: api_models.Device) -> bool:
    manufacturer = device.device_type.manufacturer.name
    if manufacturer not in (
            "Huawei", "Mellanox", "Juniper", "Cisco", "Adva", "Arista",
    ):
        logger.warning("Unsupported manufacturer `%s`", manufacturer)
        return False
    return True


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
