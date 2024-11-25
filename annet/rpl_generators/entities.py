from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


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
    type: CommunityType
    members: Sequence[str]  #
    logic: CommunityLogic
    use_regex: bool


@dataclass(frozen=True)
class RouteDistinguisherFilter:
    name: str
    members: Sequence[str]
