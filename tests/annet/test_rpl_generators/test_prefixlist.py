from typing import Any, Sequence
from ipaddress import IPv4Network
from unittest.mock import Mock
from annet.vendors.tabparser import parse_to_tree
from annet.rpl_generators import ip_prefix_list, IpPrefixList, IpPrefixListMember, PrefixListFilterGenerator, CumulusPolicyGenerator, RoutingPolicyGenerator
from annet.rpl import R, RouteMap, Route, RoutingPolicy
from annet.vendors import registry_connector
from .. import MockDevice
from .helpers import scrub, huawei, arista, cumulus


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


def test_arista_tutorial():
    plists = [
        ip_prefix_list("LOCAL_NETS", ["192.168.0.0/16"], (16, 32)),
    ]
    routemap = RouteMap[Mock]()
    @routemap
    def IMPORT_CONNECTED(_: Mock, route: Route):
        with route(
                R.protocol == "connected",
                R.match_v4("LOCAL_NETS"),
                number=10
        ) as rule:
            rule.community.set("ADVERTISE")
            rule.allow()
        with route(number=20) as rule:
            rule.deny()


    @routemap
    def ROUTERS_IMPORT(_: Mock, route: Route):
        with route(
                R.match_v4("LOCAL_NETS", or_longer=(16, 24)),  # custom ge/le
                R.community.has("ADVERTISE"),
                number=10
        ) as rule:
            rule.allow()
        with route(number=20) as rule:
            rule.deny()


    @routemap
    def ROUTERS_EXPORT(_: Mock, route: Route):
        with route(
                R.community.has("ADVERTISE"),
                number=10
        ) as rule:
            rule.allow()
        with route(number=20) as rule:
            rule.deny()

    result = gen(routemap, plists, arista(), with_policies=True)
    expected = scrub("""
ip prefix-list LOCAL_NETS
  seq 10 permit 192.168.0.0/16 ge 16 le 32
ip prefix-list LOCAL_NETS_16_24
  seq 10 permit 192.168.0.0/16 ge 16 le 24
route-map IMPORT_CONNECTED permit 10
  match source-protocol connected
  match ip address prefix-list LOCAL_NETS
  set community community-list ADVERTISE
route-map IMPORT_CONNECTED deny 20
route-map ROUTERS_IMPORT permit 10
  match ip address prefix-list LOCAL_NETS_16_24
  match community ADVERTISE
route-map ROUTERS_IMPORT deny 20
route-map ROUTERS_EXPORT permit 10
  match community ADVERTISE
route-map ROUTERS_EXPORT deny 20
""")
    assert result == expected


def gen(routemaps: RouteMap, plists: list[IpPrefixList], dev: MockDevice, with_policies: bool = False) -> str:
    class TestPrefixListFilterGenerator(PrefixListFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
            return plists

    class TestPolicyGenerator(RoutingPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return plists

        def get_community_lists(self, _: Any) -> list:
            return []

        def get_as_path_filters(self, _: Any) -> list:
            return []

        def get_rd_filters(self, _: Any) -> list:
            return []

    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return plists

        def get_community_lists(self, _: Any) -> list:
            return []

        def get_as_path_filters(self, _: Any) -> list:
            return []

    result: list[str] = []
    if dev.hw.soft.startswith("Cumulus"):
        generator = TestCumulusPolicyGenerator()
        genoutput = generator.generate_cumulus_rpl(dev)
        if not with_policies:
            # frr contains both plists and policies
            # leave only prefix-list related commands
            # <ip|ipv6> prefix-list ...
            genoutput = (x for x in genoutput if len(x) > 2)
            genoutput = (x for x in genoutput if x[1] == "prefix-list")
        result = [" ".join(x) for x in genoutput]
        text = "\n".join(result)
    else:
        storage = Mock()
        generator = TestPrefixListFilterGenerator(storage)
        result.append(generator(dev))
        if with_policies:
            # run policies generator too
            generator = TestPolicyGenerator(storage)
            result.append(generator(dev))
        fmtr = registry_connector.get().match(dev.hw).make_formatter()
        tree = parse_to_tree("\n".join(result), fmtr.split)
        text = fmtr.join(tree)
    return scrub(text)
