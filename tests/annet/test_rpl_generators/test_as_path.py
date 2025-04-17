from typing import Any, Sequence
from unittest.mock import Mock

from annet.annlib.tabparser import parse_to_tree
from annet.rpl import R, RouteMap, Route, RoutingPolicy
from annet.rpl_generators import (
    IpPrefixList, CumulusPolicyGenerator, RoutingPolicyGenerator, RDFilter, CommunityList, AsPathFilterGenerator,
    AsPathFilter
)
from annet.tabparser import make_formatter
from .helpers import scrub, cumulus, iosxr
from .. import MockDevice


def gen(routemaps: RouteMap, as_path_filters: list[AsPathFilter], dev: MockDevice) -> str:
    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return []

        def get_community_lists(self, _: Any) -> list:
            return []

        def get_as_path_filters(self, _: Any) -> list:
            return as_path_filters

    class BlackboxAsPathGenerator(AsPathFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_as_path_filters(self, device: Any) -> Sequence[AsPathFilter]:
            return as_path_filters

    class BlackBoxPolicyGenerator(RoutingPolicyGenerator):
        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return []

        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_community_lists(self, device: Any) -> list[CommunityList]:
            return []

        def get_rd_filters(self, device: Any) -> list[RDFilter]:
            return []

    if dev.hw.soft.startswith("Cumulus"):
        generator = TestCumulusPolicyGenerator()
        genoutput = generator.generate_cumulus_rpl(dev)
        result = [" ".join(x) for x in genoutput]
        text = "\n".join(result)
    else:
        result: list[str] = []
        storage = Mock()
        generator = BlackboxAsPathGenerator(storage)
        result.append(generator(dev))
        generator = BlackBoxPolicyGenerator(storage)
        result.append(generator(dev))
        fmtr = make_formatter(dev.hw)
        tree = parse_to_tree("\n".join(result), fmtr.split)
        text = fmtr.join(tree)
    return scrub(text)


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

    result = gen(routemaps, [], cumulus())
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

    result = gen(routemaps, aspath_filters, iosxr())
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

    @routemaps
    def policy(device: Mock, route: Route):
        with route(name="n20", number=20) as rule:
            rule.as_path.prepend("65432")

    result = gen(routemaps, [], iosxr())
    expected = scrub("""
route-policy policy
  prepend as-path 65432
  pass
""")
    assert result == expected