from dataclasses import dataclass
from datetime import datetime
from typing import List


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
