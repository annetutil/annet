from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

from annet.adapters.netbox.common.models import (
    Entity, Label, DeviceType, DeviceIp,
)


@dataclass
class Interface(Entity):
    device: Entity
    enabled: bool
    display: str = ""  # added in 3.x


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
