from dataclasses import dataclass
from typing import Optional
from annet.adapters.netbox.common.models import IpAddress, NetboxDevice, Entity, Prefix


@dataclass
class PrefixV37(Prefix):
    site: Optional[Entity] = None


@dataclass
class IpAddressV37(IpAddress):
    prefix: Optional[PrefixV37] = None


@dataclass
class NetboxDeviceV37(NetboxDevice):
    device_role: Entity 

    def __hash__(self):
        return hash((self.id, type(self)))
