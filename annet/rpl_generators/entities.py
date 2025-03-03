from ipaddress import IPv4Network, IPv6Network, ip_network
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from annet.rpl import RoutingPolicy, PrefixMatchValue, SingleCondition, MatchField, OrLonger


class CommunityLogic(Enum):
    AND = "AND"
    OR = "OR"


class CommunityType(Enum):
    BASIC = "BASIC"
    RT = "RT"
    SOO = "SOO"
    COST = "COST"
    LARGE = "LARGE"


@dataclass(frozen=True)
class CommunityList:
    name: str
    members: Sequence[str]
    type: CommunityType = CommunityType.BASIC
    logic: CommunityLogic = CommunityLogic.OR
    use_regex: bool = False


@dataclass(frozen=True)
class RDFilter:
    name: str
    number: int
    members: Sequence[str]


@dataclass(frozen=True)
class AsPathFilter:
    name: str
    filters: Sequence[str]


@dataclass
class IpPrefixListMember:
    prefix: IPv4Network | IPv6Network
    or_longer: OrLonger = (None, None)

    def __post_init__(self):
        self.prefix = ip_network(self.prefix)


@dataclass
class IpPrefixList:
    name: str
    members: list[IpPrefixListMember]

    def __post_init__(self):
        for (i, m) in enumerate(self.members):
            if isinstance(m, str):
                self.members[i] = IpPrefixListMember(m)


def ip_prefix_list(
        name: str,
        members: Sequence[IpPrefixListMember | str],
        or_longer: OrLonger = (None, None),
) -> IpPrefixList:
    for (i, m) in enumerate(members):
        if isinstance(m, str):
            m = IpPrefixListMember(m, or_longer)
        elif m.or_longer == (None, None):
            m.or_longer = or_longer
        members[i] = m
    return IpPrefixList(
        name=name,
        members=members,
    )


def arista_well_known_community(community: str) -> str:
    if community == "65535:0":
        return "GSHUT"
    return community


def mangle_united_community_list_name(values: Sequence[str]) -> str:
    """Name for a list used as HAS_ANY between multiple lists"""
    return "_OR_".join(values)


class PrefixListNameGenerator:
    def __init__(self, prefix_lists: Sequence[IpPrefixList], policies: Sequence[RoutingPolicy]):
        self._prefix_lists = {x.name: x for x in prefix_lists}
        self._policies = {x.name: x for x in policies}  # this is here for a later use ~azryve@

    def get_prefix(self, name: str, match: PrefixMatchValue) -> IpPrefixList:
        orig_prefix = self._prefix_lists[name]
        override_name: Optional[str] = None
        override_orlonger: Optional[OrLonger] = None

        if any(match.or_longer):
            ge, le = match.or_longer
            ge_str = "unset" if ge is None else str(ge)
            le_str = "unset" if le is None else str(le)
            override_name = f"{orig_prefix.name}_{ge_str}_{le_str}"
            override_orlonger = match.or_longer

        return IpPrefixList(
            name=override_name or name,
            members=[
                IpPrefixListMember(
                    x.prefix,
                    or_longer=override_orlonger or x.or_longer,
                )
                for x in orig_prefix.members
            ],
        )
