from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ASN(int):
    """
    Stores ASN number and formats it as в AS1.AS2
    None is treated like 0. Supports integer operations
    Supported formats: https://tools.ietf.org/html/rfc5396#section-1
    """
    PLAIN_MAX = 0x10000

    def __new__(cls, asn):
        if isinstance(asn, ASN):
            return asn
        elif asn is None:
            asn = 0
        elif not isinstance(asn, int):
            if isinstance(asn, float):
                asn = str(asn)
            if isinstance(asn, str) and "." in asn:
                high, low = [int(token) for token in asn.split(".")]
                if not (0 <= high < ASN.PLAIN_MAX and 0 <= low < ASN.PLAIN_MAX):
                    raise ValueError("Invalid ASN asn %r" % asn)
                asn = (high << 16) + low
            asn = int(asn)
        if not 0 <= asn <= 0xffffffff:
            raise ValueError("Invalid ASN asn %r" % asn)
        return int.__new__(cls, asn)

    def __add__(self, other):
        return ASN(super().__add__(other))

    def __sub__(self, other):
        return ASN(super().__sub__(other))

    def __mul__(self, other):
        return ASN(super().__mul__(other))

    def is_plain(self):
        return self < ASN.PLAIN_MAX

    def asdot(self):
        if not self.is_plain():
            return "%d.%d" % (self // ASN.PLAIN_MAX, self % ASN.PLAIN_MAX)
        return "%d" % self

    def asplain(self):
        return "%d" % self

    def asdot_high(self):
        return self // ASN.PLAIN_MAX

    def asdot_low(self):
        return self % ASN.PLAIN_MAX

    __str__ = asdot

    def __repr__(self):
        srepr = str(self)
        if "." in srepr:
            srepr = repr(srepr)
        return f"{self.__class__.__name__}({srepr})"


@dataclass(frozen=True, slots=True)
class BFDTimers:
    minimum_interval: int
    multiplier: int


Family = Literal["ipv4_unicast", "ipv6_unicast", "ipv4_labeled", "ipv6_labeled"]


@dataclass(frozen=True, slots=True, kw_only=True)
class PeerOptions:
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
    bfd_timers: BFDTimers | None = None,
    resolve_vpn: bool = False
    af_rib_group: str | None = None,
    af_loops: int = 0,
    hold_time: int = 0,
    listen_network: bool = False
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


@dataclass(frozen=True, slots=True, kw_only=True)
class PeerGroup:
    name: str
    remote_as: ASN = ASN(None)
    internal_name: str
    description: str | None
    update_source: str | None
    connect_retry: bool | None


@dataclass(slots=True, kw_only=True)
class Peer:
    addr: str
    remote_as: ASN
    families: set[Family]
    name: str = ""
    description: str = ""
    vrf_name: str = ""
    import_policy: str = ""
    export_policy: str = ""
    update_source: str | None = None  # interface name
    options: PeerOptions | None = None
    group: PeerGroup | None = None
    hostname: str = ""


@dataclass(slots=True)
class Aggregate:
    policy: str = ""
    routes: tuple[str, ...] = ()  # "182.168.1.0/24",
    export_policy: str = ""
    as_path: str = ""
    reference: str = ""
    suppress: bool = False
    discard: bool = True
    as_set: bool = False


@dataclass(slots=True)
class Redistribute:
    protocol: str
    policy: str | None = None  # TODO


@dataclass(slots=True, kw_only=True)
class FamilyOptions:
    family: Family
    vrf_name: str
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


@dataclass(slots=True, kw_only=True)
class _FamiliesMixin:
    ipv4_unicast: FamilyOptions | None = None
    ipv6_unicast: FamilyOptions | None = None
    ipv4_labeled_unicast: FamilyOptions | None = None
    ipv6_labeled_unicast: FamilyOptions | None = None


@dataclass(slots=True, kw_only=True)
class VrfOptions(_FamiliesMixin):
    vrf_name: str
    vrf_name_global: str | None = None
    import_policy: str | None = None
    export_policy: str | None = None
    rt_import: list[str] = field(default_factory=list)
    rt_export: list[str] = field(default_factory=list)
    rt_import_v4: list[str] = field(default_factory=list)
    rt_export_v4: list[str] = field(default_factory=list)
    route_distinguisher: str | None = None
    auto_export: bool = False  # TODO: None?
    static_label: int | None = None  # FIXME: str?


@dataclass(slots=True, kw_only=True)
class GlobalOptions(_FamiliesMixin):
    local_as: ASN = ASN(None)
    loops: int = 0
    multipath: int = 0
    router_id: str = ""
    vrf: dict[str, VrfOptions] = field(default_factory=dict)
