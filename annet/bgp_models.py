from dataclasses import dataclass, field
from typing import Literal, Union, Optional


class ASN(int):
    """
    Stores ASN number and formats it as в AS1.AS2
    None is treated like 0. Supports integer operations
    Supported formats: https://tools.ietf.org/html/rfc5396#section-1
    """
    PLAIN_MAX = 0x10000

    def __new__(cls, asn: Union[int, str, None, "ASN"]):
        if isinstance(asn, ASN):
            return asn
        elif asn is None:
            asn = 0
        elif not isinstance(asn, int):
            if isinstance(asn, str) and "." in asn:
                high, low = [int(token) for token in asn.split(".")]
                if not (0 <= high < ASN.PLAIN_MAX and 0 <= low < ASN.PLAIN_MAX):
                    raise ValueError("Invalid ASN asn %r" % asn)
                asn = (high << 16) + low
            asn = int(asn)
        if not 0 <= asn <= 0xffffffff:
            raise ValueError("Invalid ASN asn %r" % asn)
        return int.__new__(cls, asn)

    def __add__(self, other: int):
        return ASN(super().__add__(other))

    def __sub__(self, other: int):
        return ASN(super().__sub__(other))

    def __mul__(self, other: int):
        return ASN(super().__mul__(other))

    def is_plain(self) -> bool:
        return self < ASN.PLAIN_MAX

    def asdot(self) -> str:
        if not self.is_plain():
            return "%d.%d" % (self // ASN.PLAIN_MAX, self % ASN.PLAIN_MAX)
        return "%d" % self

    def asplain(self) -> str:
        return "%d" % self

    def asdot_high(self) -> int:
        return self // ASN.PLAIN_MAX

    def asdot_low(self) -> int:
        return self % ASN.PLAIN_MAX

    __str__ = asdot

    def __repr__(self) -> str:
        srepr = str(self)
        if "." in srepr:
            srepr = repr(srepr)
        return f"{self.__class__.__name__}({srepr})"


@dataclass(frozen=True)
class BFDTimers:
    minimum_interval: int = 500
    multiplier: int = 4


Family = Literal["ipv4_unicast", "ipv6_unicast", "ipv4_labeled_unicast", "ipv6_labeled_unicast"]


@dataclass(frozen=True)
class PeerOptions:
    """The same options as for group but any field is optional"""
    local_as: Optional[ASN] = None
    unnumbered: Optional[bool] = None
    rr_client: Optional[bool] = None
    next_hop_self: Optional[bool] = None
    extended_next_hop: Optional[bool] = None
    send_community: Optional[bool] = None
    send_lcommunity: Optional[bool] = None
    send_extcommunity: Optional[bool] = None
    send_labeled: Optional[bool] = None
    import_limit: Optional[bool] = None
    teardown_timeout: Optional[bool] = None
    redistribute: Optional[bool] = None
    passive: Optional[bool] = None
    mtu_discovery: Optional[bool] = None
    advertise_inactive: Optional[bool] = None
    advertise_bgp_static: Optional[bool] = None
    allowas_in: Optional[bool] = None
    auth_key: Optional[bool] = None
    add_path: Optional[bool] = None
    multipath: Optional[bool] = None
    multihop: Optional[bool] = None
    multihop_no_nexthop_change: Optional[bool] = None
    af_no_install: Optional[bool] = None
    bfd: Optional[bool] = None
    rib: Optional[bool] = None
    bfd_timers: Optional[BFDTimers] = None
    resolve_vpn: Optional[bool] = None
    af_rib_group: Optional[str] = None
    af_loops: Optional[int] = None
    hold_time: Optional[int] = None
    listen_network: Optional[list[str]] = None
    remove_private: Optional[bool] = None
    as_override: Optional[bool] = None
    aigp: Optional[bool] = None
    bmp_monitor: Optional[bool] = None
    no_prepend: Optional[bool] = None
    no_explicit_null: Optional[bool] = None
    uniq_iface: Optional[bool] = None
    advertise_peer_as: Optional[bool] = None
    connect_retry: Optional[bool] = None
    advertise_external: Optional[bool] = None
    advertise_irb: Optional[bool] = None
    listen_only: Optional[bool] = None
    soft_reconfiguration_inbound: Optional[bool] = None
    not_active: Optional[bool] = None
    mtu: Optional[int] = None


@dataclass
class Peer:
    addr: str
    interface: Optional[str]
    remote_as: ASN
    families: set[Family] = field(default_factory=set)
    description: str = ""
    vrf_name: str = ""
    group_name: str = ""
    import_policy: str = ""
    export_policy: str = ""
    update_source: Optional[str] = None
    options: Optional[PeerOptions] = None
    hostname: str = ""


@dataclass
class Aggregate:
    policy: str = ""
    routes: tuple[str, ...] = ()  # "182.168.1.0/24",
    export_policy: str = ""
    as_path: str = ""
    reference: str = ""
    suppress: bool = False
    discard: bool = True
    as_set: bool = False


@dataclass
class Redistribute:
    protocol: str
    policy: str = ""


@dataclass
class FamilyOptions:
    family: Family
    vrf_name: str = ""
    multipath: int = 0
    global_multipath: int = 0
    aggregate: Aggregate = field(default_factory=Aggregate)
    redistributes: tuple[Redistribute, ...] = ()
    allow_default: bool = False
    aspath_relax: bool = False
    igp_ignore: bool = False
    next_hop_policy: bool = False
    rib_import_policy: bool = False
    advertise_l2vpn_evpn: bool = False
    rib_group: bool = False
    loops: int = 0
    advertise_bgp_static: bool = False


@dataclass(frozen=True)
class PeerGroup:
    name: str
    remote_as: ASN = ASN(None)
    families: set[Family] = field(default_factory=set)
    internal_name: str = ""
    description: str = ""
    update_source: str = ""
    import_policy: str = ""
    export_policy: str = ""

    # more strict version of PeerOptions
    local_as: ASN = ASN(None)
    unnumbered: bool = False
    rr_client: bool = False
    next_hop_self: bool = False
    extended_next_hop: bool = False
    send_community: bool = False
    send_lcommunity: bool = False
    send_extcommunity: bool = False
    send_labeled: bool = False
    import_limit: bool = False
    teardown_timeout: bool = False
    redistribute: bool = False
    passive: bool = False
    mtu_discovery: bool = False
    advertise_inactive: bool = False
    advertise_bgp_static: bool = False
    allowas_in: bool = False
    auth_key: bool = False
    add_path: bool = False
    multipath: bool = False
    multihop: bool = False
    multihop_no_nexthop_change: bool = False
    af_no_install: bool = False
    bfd: bool = False
    rib: bool = False
    bfd_timers: Optional[BFDTimers] = None
    resolve_vpn: bool = False
    af_rib_group: Optional[str] = None
    af_loops: int = 0
    hold_time: int = 0
    listen_network: list[str] = field(default_factory=list)
    remove_private: bool = False
    as_override: bool = False
    aigp: bool = False
    bmp_monitor: bool = False
    no_prepend: bool = False
    no_explicit_null: bool = False
    uniq_iface: bool = False
    advertise_peer_as: bool = False
    connect_retry: bool = False
    advertise_external: bool = False
    advertise_irb: bool = False
    listen_only: bool = False
    soft_reconfiguration_inbound: bool = False
    not_active: bool = False
    mtu: int = 0


@dataclass
class VrfOptions:
    vrf_name: str

    ipv4_unicast: FamilyOptions
    ipv6_unicast: FamilyOptions
    ipv4_labeled_unicast: FamilyOptions
    ipv6_labeled_unicast: FamilyOptions

    vrf_name_global: Optional[str] = None
    rt_import: list[str] = field(default_factory=list)
    rt_export: list[str] = field(default_factory=list)
    rt_import_v4: list[str] = field(default_factory=list)
    rt_export_v4: list[str] = field(default_factory=list)
    route_distinguisher: Optional[str] = None
    static_label: Optional[int] = None  # FIXME: str?

    groups: list[PeerGroup] = field(default_factory=list)


@dataclass
class GlobalOptions:
    ipv4_unicast: FamilyOptions
    ipv6_unicast: FamilyOptions
    ipv4_labeled_unicast: FamilyOptions
    ipv6_labeled_unicast: FamilyOptions

    local_as: ASN = ASN(None)
    loops: int = 0
    multipath: int = 0
    router_id: str = ""
    vrf: dict[str, VrfOptions] = field(default_factory=dict)

    groups: list[PeerGroup] = field(default_factory=list)
