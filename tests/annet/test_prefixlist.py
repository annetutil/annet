from typing import Any, Sequence
from ipaddress import IPv4Network, IPv6Network
from unittest.mock import Mock
from annet.tabparser import make_formatter, parse_to_tree
from annet.rpl_generators import ip_prefix_list, IpPrefixList, IpPrefixListMember, PrefixListFilterGenerator, CumulusPolicyGenerator
from annet.rpl import R, RouteMap, Route, RoutingPolicy

from . import MockDevice


def test_ip_prefix_list():
    assert ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]) == IpPrefixList(
        name="IPV4_LIST",
        members=[
            IpPrefixListMember(
                prefix=IPv4Network("10.0.0.0/8"),
                or_longer=(None, None),
            ),
        ])

    assert ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"], (None, 32)) == IpPrefixList(
        name="IPV4_LIST",
        members=[
            IpPrefixListMember(
                prefix=IPv4Network("10.0.0.0/8"),
                or_longer=(None, 32),
            ),
        ])

    assert ip_prefix_list("IPV4_LIST", [IpPrefixListMember(IPv4Network("10.0.0.0/8"), (8, 32)), "11.0.0.0/8"], (None, 32)) == IpPrefixList(
        name="IPV4_LIST",
        members=[
            IpPrefixListMember(
                prefix=IPv4Network("10.0.0.0/8"),
                or_longer=(8, 32),
            ),
            IpPrefixListMember(
                prefix=IPv4Network("11.0.0.0/8"),
                or_longer=(None, 32),
            ),
        ])

def test_huawei_prefixlist_basic():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST")) as rule:
            rule.allow()

    result = gen(routemaps, plists, huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64
""")
    assert result == expected


def test_arista_prefixlist_basic():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST")) as rule:
            rule.allow()

    result = gen(routemaps, plists, arista())
    expected = scrub("""
ip prefix-list IPV4_LIST
  seq 10 permit 10.0.0.0/8
ipv6 prefix-list IPV6_LIST
  seq 10 permit 2001:db8:1234::/64
""")
    assert result == expected


def test_cumulus_prefixlist_basic():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST"), name="n10", number=10) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), name="n20", number=20) as rule:
            rule.allow()

    result = gen(routemaps, plists, cumulus())
    expected = scrub("""
ip prefix-list IPV4_LIST seq 5 permit 10.0.0.0/8
ipv6 prefix-list IPV6_LIST seq 5 permit 2001:db8:1234::/64
""")
    assert result == expected


def test_huawei_prefixlist_with_match_orlonger():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32))) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128))) as rule:
            rule.allow()

    result = gen(routemaps, plists, huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST_8_32 index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST_64_128 index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
""")
    assert result == expected


def test_arista_prefixlist_match_orlonger():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32))) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128))) as rule:
            rule.allow()

    result = gen(routemaps, plists, arista())
    expected = scrub("""
ip prefix-list IPV4_LIST_8_32
  seq 10 permit 10.0.0.0/8 ge 8 le 32
ipv6 prefix-list IPV6_LIST_64_128
  seq 10 permit 2001:db8:1234::/64 ge 64 le 128
""")
    assert result == expected


def test_cumulus_prefixlist_match_orlonger():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32)), name="n10", number=10) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128)), name="n20", number=20) as rule:
            rule.allow()

    result = gen(routemaps, plists, cumulus())
    expected = scrub("""
ip prefix-list IPV4_LIST_8_32 seq 5 permit 10.0.0.0/8 ge 8 le 32
ipv6 prefix-list IPV6_LIST_64_128 seq 5 permit 2001:db8:1234::/64 ge 64 le 128
""")
    assert result == expected


def test_huawei_prefixlist_with_match_both():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST")) as rule:
            rule.allow()
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32))) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128))) as rule:
            rule.allow()

    result = gen(routemaps, plists, huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64
ip ip-prefix IPV4_LIST_8_32 index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST_64_128 index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
""")
    assert result == expected


def test_huawei_prefixlist_embedded_orlonger():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"], (8, 32)),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"], (64, 128)),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST")) as rule:
            rule.allow()


    result = gen(routemaps, plists, huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
""")
    assert result == expected


def gen(routemaps: RouteMap, plists: list[IpPrefixList], dev: MockDevice) -> str:
    class TestPrefixListFilterGenerator(PrefixListFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
            return plists

    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
            return plists

        def get_community_lists(self, _: Any) -> list:
            return []

        def get_as_path_filters(self, _: Any) -> list:
            return []

    if dev.hw.soft.startswith("Cumulus"):
        generator = TestCumulusPolicyGenerator()
        result = generator.generate_cumulus_rpl(dev)
        # leave only prefix-list related commands
        # <ip|ipv6> prefix-list ...
        result = (x for x in result if len(x) > 2)
        result = (x for x in result if x[1] == "prefix-list") 
        result = (" ".join(x) for x in result)
        text = "\n".join(result)
    else: 
        storage = Mock()
        generator = TestPrefixListFilterGenerator(storage)
        result = generator(dev) 
        fmtr = make_formatter(dev.hw)
        tree = parse_to_tree(result, fmtr.split)
        text = fmtr.join(tree)
    return scrub(text)


def scrub(text: str) -> str:
    splitted = text.split("\n")
    return "\n".join(filter(None, splitted))


def huawei():
    return MockDevice(
        "Huawei CE6870-48S6CQ-EI", 
        "VRP V200R001C00SPC700 + V200R001SPH002",
        "vrp85",
    )


def arista():
    return MockDevice(
        "Arista DCS-7368", 
        "EOS 4.29.9.1M",
        "arista",
    )

def cumulus():
    return MockDevice(
        "Mellanox SN3700-VS2RO",
        "Cumulus Linux 5.4.0",
        "pc",
    )
