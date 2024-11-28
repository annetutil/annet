from annet.rpl_generators.entities import AsPathFilter, CommunityList, CommunityType, RDFilter

AS_PATH_FILTERS = [
    AsPathFilter("ASP_EXAMPLE", [".*123456.*"]),
]
COMMUNITIES = [
    CommunityList("COMMUNITY_EXAMPLE_ADD", ["1234:1000"]),
    CommunityList("COMMUNITY_EXAMPLE_REMOVE", ["1234:999"]),
    CommunityList("EXTCOMMUNITY_EXAMPLE_ADD", ["12345:1000"], CommunityType.RT),
    CommunityList("EXTCOMMUNITY_EXAMPLE_REMOVE", ["12345:999"], CommunityType.RT),
]

RD_FILTERS = [
    RDFilter("RD_EXAMPLE1", 1, ["100:1", "200:1"]),
    RDFilter("RD_EXAMPLE2", 2, ["10.2.2.2:1", "10.3.3.3:1"]),
]

# FIXME
IPV6_PREFIX_LISTS = {
    "IPV6_LIST_EXAMPLE": ["2a13:5941::/32"],
}
