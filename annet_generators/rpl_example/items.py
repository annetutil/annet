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
    is_extended: bool = False
    is_color: bool = False


COMMUNITIES = {
    "COMMUNITY_EXAMPLE_ADD": Community(["1234:1000"]),
    "COMMUNITY_EXAMPLE_REMOVE": Community(["12345:999"]),
}
