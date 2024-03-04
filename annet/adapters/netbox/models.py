from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any

from annet.annlib.netdev.views.hardware import HardwareView


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


@dataclass
class Interface(Entity):
    device: Entity
    enabled: bool
    display: str = ""  # added in 3.x

    # filled later
    ip_addreses: List[IpAddress] = field(default_factory=list)


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
class Device(Entity):
    display: str  # renamed in 3.x from display_name
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
    custom_fields: dict[str, Any]
    created: datetime
    last_updated: datetime
    # filled later
    interfaces: List[Interface] = field(default_factory=list)

    # compat
    def __hash__(self):
        return hash(self.id)

    @property
    def fqdn(self):
        return self.name

    @property
    def hostname(self):
        return self.name

    def is_pc(self):
        return self.device_type.manufacturer.name == "Mellanox"

    @property
    def hw(self):
        manufacturer = self.device_type.manufacturer.name
        model_name = self.device_type.model
        # by some reason Netbox calls Mellanox SN as MSN, so we fix them here
        if manufacturer == "Mellanox" and model_name.startswith("MSN"):
            model_name = model_name.replace("MSN", "SN", 1)
        hw = _vendor_to_hw(manufacturer + " " + model_name)
        if not hw:
            raise ValueError(f"unsupported manufacturer {manufacturer}")
        return hw

    @property
    def breed(self):
        manufacturer = self.device_type.manufacturer.name
        model_name = self.device_type.model
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
