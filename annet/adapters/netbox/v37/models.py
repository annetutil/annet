from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from annet.adapters.netbox.common.models import (
    IpAddress, NetboxDevice, Entity, Prefix, InterfaceType, Interface, IpFamily, Label,
)


@dataclass
class PrefixV37(Prefix):
    site: Optional[Entity] = None


@dataclass
class IpAddressV37(IpAddress[PrefixV37]):
    prefix: Optional[PrefixV37] = None


@dataclass
class InterfaceV37(Interface[IpAddressV37]):
    def _add_new_addr(self, address_mask: str, vrf: Entity | None, family: IpFamily) -> None:
        self.ip_addresses.append(IpAddressV37(
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
class NetboxDeviceV37(NetboxDevice[InterfaceV37]):
    device_role: Entity

    def __hash__(self):
        return hash((self.id, type(self)))

    def _make_interface(self, name: str, type: InterfaceType) -> InterfaceV37:
        return InterfaceV37(
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
