from unittest.mock import Mock

from annet.rpl import R, RouteMap, Route
from annet.rpl_generators import (
    AsPathFilter
)
from .helpers import scrub, cumulus, iosxr, arista, generate


def test_cumulus_as_path_set():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(name="n10", number=10) as rule:
            rule.as_path.set("65431")
        with route(name="n20", number=20) as rule:
            rule.as_path.prepend("65432")
        with route(name="n30", number=30) as rule:
            rule.as_path.delete("65433")
        with route(name="n40", number=40) as rule:
            rule.as_path.expand_last_as("65434")

    result = generate(routemaps=routemaps, dev=cumulus())
    expected = scrub("""
!
route-map policy permit 10
  set as-path exclude all
  set as-path prepend 65431
  on-match next
!
route-map policy permit 20
  set as-path prepend 65432
  on-match next
!
route-map policy permit 30
  set as-path exclude 65433
  on-match next
!
route-map policy permit 40
  set as-path prepend last-as 65434
  on-match next
!
""")
    assert result == expected


def test_iosxr_as_path_fitlers():
    routemaps = RouteMap[Mock]()
    aspath_filters = [
        AsPathFilter("asf1", ["123", "456"]),
        AsPathFilter("asf2", ["123"]),
        AsPathFilter("asf3", ["111"]),
    ]

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.as_path_filter("asf1"), name="n10", number=10) as rule:
            rule.allow()
        with route(R.as_path_filter("asf2"), name="n20", number=20) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, as_path_filters=aspath_filters, dev=iosxr())
    expected = scrub("""
as-path-set asf1
  ios-regex '123',
  ios-regex '456'
as-path-set asf2
  ios-regex '123'
route-policy policy
  if as-path in asf1 then
    done
  if as-path in asf2 then
    done
""")
    assert result == expected

def test_iosxr_as_path_change():
    routemaps = RouteMap[Mock]()

    aspath_filters = [
        AsPathFilter("asf1", ["123", "456"]),
    ]

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.as_path_filter("asf1"), name="n20", number=20) as rule:
            rule.as_path.prepend("65432")
            rule.allow()

    result = generate(routemaps=routemaps, as_path_filters=aspath_filters, dev=iosxr())
    expected = scrub("""
as-path-set asf1
  ios-regex '123',
  ios-regex '456'

route-policy policy
  if as-path in asf1 then
    prepend as-path 65432
    done
""")
    assert result == expected


def test_arista_as_path_change():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(number=10) as rule:
            rule.as_path.set("65431")
            rule.allow()
        with route(number=20) as rule:
            rule.as_path.prepend("65432")
            rule.allow()
        with route(number=30) as rule:
            rule.as_path.prepend("65435", "65435", "65435")
            rule.allow()
        with route(number=40) as rule:
            rule.as_path.expand_last_as("3")
            rule.allow()
        with route(number=50) as rule:
            rule.as_path.prepend("65435", "65435", "65435")
            rule.as_path.expand_last_as("3")
            rule.allow()

    result = generate(routemaps=routemaps, dev=arista())
    expected = scrub("""
route-map policy permit 10
  set as-path match all replacement 65431
route-map policy permit 20
  set as-path prepend 65432
route-map policy permit 30
  set as-path prepend 65435 65435 65435
route-map policy permit 40
  set as-path prepend last-as 3
route-map policy permit 50
  set as-path prepend 65435 65435 65435
  set as-path prepend last-as 3
""")
    assert result == expected