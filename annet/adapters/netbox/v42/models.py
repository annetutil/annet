from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from annet.adapters.netbox.common.models import InterfaceType, IpFamily, Label, Prefix, Entity
from annet.adapters.netbox.v41.models import InterfaceV41, IpAddressV41, NetboxDeviceV41


@dataclass
class PrefixV42(Prefix):
    scope: Optional[Entity] = None
    scope_type: str | None = None

    @property
    def site(self) -> Optional[Entity]:
        if self.scope_type == "dcim.site":
            return self.scope
        return None


@dataclass
class IpAddressV42(IpAddressV41):
    prefix: Optional[PrefixV42] = None


@dataclass
class InterfaceV42(InterfaceV41):
    def _add_new_addr(self, address_mask: str, vrf: Entity | None, family: IpFamily) -> None:
        self.ip_addresses.append(IpAddressV42(
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
class NetboxDeviceV42(NetboxDeviceV41):
    def __hash__(self):
        return hash((self.id, type(self)))

    def _make_interface(self, name: str, type: InterfaceType) -> InterfaceV42:
        return InterfaceV42(
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
