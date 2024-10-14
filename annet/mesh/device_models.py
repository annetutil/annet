from typing import Annotated

from .basemodel import BaseMeshModel, Concat, DictMerge, Merge, Merger, T, KeyDefaultDict
from .peer_models import MeshPeerGroup
from ..bgp_models import Family, Aggregate, Redistribute, ASN


class FamilyOptions(BaseMeshModel):
    family: Family
    vrf_name: str
    multipath: int = 0
    global_multipath: int
    aggregate: Aggregate
    redistributes: Annotated[tuple[Redistribute, ...], Concat()]
    allow_default: bool
    aspath_relax: bool
    igp_ignore: bool
    next_hop_policy: bool
    rib_import_policy: bool
    advertise_l2vpn_evpn: bool
    rib_group: bool
    loops: int
    advertise_bgp_static: bool


class _FamiliesMixin:
    ipv4_unicast: FamilyOptions | None
    ipv6_unicast: FamilyOptions | None
    ipv4_labeled_unicast: FamilyOptions | None
    ipv6_labeled_unicast: FamilyOptions | None


class VrfOptions(BaseMeshModel, _FamiliesMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault('groups', KeyDefaultDict(lambda x: MeshPeerGroup(name=x)))
        super().__init__(**kwargs)

    vrf_name: str
    vrf_name_global: str | None
    import_policy: str | None
    export_policy: str | None
    rt_import: Annotated[tuple[str, ...], Concat()]
    rt_export: Annotated[tuple[str, ...], Concat()]
    rt_import_v4: Annotated[tuple[str, ...], Concat()]
    rt_export_v4: Annotated[tuple[str, ...], Concat()]
    route_distinguisher: str | None
    auto_export: bool  # TODO: None?
    static_label: int | None  # FIXME: str?
    groups: Annotated[dict[str, MeshPeerGroup], DictMerge(Merge())]


class GlobalOptionsDTO(BaseMeshModel, _FamiliesMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault('groups', KeyDefaultDict(lambda x: MeshPeerGroup(name=x)))
        kwargs.setdefault('vrf', KeyDefaultDict(lambda x: VrfOptions(vrf_name=x)))
        super().__init__(**kwargs)

    local_as: ASN
    loops: int
    multipath: int
    router_id: str
    vrf: Annotated[dict[str, VrfOptions], DictMerge(Merge())]
    groups: Annotated[dict[str, MeshPeerGroup], DictMerge(Merge())]
