from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any, Dict

from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage


@dataclass
class Entity:
    id: int
    name: str


@dataclass
class Label:
    value: str
    label: str


@dataclass
class IpFamily:
    value: int
    label: str


@dataclass
class DeviceType:
    id: int
    manufacturer: Entity
    model: str


@dataclass
class DeviceIp:
    id: int
    display: str
    address: str
    family: int


@dataclass
class Prefix:
    id: int
    prefix: str
    site: Entity | None
    vrf: Entity | None
    tenant: Entity | None
    vlan: Entity | None
    role: Entity | None
    status: Label
    is_pool: bool
    custom_fields: dict[str, Any]
    created: datetime
    last_updated: datetime


@dataclass
class IpAddress:
    id: int
    assigned_object_id: int
    display: str
    family: IpFamily
    address: str
    status: Label
    tags: List[Entity]
    created: datetime
    last_updated: datetime
    prefix: Optional[Prefix] = None


@dataclass
class InterfaceConnectedEndpoint(Entity):
    device: Entity


@dataclass
class InterfaceType:
    value: str
    label: str


@dataclass
class InterfaceMode:
    value: str
    label: str


@dataclass
class InterfaceVlan(Entity):
    vid: int


@dataclass
class Interface(Entity):
    device: Entity
    enabled: bool
    description: str
    type: InterfaceType
    connected_endpoints: Optional[list[InterfaceConnectedEndpoint]]
    mode: Optional[InterfaceMode]
    untagged_vlan: Optional[InterfaceVlan]
    tagged_vlans: Optional[List[InterfaceVlan]]
    display: str = ""
    ip_addresses: List[IpAddress] = field(default_factory=list)


@dataclass
class NetboxDevice(Entity):
    url: str
    storage: Storage

    display: str
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
    tags: List[Entity]
    custom_fields: Dict[str, Any]
    created: datetime
    last_updated: datetime

    fqdn: str
    hostname: str
    hw: Optional[HardwareView]
    breed: str

    interfaces: List[Interface]
    neighbours: Optional[List["NetboxDevice"]]

    # compat

    def __hash__(self):
        return hash((self.id, type(self)))

    def __eq__(self, other):
        return type(self) is type(other) and self.url == other.url

    def is_pc(self):
        return self.device_type.manufacturer.name == "Mellanox"
