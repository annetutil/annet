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
  if protocol is bgp and local-preference ge 1 then
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
