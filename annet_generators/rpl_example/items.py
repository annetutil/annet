from collections.abc import Sequence
from dataclasses import dataclass

from annet.rpl_generators.entities import CommunityList, CommunityType

AS_PATH_FILTERS = {
    "ASP_EXAMPLE": [".*123456.*"],
}

IPV6_PREFIX_LISTS = {
    "IPV6_LIST_EXAMPLE": ["2a13:5941::/32"],
}


COMMUNITIES = [
    CommunityList("COMMUNITY_EXAMPLE_ADD", ["1234:1000"]),
    CommunityList("COMMUNITY_EXAMPLE_REMOVE", ["1234:999"]),
    CommunityList("EXTCOMMUNITY_EXAMPLE_ADD", ["12345:1000"], CommunityType.RT),
    CommunityList("EXTCOMMUNITY_EXAMPLE_REMOVE", ["12345:999"], CommunityType.RT),
]