from dataclasses import dataclass
from enum import Enum


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


class Family(Enum):
    IPV4_UNICAST = "IPV4_UNICAST"
    IPV6_UNICAST = "IPV6_UNICAST"
    IPV4_LABELED = "IPV4_LABELED"
    IPV6_LABELED = "IPV6_LABELED"


@dataclass(frozen=True, slots=True)
class PeerOptions:
    local_as: ASN
    unnumbered: bool
    rr_client: bool
    next_hop_self: bool
    extended_next_hop: bool
    send_community: bool
    send_lcommunity: bool
    send_extcommunity: bool
    send_labeled: bool
    import_limit: int | None
    teardown_timeout: bool
    # TODO more fields


@dataclass(frozen=True, slots=True)
class PeerGroup:
    name: str
    internal_name: str
    description: str | None
    remote_as: ASN
    update_source: str | None
    connect_retry: bool | None


@dataclass(frozen=True, slots=True)
class Peer:
    hostname: str
    addr: str
    remote_as: ASN
    family: Family
    name: str
    description: str
    vrf_name: str
    import_policy: str
    export_policy: str
    update_source: str  # interface name
    options: PeerOptions
    group: PeerGroup


