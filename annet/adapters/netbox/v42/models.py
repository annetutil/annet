from dataclasses import dataclass
from typing import Optional
from annet.adapters.netbox.common.models import Prefix, IpAddress, Entity
from annet.adapters.netbox.v41.models import NetboxDeviceV41


@dataclass
class PrefixV42(Prefix):
    scope: Optional[Entity] = None


@dataclass
class IpAddressV42(IpAddress):
    prefix: Optional[PrefixV42] = None


@dataclass
class NetboxDeviceV42(NetboxDeviceV41):
    def __hash__(self):
        return hash((self.id, type(self)))
