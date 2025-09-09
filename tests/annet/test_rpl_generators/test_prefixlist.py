from ipaddress import IPv4Network
from unittest.mock import Mock
from annet.rpl_generators import ip_prefix_list, IpPrefixList, IpPrefixListMember, CommunityList, CommunityType
from annet.rpl import R, RouteMap, Route

from .helpers import scrub, huawei, arista, cumulus, generate, iosxr, juniper


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


def test_juniper_prefixlist01():
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/16"]),
        ip_prefix_list("IPV4_LIST_2", ["10.21.0.0/16", "10.22.0.0/16"]),
        ip_prefix_list("IPV6_LIST_1", ["2001:db8:11::/64", "2001:db8:12::/64"]),
        ip_prefix_list("IPV6_LIST_2", ["2001:db8:21::/64", "2001:db8:22::/64"]),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST_1", "IPV4_LIST_2")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST_1", "IPV6_LIST_2")) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    prefix-list IPV4_LIST_1 {
        10.11.0.0/16;
        10.12.0.0/16;
    }
    prefix-list IPV4_LIST_2 {
        10.21.0.0/16;
        10.22.0.0/16;
    }
    prefix-list IPV6_LIST_1 {
        2001:db8:11::/64;
        2001:db8:12::/64;
    }
    prefix-list IPV6_LIST_2 {
        2001:db8:21::/64;
        2001:db8:22::/64;
    }
    policy-statement policy {
        term policy_0 {
            from {
                prefix-list IPV4_LIST_1;
                prefix-list IPV4_LIST_2;
            }
            then accept;
        }
        term policy_1 {
            from {
                prefix-list IPV6_LIST_1;
                prefix-list IPV6_LIST_2;
            }
            then accept;
        }
    }
}
""")
    assert result == expected



def test_juniper_prefixlist02():
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/16"]),
        ip_prefix_list("IPV6_LIST_1", ["2001:db8:11::/64", "2001:db8:12::/64"]),
        ip_prefix_list("IPV4_LIST_2", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(None, 32)),
        ip_prefix_list("IPV6_LIST_2", ["2001:db8:11::/64", "2001:db8:12::/96"], or_longer=(None, 128)),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST_1", "IPV4_LIST_2")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST_1", "IPV6_LIST_2")) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    prefix-list IPV4_LIST_1 {
        10.11.0.0/16;
        10.12.0.0/16;
    }
    prefix-list IPV4_LIST_2 {
        10.11.0.0/16;
        10.12.0.0/24;
    }
    prefix-list IPV6_LIST_1 {
        2001:db8:11::/64;
        2001:db8:12::/64;
    }
    prefix-list IPV6_LIST_2 {
        2001:db8:11::/64;
        2001:db8:12::/96;
    }
    policy-statement policy {
        term policy_0 {
            from {
                prefix-list IPV4_LIST_1;
                prefix-list-filter IPV4_LIST_2 orlonger;
            }
            then accept;
        }
        term policy_1 {
            from {
                prefix-list IPV6_LIST_1;
                prefix-list-filter IPV6_LIST_2 orlonger;
            }
            then accept;
        }
    }
}
""")
    assert result == expected



def test_juniper_prefixlist03():
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/16"]),
        ip_prefix_list("IPV6_LIST_1", ["2001:db8:11::/64", "2001:db8:12::/64"]),
        ip_prefix_list("IPV4_LIST_2", ["10.11.0.0/16", "10.12.0.0/16"], or_longer=(24, 32)),
        ip_prefix_list("IPV6_LIST_2", ["2001:db8:11::/64", "2001:db8:12::/64"], or_longer=(96, 128)),
    ]
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4("IPV4_LIST_1", "IPV4_LIST_2")) as rule:
            rule.allow()
        with route(R.match_v6("IPV6_LIST_1", "IPV6_LIST_2")) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    prefix-list IPV4_LIST_1 {
        10.11.0.0/16;
        10.12.0.0/16;
    }
    route-filter-list IPV4_LIST_2 {
        10.11.0.0/16 prefix-length-range /24-/32;
        10.12.0.0/16 prefix-length-range /24-/32;
    }
    prefix-list IPV6_LIST_1 {
        2001:db8:11::/64;
        2001:db8:12::/64;
    }
    route-filter-list IPV6_LIST_2 {
        2001:db8:11::/64 prefix-length-range /96-/128;
        2001:db8:12::/64 prefix-length-range /96-/128;
    }
    policy-statement policy {
        term policy_0 {
            from {
                prefix-list IPV4_LIST_1;
                route-filter-list IPV4_LIST_2;
            }
            then accept;
        }
        term policy_1 {
            from {
                prefix-list IPV6_LIST_1;
                route-filter-list IPV6_LIST_2;
            }
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_prefixlist04():
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/16"], or_longer=(16, 32)),
        ip_prefix_list("IPV4_LIST_2", ["10.21.0.0/16", "10.22.0.0/16"], or_longer=(None, 32)),
        ip_prefix_list("IPV4_LIST_3", ["10.31.0.0/16", "10.32.0.0/16"], or_longer=(16, None)),
    ]
    plist_names = [x.name for x in plists]

    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4(*plist_names)) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    prefix-list IPV4_LIST_1 {
        10.11.0.0/16;
        10.12.0.0/16;
    }
    prefix-list IPV4_LIST_2 {
        10.21.0.0/16;
        10.22.0.0/16;
    }
    prefix-list IPV4_LIST_3 {
        10.31.0.0/16;
        10.32.0.0/16;
    }
    policy-statement policy {
        term policy_0 {
            from {
                prefix-list-filter IPV4_LIST_1 orlonger;
                prefix-list-filter IPV4_LIST_2 orlonger;
                prefix-list-filter IPV4_LIST_3 orlonger;
            }
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_prefixlist05():
    # some of are valid syntaxically but not logically
    # see comment in _juniper_router_filter_list
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(24, None)),
        ip_prefix_list("IPV4_LIST_2", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(None, 24)),
        ip_prefix_list("IPV4_LIST_3", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(25, 30)),
    ]
    plist_names = [x.name for x in plists]

    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4(*plist_names)) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    route-filter-list IPV4_LIST_1 {
        10.11.0.0/16 prefix-length-range /24-/32;
        10.12.0.0/24 prefix-length-range /24-/32;
    }
    route-filter-list IPV4_LIST_2 {
        10.11.0.0/16 prefix-length-range /16-/24;
        10.12.0.0/24 prefix-length-range /24-/24;
    }
    route-filter-list IPV4_LIST_3 {
        10.11.0.0/16 prefix-length-range /25-/30;
        10.12.0.0/24 prefix-length-range /25-/30;
    }
    policy-statement policy {
        term policy_0 {
            from {
                route-filter-list IPV4_LIST_1;
                route-filter-list IPV4_LIST_2;
                route-filter-list IPV4_LIST_3;
            }
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_prefixlist06():
    # are valid syntaxically but not logically
    # kept that way to conform with other vendor generator behaviour
    # see comment in _juniper_router_filter_list
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(32, 16)),
        ip_prefix_list("IPV4_LIST_2", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(None, 16)),
        ip_prefix_list("IPV4_LIST_3", ["10.11.0.0/16", "10.12.0.0/24"], or_longer=(16, None)),
    ]
    plist_names = [x.name for x in plists]

    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4(*plist_names)) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    route-filter-list IPV4_LIST_1 {
        10.11.0.0/16 prefix-length-range /32-/16;
        10.12.0.0/24 prefix-length-range /32-/16;
    }
    route-filter-list IPV4_LIST_2 {
        10.11.0.0/16 prefix-length-range /16-/16;
        10.12.0.0/24 prefix-length-range /24-/16;
    }
    route-filter-list IPV4_LIST_3 {
        10.11.0.0/16 prefix-length-range /16-/32;
        10.12.0.0/24 prefix-length-range /16-/32;
    }
    policy-statement policy {
        term policy_0 {
            from {
                route-filter-list IPV4_LIST_1;
                route-filter-list IPV4_LIST_2;
                route-filter-list IPV4_LIST_3;
            }
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_prefixlist07():
    plists = [
        ip_prefix_list("IPV4_LIST_1", ["10.11.0.0/16", "10.12.0.0/16"]),
        ip_prefix_list("IPV4_LIST_2", ["10.21.0.0/16", "10.22.0.0/16"], or_longer=(None, 32)),
        ip_prefix_list("IPV4_LIST_3", ["10.31.0.0/16", "10.32.0.0/16"], or_longer=(17, 32)),
    ]
    plist_names = [x.name for x in plists]

    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.match_v4(*plist_names)) as rule:
            rule.allow()
        with route(R.match_v4(*plist_names, or_longer=True)) as rule:
            rule.allow()
        with route(R.match_v4(*plist_names, or_longer=(17, 24))) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, prefix_lists=plists, dev=juniper())
    expected = scrub("""
policy-options {
    prefix-list IPV4_LIST_1 {
        10.11.0.0/16;
        10.12.0.0/16;
    }
    prefix-list IPV4_LIST_2 {
        10.21.0.0/16;
        10.22.0.0/16;
    }
    route-filter-list IPV4_LIST_3 {
        10.31.0.0/16 prefix-length-range /17-/32;
        10.32.0.0/16 prefix-length-range /17-/32;
    }
    route-filter-list IPV4_LIST_1_17_24 {
        10.11.0.0/16 prefix-length-range /17-/24;
        10.12.0.0/16 prefix-length-range /17-/24;
    }
    route-filter-list IPV4_LIST_2_17_24 {
        10.21.0.0/16 prefix-length-range /17-/24;
        10.22.0.0/16 prefix-length-range /17-/24;
    }
    route-filter-list IPV4_LIST_3_17_24 {
        10.31.0.0/16 prefix-length-range /17-/24;
        10.32.0.0/16 prefix-length-range /17-/24;
    }
    policy-statement policy {
        term policy_0 {
            from {
                prefix-list IPV4_LIST_1;
                prefix-list-filter IPV4_LIST_2 orlonger;
                route-filter-list IPV4_LIST_3;
            }
            then accept;
        }
        term policy_1 {
            from {
                prefix-list-filter IPV4_LIST_1 orlonger;
                prefix-list-filter IPV4_LIST_2 orlonger;
                route-filter-list IPV4_LIST_3;
            }
            then accept;
        }
        term policy_2 {
            from {
                route-filter-list IPV4_LIST_1_17_24;
                route-filter-list IPV4_LIST_2_17_24;
                route-filter-list IPV4_LIST_3_17_24;
            }
            then accept;
        }
    }
}
""")
    assert result == expected
