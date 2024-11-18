from enum import Enum

class ConditionField(str, Enum):
    community = "community"
    extcommunity = "extcommunity"
    rd = "rd"
    interface = "interface"
    protocol="protocol"

    as_path_length = "as_path_length"
    as_path_filter = "as_path_filter"
    ipv6_prefix = "ipv6_prefix"
    ip_prefix = "ip_prefix"