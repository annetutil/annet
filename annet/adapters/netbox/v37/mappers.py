from typing import Optional

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    get_hw, get_breed,
)
from annet.storage import Storage
from annet_netbox.models import (
    DeviceWithConfigContext, Interface, IPAddress,
    DeviceWithConfigContextFaceType0, NestedIPAddress, IPAddressStatus,
)


def extend_device_ip(
        ip: Optional[NestedIPAddress],
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
        label: DeviceWithConfigContextFaceType0 | IPAddressStatus,
) -> Optional[models.Label]:
    if not label:
        return None
    return models.Label(
        label=label.label,
        value=str(label.value),
    )


def extend_device(
        device: DeviceWithConfigContext, storage: Storage,
) -> models.NetboxDevice:
    return models.NetboxDevice(
        url=device.url,
        id=device.id,
        name=device.name,
        hostname=device.name,
        fqdn=device.name,
        display=device.display,
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
        tags=[models.Entity(tag.id, tag.name) for tag in device.tags],
        custom_fields=device.custom_fields,  # ???
        created=device.created,
        last_updated=device.last_updated,
        breed=get_breed(
            device.device_type.manufacturer.name,
            device.device_type.model,
        ),
        hw=get_hw(
            device.device_type.manufacturer.name,
            device.device_type.model,
        ),
        interfaces=[],
        neighbours_ids=[],
        storage=storage,
    )


def extend_interface(interface: Interface, ip_addresses: list[models.IpAddress]) -> models.Interface:
    return models.Interface(
        id=interface.id,
        name=interface.name,
        device=interface.device,
        enabled=interface.enabled,
        display=interface.name,
        ip_addresses=ip_addresses,
    )


def extend_ip(ip: IPAddress) -> models.IpAddress:
    return models.IpAddress(
        id=ip.id,
        assigned_object_id=ip.interface.id,
        display=ip.address,
        family=models.IpFamily(
            value=ip.family,
            label=str(ip.family),
        ),
        address=ip.address,
        status=extend_label(ip.status),
        tags=[models.Entity(tag.id, tag.name) for tag in ip.tags],
        created=ip.created,
        last_updated=ip.last_updated,
    )
