from dataclasses import dataclass
from typing import Optional
from annet.adapters.netbox.common.models import Prefix, IpAddress, Entity


@dataclass
class PrefixV42(Prefix):
    scope: Optional[Entity] = None
    scope_type: str = ""

    @property
    def site(self):
        if self.scope_type == "dcim.site":
            return self.scope
        return None


@dataclass
class IpAddressV42(IpAddress):
    prefix: Optional[PrefixV42] = None
