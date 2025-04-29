from ipaddress import IPv4Network
from unittest.mock import Mock
from annet.rpl_generators import ip_prefix_list, IpPrefixList, IpPrefixListMember, CommunityList, CommunityType
from annet.rpl import R, RouteMap, Route

from .helpers import scrub, huawei, arista, cumulus, generate, iosxr


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
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64

route-policy policy permit node 1
  if-match ip-prefix IPV4_LIST
route-policy policy permit node 2
  if-match ipv6 address prefix-list IPV6_LIST
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
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists,  dev=arista())
    expected = scrub("""
ip prefix-list IPV4_LIST
  seq 10 permit 10.0.0.0/8
ipv6 prefix-list IPV6_LIST
  seq 10 permit 2001:db8:1234::/64
route-map policy permit 1
  match ip address prefix-list IPV4_LIST
route-map policy permit 2
  match ipv6 address prefix-list IPV6_LIST
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

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=cumulus())
    expected = scrub("""
ip prefix-list IPV4_LIST seq 5 permit 10.0.0.0/8
ipv6 prefix-list IPV6_LIST seq 5 permit 2001:db8:1234::/64
!
route-map policy permit 10
  match ip address prefix-list IPV4_LIST
!
route-map policy permit 20
  match ipv6 address prefix-list IPV6_LIST
!
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
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32)), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128)), number=2) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST_8_32 index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST_64_128 index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
route-policy policy permit node 1
  if-match ip-prefix IPV4_LIST_8_32
route-policy policy permit node 2
  if-match ipv6 address prefix-list IPV6_LIST_64_128
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
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32)), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128)), number=2) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=arista())
    expected = scrub("""
ip prefix-list IPV4_LIST_8_32
  seq 10 permit 10.0.0.0/8 ge 8 le 32
ipv6 prefix-list IPV6_LIST_64_128
  seq 10 permit 2001:db8:1234::/64 ge 64 le 128
route-map policy permit 1
  match ip address prefix-list IPV4_LIST_8_32
route-map policy permit 2
  match ipv6 address prefix-list IPV6_LIST_64_128
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

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=cumulus())
    expected = scrub("""
ip prefix-list IPV4_LIST_8_32 seq 5 permit 10.0.0.0/8 ge 8 le 32
ipv6 prefix-list IPV6_LIST_64_128 seq 5 permit 2001:db8:1234::/64 ge 64 le 128
!
route-map policy permit 10
  match ip address prefix-list IPV4_LIST_8_32
!
route-map policy permit 20
  match ipv6 address prefix-list IPV6_LIST_64_128
!
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
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32)), number=3) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128)), number=4) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64
ip ip-prefix IPV4_LIST_8_32 index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST_64_128 index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
route-policy policy permit node 1
  if-match ip-prefix IPV4_LIST
route-policy policy permit node 2
  if-match ipv6 address prefix-list IPV6_LIST
route-policy policy permit node 3
  if-match ip-prefix IPV4_LIST_8_32
route-policy policy permit node 4
  if-match ipv6 address prefix-list IPV6_LIST_64_128
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
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()


    result = generate(routemaps=routemaps, prefix_lists=plists, dev=huawei())
    expected = scrub("""
ip ip-prefix IPV4_LIST index 5 permit 10.0.0.0 8 greater-equal 8 less-equal 32
ip ipv6-prefix IPV6_LIST index 5 permit 2001:DB8:1234:: 64 greater-equal 64 less-equal 128
route-policy policy permit node 1
  if-match ip-prefix IPV4_LIST
route-policy policy permit node 2
  if-match ipv6 address prefix-list IPV6_LIST
""")
    assert result == expected


def test_iosxr_prefixlist_with_match_both():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"]),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()
        with route(R.match_v4("IPV4_LIST", or_longer=(8, 32)), number=3) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST", or_longer=(64, 128)), number=4) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=iosxr())
    expected = scrub("""
prefix-set IPV4_LIST
  10.0.0.0/8
prefix-set IPV6_LIST
  2001:db8:1234::/64
prefix-set IPV4_LIST_8_32
  10.0.0.0/8 ge 8 le 32
prefix-set IPV6_LIST_64_128
  2001:db8:1234::/64 ge 64 le 128
route-policy policy
  if destination in IPV4_LIST then
    done
  if destination in IPV6_LIST then
    done
  if destination in IPV4_LIST_8_32 then
    done
  if destination in IPV6_LIST_64_128 then
    done
""")
    assert result == expected



def test_iosxr_prefixlist_embedded_orlonger():
    plists = [
        ip_prefix_list("IPV4_LIST", ["10.0.0.0/8"], (8, 32)),
        ip_prefix_list("IPV6_LIST", ["2001:db8:1234::/64"], (64, 128)),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST"), number=1) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST"), number=2) as rule:
            rule.allow()


    result = generate(routemaps=routemaps, prefix_lists=plists, dev=iosxr())
    expected = scrub("""
prefix-set IPV4_LIST
  10.0.0.0/8 ge 8 le 32
prefix-set IPV6_LIST
  2001:db8:1234::/64 ge 64 le 128
route-policy policy
  if destination in IPV4_LIST then
    done
  if destination in IPV6_LIST then
    done
""")
    assert result == expected


def test_arista_tutorial():
    plists = [
        ip_prefix_list("LOCAL_NETS", ["192.168.0.0/16"], (16, 32)),
    ]
    communities = [
        CommunityList("ADVERTISE", type=CommunityType.BASIC, members=["65001:0"])
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

    result = generate(routemaps=routemap, prefix_lists=plists, community_lists=communities, dev=arista())
    expected = scrub("""
ip prefix-list LOCAL_NETS
  seq 10 permit 192.168.0.0/16 ge 16 le 32
ip prefix-list LOCAL_NETS_16_24
  seq 10 permit 192.168.0.0/16 ge 16 le 24
ip community-list ADVERTISE permit 65001:0
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
