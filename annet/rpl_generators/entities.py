from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum



@dataclass(frozen=True)
class CommunityList:
    name: str
    values: Sequence[str]


class ExtCommunityType(Enum):
    REGULAR = "REGULAR"
    RT = "RT"
    SOO = "SOO"


@dataclass(frozen=True)
class ExtCommunityList:
    name: str
    values: Sequence[str]
    type: ExtCommunityType


@dataclass(frozen=True)
class RouteDistinguisherFilter:
    name: str
    members: Sequence[str]
