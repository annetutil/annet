from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from annet.adapters.netbox.common.models import InterfaceType, IpFamily, Label, Prefix, Entity
from annet.adapters.netbox.v41.models import InterfaceV41, IpAddressV41, NetboxDeviceV41
import annetbox.v43.models


@dataclass
class PrefixV43(Prefix):
    scope: Optional[Entity] = None
    scope_type: str | None = None

    @property
    def site(self) -> Optional[Entity]:
        if self.scope_type == "dcim.site":
            return self.scope
        return None


@dataclass
class IpAddressV43(IpAddressV41):
    prefix: Optional[PrefixV43] = None


@dataclass
class InterfaceV43(InterfaceV41):
    def _add_new_addr(self, address_mask: str, vrf: Entity | None, family: IpFamily) -> None:
        self.ip_addresses.append(IpAddressV43(
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
class NetboxDeviceV43(NetboxDeviceV41):
    def __hash__(self):
        return hash((self.id, type(self)))

    def _make_interface(self, name: str, type: InterfaceType) -> InterfaceV43:
        return InterfaceV43(
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


# should be unified in case of netbox update
Vrf = annetbox.v43.models.Vrf
Vlan = annetbox.v43.models.Vlan
