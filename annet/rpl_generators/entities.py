from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Optional


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


@dataclass(frozen=True)
class IpPrefixList:
    name: str
    members: Sequence[str]


def arista_well_known_community(community: str) -> str:
    if community == "65535:0":
        return "GSHUT"
    return community


def mangle_united_community_list_name(values: Sequence[str]) -> str:
    """Name for a list used as HAS_ANY between multiple lists"""
    return "_OR_".join(values)


def mangle_ranged_prefix_list_name(name: str, greater_equal: Optional[int], less_equal: Optional[int]) -> str:
    if greater_equal is less_equal is None:
        return name
    if greater_equal is None:
        ge_str = "unset"
    else:
        ge_str = str(greater_equal)
    if less_equal is None:
        le_str = "unset"
    else:
        le_str = str(less_equal)
    return f"{name}_{ge_str}_{le_str}"
