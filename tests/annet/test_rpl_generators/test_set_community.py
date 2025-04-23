from unittest.mock import Mock
from annet.rpl_generators import CommunityList, CommunityType
from annet.rpl import R, RouteMap, Route

from .helpers import scrub, huawei, arista, cumulus, generate


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

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=huawei())
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

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=arista())
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

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=cumulus())
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
