from collections.abc import Sequence
from unittest.mock import Mock

from annet.rpl import RouteMap, Route, R
from .helpers import scrub, iosxr, generate


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