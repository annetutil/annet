from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

from annet.adapters.netbox.common.models import Entity, DeviceType


@dataclass
class Label:
    value: int
    label: str


@dataclass
class DeviceIp:
    id: int
    address: str
    family: int


@dataclass
class Device(Entity):
    display_name: str
    device_type: DeviceType
    device_role: Entity
    tenant: Optional[Entity]
    platform: Optional[Entity]
    serial: str
    asset_tag: Optional[str]
    site: Entity
    rack: Optional[Entity]
    position: Optional[float]
    face: Optional[Label]
    status: Label
    primary_ip: Optional[DeviceIp]
    primary_ip4: Optional[DeviceIp]
    primary_ip6: Optional[DeviceIp]
    tags: List[str]
    custom_fields: dict[str, Any]
    created: datetime
    last_updated: datetime


@dataclass
class Interface(Entity):
    device: Entity
    enabled: bool


@dataclass
class Vrf(Entity):
    rd: str


@dataclass
class IpAddress:
    id: int
    family: int
    address: str
    vrf: Optional[Vrf]
    tenant: Any  # ???
    status: Label
    description: Optional[str]
    custom_fields: dict[str, Any]
    tags: List[str]
    created: datetime
    last_updated: datetime

    interface: Entity

    nat_inside: Any  # ???
    nat_outside: Any  # ???
