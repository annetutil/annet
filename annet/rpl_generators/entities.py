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


def mangle_huawei_prefix_list_name(name: str, greater_equal: Optional[int], less_equal: Optional[int]) -> str:
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
