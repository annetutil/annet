from logging import getLogger
from typing import Optional, List

from annet.adapters.netbox import models, common_models
from annet.adapters.netbox.query import NetboxQuery
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage
from . import api_models
from .client import NetboxV24
from ..common.storage_opts import NetboxStorageOpts

logger = getLogger(__name__)


def extend_device_ip(
        ip: Optional[api_models.DeviceIp],
) -> Optional[models.DeviceIp]:
    if not ip:
        return None
    return models.DeviceIp(
        address=ip.address,
        id=ip.id,
        display=ip.address,
        family=ip.family,
    )


def extend_label(
        label: Optional[api_models.Label],
) -> Optional[models.Label]:
    if not label:
        return None
    return models.Label(
        label=label.label,
        value=str(label.value),
    )


def extend_device(device: api_models.Device) -> models.Device:
    return models.Device(
        id=device.id,
        name=device.name,
        display=device.display_name,
        device_type=device.device_type,
        device_role=device.device_role,
        tenant=device.tenant,
        platform=device.platform,
        serial=device.serial,
        asset_tag=device.asset_tag,
        site=device.site,
        rack=device.rack,
        position=device.position,
        face=extend_label(device.face),
        status=device.status,
        primary_ip=extend_device_ip(device.primary_ip),
        primary_ip4=extend_device_ip(device.primary_ip4),
        primary_ip6=extend_device_ip(device.primary_ip6),
        tags=[models.Entity(0, tag) for tag in device.tags],
        custom_fields=device.custom_fields,  # ???
        created=device.created,
        last_updated=device.last_updated,

        fqdn=device.name,
        hostname=device.name,
        hw=get_hw(device),
        breed=get_breed(device),
        interfaces=[],
    )


def extend_interface(interface: api_models.Interface) -> models.Interface:
    return models.Interface(
        id=interface.id,
        name=interface.name,
        device=interface.device,
        enabled=interface.enabled,
        display=interface.name,
        ip_addresses=[],
    )


def extend_ip(ip: api_models.IpAddress) -> models.IpAddress:
    return models.IpAddress(
        id=ip.id,
        assigned_object_id=ip.interface.id,
        display=ip.address,
        family=common_models.IpFamily(
            value=ip.family,
            label=str(ip.family),
        ),
        address=ip.address,
        status=extend_label(ip.status),
        tags=[models.Entity(0, tag) for tag in ip.tags],
        created=ip.created,
        last_updated=ip.last_updated,
    )


class NetboxStorageV24(Storage):
    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        self.netbox = NetboxV24(
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
    ) -> list[models.Device]:
        device_ids = {
            device.id: extend_device(device)
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
            interface.id: extend_interface(interface)
            for interface in interfaces.results
        }

        ips = self.netbox.all_ip_addresses(interface_id=list(extended_ifaces))
        for ip in ips.results:
            extended_ip = extend_ip(ip)
            interface = extended_ifaces[extended_ip.assigned_object_id]
            interface.ip_addresses.append(extended_ip)
        return list(extended_ifaces.values())

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> models.Device:
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
