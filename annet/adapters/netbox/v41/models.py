from dataclasses import dataclass
from typing import Optional
import warnings
from datetime import datetime, timezone
from annet.adapters.netbox.common.models import Entity, Interface, InterfaceType, IpAddress, Label, NetboxDevice, DeviceIp, IpFamily, Prefix


@dataclass
class PrefixV41(Prefix):
    site: Optional[Entity] = None


@dataclass
class IpAddressV41(IpAddress[PrefixV41]):
    prefix: Optional[PrefixV41] = None


@dataclass
class InterfaceV41(Interface[IpAddressV41]):
    def _add_new_addr(self, address_mask: str, vrf: Entity | None, family: IpFamily) -> None:
        self.ip_addresses.append(IpAddressV41(
            id=0,
            display=address_mask,
            address=address_mask,
            vrf=vrf,
            prefix=None,
            family=family,
            created=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
            tags=[],
            status=Label(value="active", label="Active"),
            assigned_object_id=self.id,
        ))


@dataclass
class DeviceIpV41(DeviceIp):
    id: int
    display: str
    address: str
    family: IpFamily


@dataclass
class NetboxDeviceV41(NetboxDevice[InterfaceV41]):
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

    def _make_interface(self, name: str, type: InterfaceType) -> InterfaceV41:
        return InterfaceV41(
            name=name,
            device=self,
            enabled=True,
            description="",
            type=type,
            id=0,
            vrf=None,
            display=name,
            untagged_vlan=None,
            tagged_vlans=[],
            ip_addresses=[],
            connected_endpoints=[],
            mode=None,
        )
