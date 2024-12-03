from typing import Annotated, Optional, Union

from annet.bgp_models import Family, Redistribute
from .basemodel import BaseMeshModel, Concat, DictMerge, Merge, KeyDefaultDict
from .peer_models import MeshPeerGroup


class Aggregate(BaseMeshModel):
    policy: str
    routes: Annotated[tuple[str, ...], Concat()]
    export_policy: str
    as_path: str
    reference: str
    suppress: bool
    discard: bool
    as_set: bool


class FamilyOptions(BaseMeshModel):
    def __init__(self, **kwargs):
        kwargs.setdefault("aggregate", Aggregate())
        super().__init__(**kwargs)
    family: Family
    vrf_name: str
    multipath: int = 0
    global_multipath: int
    aggregate: Annotated[Aggregate, Merge()]
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
    def __init__(self, **kwargs):
        kwargs.setdefault("ipv4_unicast", FamilyOptions(family="ipv4_unicast"))
        kwargs.setdefault("ipv6_unicast", FamilyOptions(family="ipv6_unicast"))
        kwargs.setdefault("ipv4_labeled_unicast", FamilyOptions(family="ipv4_labeled_unicast"))
        kwargs.setdefault("ipv6_labeled_unicast", FamilyOptions(family="ipv6_labeled_unicast"))
        super().__init__(**kwargs)
    ipv4_unicast: Annotated[FamilyOptions, Merge()]
    ipv6_unicast: Annotated[FamilyOptions, Merge()]
    ipv4_labeled_unicast: Annotated[FamilyOptions, Merge()]
    ipv6_labeled_unicast: Annotated[FamilyOptions, Merge()]


class VrfOptions(_FamiliesMixin, BaseMeshModel):
    def __init__(self, vrf_name: str, **kwargs):
        kwargs.setdefault("ipv4_unicast", FamilyOptions(family="ipv4_unicast", vrf_name=vrf_name))
        kwargs.setdefault("ipv6_unicast", FamilyOptions(family="ipv6_unicast", vrf_name=vrf_name))
        kwargs.setdefault("ipv4_labeled_unicast", FamilyOptions(family="ipv4_labeled_unicast", vrf_name=vrf_name))
        kwargs.setdefault("ipv6_labeled_unicast", FamilyOptions(family="ipv6_labeled_unicast", vrf_name=vrf_name))
        kwargs.setdefault("groups", KeyDefaultDict(lambda x: MeshPeerGroup(name=x)))
        super().__init__(vrf_name=vrf_name, **kwargs)

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


class GlobalOptionsDTO(_FamiliesMixin, BaseMeshModel):
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
