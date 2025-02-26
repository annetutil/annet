from dataclasses import dataclass
from typing import Optional
import warnings

from annet.adapters.netbox.common.models import Entity, IpAddress, NetboxDevice, DeviceIp, IpFamily, Prefix


@dataclass
class PrefixV41(Prefix):
    site: Optional[Entity] = None


@dataclass
class IpAddressV41(IpAddress):
    prefix: Optional[PrefixV41] = None


@dataclass
class DeviceIpV41(DeviceIp):
    id: int
    display: str
    address: str
    family: IpFamily


@dataclass
class NetboxDeviceV41(NetboxDevice):
    role: Entity
    primary_ip: Optional[DeviceIpV41]
    primary_ip4: Optional[DeviceIpV41]
    primary_ip6: Optional[DeviceIpV41]

    @property
    def device_role(self):
        warnings.warn(
            "'device_role' is deprecated, use 'role' instead.", 
            DeprecationWarning,
            stacklevel=2
        )
        return self.role

    def __hash__(self):
        return hash((self.id, type(self)))
