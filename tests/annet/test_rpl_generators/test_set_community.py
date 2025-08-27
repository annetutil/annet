from unittest.mock import Mock
from annet.rpl_generators import CommunityList, CommunityType, CommunityLogic
from annet.rpl import R, RouteMap, Route

import pytest

from .helpers import scrub, huawei, arista, cumulus, generate, iosxr, juniper

BASIC_CLIST = "CL1"
BASIC2_CLIST = "CL2"
RT_CLIST = "RT1"
RT2_CLIST = "RT2"
SOO_CLIST = "SOO2"
WILD_CLIST = "WILD"
CLISTS = [
    CommunityList(BASIC_CLIST, ["65000:2"], type=CommunityType.BASIC),
    CommunityList(BASIC2_CLIST, ["65001:2"], type=CommunityType.BASIC, logic=CommunityLogic.AND),
    CommunityList(RT_CLIST, ["100:2"], type=CommunityType.RT),
    CommunityList(RT2_CLIST, ["200:2"], type=CommunityType.RT, logic=CommunityLogic.AND),
    CommunityList(SOO_CLIST, ["100:3", "100:4"], type=CommunityType.SOO),
    CommunityList(WILD_CLIST, ["*:*"], type=CommunityType.BASIC, use_regex=True),
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
ip extcommunity-filter basic RT1 index 10 permit rt 100:2
ip extcommunity-list soo basic SOO2 index 10 permit 100:3
ip extcommunity-list soo basic SOO2 index 20 permit 100:4

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


def test_iosxr_set_comm_ext():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.extcommunity_rt.has_any(RT_CLIST, RT2_CLIST), number=1) as rule:
            rule.extcommunity.set(RT_CLIST, RT2_CLIST)
            rule.allow()
        with route(R.extcommunity_rt.has(RT_CLIST, RT2_CLIST), number=2) as rule:
            rule.extcommunity.set()
            rule.allow()

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=iosxr())
    expected = scrub("""
extcommunity-set rt RT1
  100:2
extcommunity-set rt RT2
  200:2

route-policy policy
  if (extcommunity rt matches-any RT1 or extcommunity rt matches-every RT2) then
    delete extcommunity rt all
    set extcommunity rt RT1 additive
    set extcommunity rt RT2 additive
    done
  if extcommunity rt matches-any RT1 and extcommunity rt matches-every RT2 then
    delete extcommunity rt all
    done
""")
    assert result == expected

def test_iosxr_set_comm():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.community.has_any(BASIC_CLIST, BASIC2_CLIST), number=1) as rule:
            rule.community.set(BASIC_CLIST)
            rule.community.remove(BASIC2_CLIST)
            rule.allow()
        with route(R.community.has(BASIC_CLIST, BASIC2_CLIST), number=2) as rule:
            rule.community.set()
            rule.allow()

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=iosxr())
    expected = scrub("""
community-set CL1
  65000:2
community-set CL2
  65001:2

route-policy policy
  if (community matches-any CL1 or community matches-every CL2) then
    delete community all
    set community CL1 additive
    delete community in CL2
    done
  if community matches-any CL1 and community matches-every CL2 then
    delete community all
    done
""")
    assert result == expected


def test_juniper_comm_match_set():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.community.has_any(BASIC_CLIST, BASIC2_CLIST)) as rule:
            rule.community.remove(BASIC2_CLIST)
            rule.community.add(BASIC_CLIST)
            rule.allow()
        with route(R.community.has(BASIC2_CLIST)) as rule:
            rule.community.remove(BASIC2_CLIST)
            rule.allow()
        with route(R.community.has(RT_CLIST)) as rule:
            rule.community.set(RT2_CLIST)
            rule.allow()

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=juniper())
    expected = scrub("""
policy-options {
    community CL1 members 65000:2;
    community CL2 members 65001:2;
    community RT1 members target:100:2;
    community RT2 members target:200:2;
    policy-statement policy {
        term policy_0 {
            from community [ CL1 CL2 ];
            then {
                community delete CL2;
                community add CL1;
                accept;
            }
        }
        term policy_1 {
            from community CL2;
            then {
                community delete CL2;
                accept;
            }
        }
        term policy_2 {
            from community RT1;
            then {
                community set RT2;
                accept;
            }
        }
    }
}
""")
    assert result == expected


def test_juniper_community_has_multiple():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        # match for all members of multiple community lists is not implemented
        with route(R.community.has(BASIC_CLIST, BASIC2_CLIST)) as rule:
            rule.allow()

    with pytest.raises(NotImplementedError):
        generate(routemaps=routemaps, community_lists=CLISTS, dev=juniper())


def test_juniper_community_empty_set():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        # empty community.set() to delete all is not supported
        # you need to make explicit delete with wildcard or use set(CLIST_NAME)
        with route() as rule:
            rule.community.set()
            rule.allow()

    with pytest.raises(NotImplementedError):
        generate(routemaps=routemaps, community_lists=CLISTS, dev=juniper())

def test_juniper_communities_remove_all():
    routemaps = RouteMap[Mock]()

    @routemaps
    def policy(device: Mock, route: Route):
        with route() as rule:
            rule.community.set(BASIC_CLIST)
            rule.allow()
        with route() as rule:
            rule.community.remove(WILD_CLIST)
            rule.community.add(BASIC_CLIST)
            rule.allow()
        # remove is ignored when there is a set
        with route() as rule:
            rule.community.remove(WILD_CLIST)
            rule.community.set(BASIC2_CLIST)
            rule.community.add(BASIC_CLIST)
            rule.allow()

    result = generate(routemaps=routemaps, community_lists=CLISTS, dev=juniper())
    expected = scrub("""
policy-options {
    community CL1 members 65000:2;
    community CL2 members 65001:2;
    community WILD members *:*;
    policy-statement policy {
        term policy_0 {
            then {
                community set CL1;
                accept;
            }
        }
        term policy_1 {
            then {
                community delete WILD;
                community add CL1;
                accept;
            }
        }
        term policy_2 {
            then {
                community set CL2;
                community add CL1;
                accept;
            }
        }
    }
}
""")
    assert result == expected
