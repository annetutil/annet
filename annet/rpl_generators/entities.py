from ipaddress import IPv4Network, IPv6Network, ip_network
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from annet.rpl import RoutingPolicy, PrefixMatchValue, SingleCondition, MatchField


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

    def __init__(
            self,
            prefix: IPv4Network | IPv6Network | str,
        ):
        self.prefix = ip_network(prefix)


@dataclass
class IpPrefixList:
    name: str
    members: list[IpPrefixListMember]

    def __init__(self, name: str, members: Sequence[IpPrefixListMember | str]):
        self.name = name
        self.members = []
        for m in members:
            if isinstance(m, str):
                m = IpPrefixListMember(m)
            self.members.append(m)


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
        self._orlongers = defaultdict(set)

        for policy in policies:
            for statement in policy.statements:
                condition: SingleCondition[PrefixMatchValue]
                for condition in statement.match.find_all(MatchField.ipv6_prefix):
                    for name in condition.value.names:
                        orlonger = (condition.value.greater_equal, condition.value.less_equal)
                        self._orlongers[name].add(orlonger)
                for condition in statement.match.find_all(MatchField.ip_prefix):
                    for name in condition.value.names:
                        orlonger = (condition.value.greater_equal, condition.value.less_equal)
                        self._orlongers[name].add(orlonger)

    def get_prefix(self, name: str, match: PrefixMatchValue) -> IpPrefixList:
        orig_prefix = self._prefix_lists[name]
        orig_name = orig_prefix.name
        greater_equal = match.greater_equal
        less_equal = match.less_equal

        if len(self._orlongers[orig_name]) == 1:
            name = orig_name
        elif greater_equal is less_equal is None:
            name = orig_name
        else:
            ge_str = "unset" if greater_equal is None else str(greater_equal)
            le_str = "unset" if less_equal is None else str(less_equal)
            name = f"{orig_name}_{ge_str}_{le_str}"

        return IpPrefixList(
            name=name,
            members=orig_prefix.members,
        )
