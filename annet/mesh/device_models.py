from typing import Annotated, Optional, Union

from annet.bgp_models import Family, Aggregate, Redistribute
from .basemodel import BaseMeshModel, Concat, DictMerge, Merge, KeyDefaultDict
from .peer_models import MeshPeerGroup


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
    ipv4_unicast: Optional[FamilyOptions]
    ipv6_unicast: Optional[FamilyOptions]
    ipv4_labeled_unicast: Optional[FamilyOptions]
    ipv6_labeled_unicast: Optional[FamilyOptions]


class VrfOptions(BaseMeshModel, _FamiliesMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault("groups", KeyDefaultDict(lambda x: MeshPeerGroup(name=x)))
        super().__init__(**kwargs)

    vrf_name: str
    vrf_name_global: Optional[str]
    import_policy: Optional[str]
    export_policy: Optional[str]
    rt_import: Annotated[tuple[str, ...], Concat()]
    rt_export: Annotated[tuple[str, ...], Concat()]
    rt_import_v4: Annotated[tuple[str, ...], Concat()]
    rt_export_v4: Annotated[tuple[str, ...], Concat()]
    route_distinguisher: Optional[str]
    static_label: Optional[int]  # FIXME: str?
    groups: Annotated[dict[str, MeshPeerGroup], DictMerge(Merge())]


class GlobalOptionsDTO(BaseMeshModel, _FamiliesMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault("groups", KeyDefaultDict(lambda x: MeshPeerGroup(name=x)))
        kwargs.setdefault("vrf", KeyDefaultDict(lambda x: VrfOptions(vrf_name=x)))
        super().__init__(**kwargs)

    local_as: Union[int, str]
    loops: int
    multipath: int
    router_id: str
    vrf: Annotated[dict[str, VrfOptions], DictMerge(Merge())]
    groups: Annotated[dict[str, MeshPeerGroup], DictMerge(Merge())]
