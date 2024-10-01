from dataclasses import dataclass
from typing import Literal, Annotated

from .basemodel import BaseMeshModel, Merge, DictMerge, Forbid

FamilyName = Literal["ipv4_unicast", "ipv6_unicast", "ipv4_labeled", "ipv6_labeled"]


@dataclass
class BFDTimers:
    minimum_interval: int = 500
    multiplier: int = 4


class PeerGroup(BaseMeshModel):
    name: str
    remote_as: int = 0
    internal_name: str = ""
    update_source: str | None
    connect_retry: bool | None
    description: str | None

    @classmethod
    def default(cls):
        return cls(
            name="",
            remote_as=0,
            internal_name="",
            update_source=None,
            connect_retry=None,
            description=None,
        )


class SessionDTO(BaseMeshModel):
    asnum: str
    vrf: str
    name: str
    families: Annotated[list[FamilyName], Merge()]
    group: PeerGroup

    subif: str
    bmp_monitor: bool
    add_path: bool
    multipath: bool
    multipath: bool
    advertise_irb: bool
    send_labeled: bool
    send_community: bool
    lagg_links: int

    import_policy: str
    export_policy: str

    bfd: bool
    bfd_timers: BFDTimers


class PeerDTO(SessionDTO):
    pod: int
    addr: str
    families: Annotated[list[FamilyName], Merge()]

    import_policy: str
    export_policy: str


class VrfOptions(BaseMeshModel):
    vrf_name_global: str | None = None


class GlobalOptionsDTO(BaseMeshModel):
    local_as: int
    loops: int
    multipath: int
    router_id: str
    vrf: Annotated[dict[str, VrfOptions], DictMerge(Forbid)]

    @classmethod
    def default(cls):
        return GlobalOptionsDTO(
            local_as=0,
            loops=0,
            multipath=0,
            router_id="",
            vrf={},
        )


assert not GlobalOptionsDTO.default().unset_attrs()
