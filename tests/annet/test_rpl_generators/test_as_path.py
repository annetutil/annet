from typing import Any
from unittest.mock import Mock

from annet.rpl import R, RouteMap, Route, RoutingPolicy
from annet.rpl_generators import (
    IpPrefixList, CumulusPolicyGenerator
)
from .helpers import scrub, cumulus
from .. import MockDevice


def gen(routemaps: RouteMap, dev: MockDevice) -> str:
    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return []

        def get_community_lists(self, _: Any) -> list:
            return []

        def get_as_path_filters(self, _: Any) -> list:
            return []

    if dev.hw.soft.startswith("Cumulus"):
        generator = TestCumulusPolicyGenerator()
        genoutput = generator.generate_cumulus_rpl(dev)
        result = [" ".join(x) for x in genoutput]
        text = "\n".join(result)
    else:
        raise ValueError("Unsupported device")
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

    result = gen(routemaps, cumulus())
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
