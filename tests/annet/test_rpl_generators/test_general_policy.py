from collections.abc import Sequence
from unittest.mock import Mock

from annet.rpl import RouteMap, Route, R
from annet.rpl_generators.entities import CommunityList, AsPathFilter, ip_prefix_list
from .helpers import scrub, iosxr, generate, juniper


def test_iosxr_action():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy1(device: Mock, route: Route):
        with route() as rule:
            rule.deny()

    @routemaps
    def policy2(device: Mock, route: Route):
        with route() as rule:
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy policy1
  drop
route-policy policy2
  done
""")
    assert result == expected


def test_iosxr_conditions():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy1(device: Mock, route: Route):
        with route(R.protocol == "bgp") as rule:
            rule.allow()
        with route(R.protocol == "bgp", R.as_path_length >= 1) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy policy1
  if protocol is bgp then
    done
  if protocol is bgp and as-path length ge 1 then
    done
""")
    assert result == expected


def test_iosxr_match_as_path_length():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy1(device: Mock, route: Route):
        with route(R.as_path_length >= 1) as rule:
            rule.allow()
        with route(R.as_path_length <= 10) as rule:
            rule.allow()
        with route(R.as_path_length == 2) as rule:
            rule.allow()
        with route(R.as_path_length <= 10, R.as_path_length >= 1) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy policy1
  if as-path length ge 1 then
    done
  if as-path length le 10 then
    done
  if as-path length eq 2 then
    done
  if as-path length ge 1 and as-path length le 10 then
    done
""")
    assert result == expected


def test_iosxr_match_local_pref_length():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy1(device: Mock, route: Route):
        with route(R.local_pref >= 1) as rule:
            rule.allow()
        with route(R.local_pref <= 10) as rule:
            rule.allow()
        with route(R.local_pref == 2) as rule:
            rule.allow()
        with route(R.local_pref <= 10, R.local_pref >= 1) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy policy1
  if local-preference ge 1 then
    done
  if local-preference le 10 then
    done
  if local-preference eq 2 then
    done
  if local-preference ge 1 and local-preference le 10 then
    done
""")
    assert result == expected


def test_iosxr_then():
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy1(device: Mock, route: Route):
        with route(R.as_path_length==1) as rule:
            rule.set_metric(1)
        with route(R.as_path_length==2) as rule:
            rule.add_metric(2)
        with route(R.as_path_length==3) as rule:
            rule.set_tag(100)
        with route(R.as_path_length==4) as rule:
            rule.next_hop.discard()
        with route(R.as_path_length==5) as rule:
            rule.next_hop.self()
        with route(R.as_path_length==6) as rule:
            rule.next_hop.peer()
        with route(R.as_path_length==7) as rule:
            rule.next_hop.ipv4_addr("192.168.1.1")
        with route(R.as_path_length==8) as rule:
            rule.next_hop.ipv6_addr("FE80::1")
        with route(R.as_path_length==9) as rule:
            rule.next_hop.mapped_ipv4("192.168.1.1")
        with route(R.as_path_length==10) as rule:
            rule.set_metric_type("type-1")
        with route(R.as_path_length==11) as rule:
            rule.set_origin("egp")
        with route(R.as_path_length==12) as rule:
            rule.set_local_pref(42)


    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy policy1
  if as-path length eq 1 then
    set med 1
    pass
  if as-path length eq 2 then
    set med +2
    pass
  if as-path length eq 3 then
    set tag 100
    pass
  if as-path length eq 4 then
    set next-hop discard
    pass
  if as-path length eq 5 then
    set next-hop self
    pass
  if as-path length eq 6 then
    pass
  if as-path length eq 7 then
    set next-hop 192.168.1.1
    pass
  if as-path length eq 8 then
    set next-hop fe80::1
    pass
  if as-path length eq 9 then
    set next-hop ::ffff:192.168.1.1
    pass
  if as-path length eq 10 then
    set metric-type type-1
    pass
  if as-path length eq 11 then
    set origin egp
    pass
  if as-path length eq 12 then
    set local-preference 42
    pass
""")
    assert result == expected



def test_juniper_inline():
    # juniper inlines "from" for *SOME* match fields or if there is only one
    # and "then" when there is no attribute modifications and only result:
    #
    # term DENY {
    #     from {
    #         community DENY;         term DENY {
    #     }                     ==>       from community DENY;
    #     then {                          then reject;
    #         reject;                 }
    #     }
    # }
    routemaps = RouteMap[Mock]()
    community_lists = [
        CommunityList("CMNT_LIST01", ["65000:1234"]),
    ]
    as_path_filters = [
        AsPathFilter("AS_PATH_FILTER01", ["1299"])
    ]
    prefix_lists = [
        ip_prefix_list("PFX_LIST01", ["10.0.0.0/8"])
    ]
    @routemaps
    def policy01(device: Mock, route: Route):
        # then accept
        with route() as rule:
            rule.allow()
        # from community CMNT_LIST01
        with route(R.community.has("CMNT_LIST01")) as rule:
            rule.allow()
        # from as-path AS_PATH_FILTER01
        with route(R.as_path_filter("AS_PATH_FILTER01")) as rule:
            rule.allow()
        # from {
        #    prefix-list PFX_LIST01;
        # }
        with route(R.match_v4("PFX_LIST01")) as rule:
            rule.allow()
        # from {
        #    as-path-calc-length 1;
        # }
        with route(R.as_path_length == 1) as rule:
            rule.allow()

    result = generate(
        routemaps=routemaps,
        dev=juniper(),
        community_lists=community_lists,
        as_path_filters=as_path_filters,
        prefix_lists=prefix_lists,
    )
    expected = scrub("""
policy-options {
    prefix-list PFX_LIST01 {
        10.0.0.0/8;
    }
    as-path AS_PATH_FILTER01 1299;
    community CMNT_LIST01 members 65000:1234;
    policy-statement policy01 {
        term policy01_0 {
            then accept;
        }
        term policy01_1 {
            from community CMNT_LIST01;
            then accept;
        }
        term policy01_2 {
            from as-path AS_PATH_FILTER01;
            then accept;
        }
        term policy01_3 {
            from {
                prefix-list PFX_LIST01;
            }
            then accept;
        }
        term policy01_4 {
            from {
                as-path-calc-length 1 equal;
            }
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_term_numbers():
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        # term policy_10
        with route(number=10) as rule:
            rule.allow()
        # term policy_11
        with route() as rule:
            rule.allow()
        # term policy_20
        with route(number=20) as rule:
            rule.allow()
        # term policy_21
        with route() as rule:
            rule.allow()

    result = generate(
        routemaps=routemaps,
        dev=juniper(),
    )
    expected = scrub("""
policy-options {
    policy-statement policy {
        term policy_10 {
            then accept;
        }
        term policy_11 {
            then accept;
        }
        term policy_20 {
            then accept;
        }
        term policy_21 {
            then accept;
        }
    }
}
""")
    assert result == expected


def test_juniper_term_number_and_name():
    routemaps = RouteMap[Mock]()
    @routemaps
    def policy(device: Mock, route: Route):
        # term policy_0
        with route() as rule:
            rule.allow()
        # term ALLOW
        with route(name="ALLOW", number=10) as rule:
            rule.allow()
        # term policy_11
        with route() as rule:
            rule.allow()

    result = generate(
        routemaps=routemaps,
        dev=juniper(),
    )
    expected = scrub("""
policy-options {
    policy-statement policy {
        term policy_0 {
            then accept;
        }
        term ALLOW {
            then accept;
        }
        term policy_11 {
            then accept;
        }
    }
}
""")
    assert result == expected
