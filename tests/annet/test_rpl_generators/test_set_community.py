from typing import Any
from unittest.mock import Mock
from annet.vendors.tabparser import parse_to_tree
from annet.rpl_generators import (
    IpPrefixList, CumulusPolicyGenerator, RoutingPolicyGenerator, CommunityList, CommunityType
)
from annet.rpl import RouteMap, Route, RoutingPolicy
from annet.vendors import registry_connector
from .. import MockDevice
from .helpers import scrub, huawei, arista, cumulus


def gen(routemaps: RouteMap, clists: list[CommunityList], dev: MockDevice) -> str:
    class TestPolicyGenerator(RoutingPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return []

        def get_community_lists(self, _: Any) -> list:
            return clists

        def get_as_path_filters(self, _: Any) -> list:
            return []

        def get_rd_filters(self, _: Any) -> list:
            return []

    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return []

        def get_community_lists(self, _: Any) -> list:
            return clists

        def get_as_path_filters(self, _: Any) -> list:
            return []

    result: list[str] = []
    if dev.hw.soft.startswith("Cumulus"):
        generator = TestCumulusPolicyGenerator()
        genoutput = generator.generate_cumulus_rpl(dev)
        result = [" ".join(x) for x in genoutput]
        text = "\n".join(result)
    else:
        storage = Mock()
        generator = TestPolicyGenerator(storage)
        result.append(generator(dev))
        fmtr = registry_connector.get().match(dev.hw).make_formatter()
        tree = parse_to_tree("\n".join(result), fmtr.split)
        text = fmtr.join(tree)
    return scrub(text)


RT_CLIST = "RT1"
SOO_CLIST = "SOO2"
CLISTS = [
    CommunityList(RT_CLIST, ["100:2"], type=CommunityType.RT),
    CommunityList(SOO_CLIST, ["100:3", "100:4"], type=CommunityType.SOO),
]


def test_huawei_set_comm_ext():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(number=1) as rule:
            rule.extcommunity.set(RT_CLIST)
            rule.allow()
        with route(number=2) as rule:
            rule.extcommunity.add(RT_CLIST, SOO_CLIST)
            rule.allow()

    result = gen(routemaps, CLISTS, huawei())
    expected = scrub("""
route-policy policy permit node 1
  apply extcommunity rt 100:2
route-policy policy permit node 2
  apply extcommunity rt 100:2 additive
  apply extcommunity soo 100:3 100:4 additive
""")
    assert result == expected


def test_arista_set_comm_ext():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(number=0) as rule:
            rule.extcommunity.set()
            rule.allow()
        with route(number=1) as rule:
            rule.extcommunity.set(RT_CLIST)
            rule.allow()
        with route(number=2) as rule:
            rule.extcommunity.add(RT_CLIST, SOO_CLIST)
            rule.allow()
        with route(number=3) as rule:
            rule.extcommunity.remove(RT_CLIST, SOO_CLIST)
            rule.allow()

    result = gen(routemaps, CLISTS, arista())
    expected = scrub("""
route-map policy permit 0
  set extcommunity none
route-map policy permit 1
  set extcommunity rt 100:2
route-map policy permit 2
  set extcommunity rt 100:2 soo 100:3 soo 100:4 additive
route-map policy permit 3
  set extcommunity rt 100:2 soo 100:3 soo 100:4 delete
""")
    assert result == expected


def test_cumulus_set_comm_ext():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(number=0) as rule:
            rule.extcommunity.set()
            rule.allow()
        with route(number=1) as rule:
            rule.extcommunity.set(RT_CLIST, SOO_CLIST)
            rule.allow()

    result = gen(routemaps, CLISTS, cumulus())
    expected = scrub("""
!
route-map policy permit 0
  set extcommunity none
!
route-map policy permit 1
  set extcommunity rt 100:2
  set extcommunity soo 100:3 100:4
!
""")
    assert result == expected
