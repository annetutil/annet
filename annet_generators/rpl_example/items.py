from collections.abc import Sequence
from dataclasses import dataclass

AS_PATH_FILTERS = {
    "ASP_EXAMPLE": [".*123456.*"],
}

IPV6_PREFIX_LISTS = {
    "IPV6_LIST_EXAMPLE": ["2a13:5941::/32"],
}


@dataclass(frozen=True)
class Community:
    values: Sequence[str]


@dataclass(frozen=True)
class ExtCommunity:
    values: Sequence[str]


COMMUNITIES = {
    "COMMUNITY_EXAMPLE_ADD": Community(["1234:1000"]),
    "COMMUNITY_EXAMPLE_REMOVE": Community(["12345:999"]),
}

EXT_COMMUNITIES = {
    "COMMUNITY_EXAMPLE_ADD": ExtCommunity(["1234:1000"]),
    "COMMUNITY_EXAMPLE_REMOVE": ExtCommunity(["12345:999"]),
}
