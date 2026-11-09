from unittest.mock import Mock

import pytest

from annet.rpl import R, Route, RouteMap

from .helpers import arista, cumulus, generate, huawei, iosxr, juniper, scrub


def test_iosxr_tag():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.protocol == "isis", R.tag == 100) as rule:
            rule.allow()
        with route(R.tag.has_any(7)) as rule:
            rule.allow()
        with route(R.tag.has_any(64514, 64522)) as rule:
            rule.allow()
        with route() as rule:
            rule.set_tag(5)
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy p
  if protocol is isis and tag is 100 then
    done
  if tag is 7 then
    done
  if tag in (64514, 64522) then
    done
  set tag 5
  done
""")
    assert result == expected


def test_juniper_tag():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.protocol == "isis", R.tag == 100) as rule:
            rule.allow()
        with route(R.tag.has_any(7)) as rule:
            rule.allow()
        with route(R.tag.has_any(64514, 64522)) as rule:
            rule.allow()
        with route() as rule:
            rule.set_tag(5)
            rule.allow()

    result = generate(routemaps=routemaps, dev=juniper())
    expected = scrub("""
policy-options {
    policy-statement p {
        term p_0 {
            from {
                protocol isis;
                tag 100;
            }
            then accept;
        }
        term p_1 {
            from tag 7;
            then accept;
        }
        term p_2 {
            from tag [ 64514 64522 ];
            then accept;
        }
        term p_3 {
            then {
                tag 5;
                accept;
            }
        }
    }
}
""")
    assert result == expected


def test_huawei_tag():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.protocol == "isis", R.tag == 100, number=10) as rule:
            rule.allow()
        with route(R.tag.has_any(7), number=20) as rule:
            rule.allow()
        with route(number=30) as rule:
            rule.set_tag(5)
            rule.allow()

    result = generate(routemaps=routemaps, dev=huawei())
    expected = scrub("""
route-policy p permit node 10
  if-match protocol isis
  if-match tag 100
route-policy p permit node 20
  if-match tag 7
route-policy p permit node 30
  apply tag 5
""")
    assert result == expected


def test_arista_tag():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.protocol == "isis", R.tag == 100, number=10) as rule:
            rule.allow()
        with route(R.tag.has_any(7), number=20) as rule:
            rule.allow()
        with route(number=30) as rule:
            rule.set_tag(5)
            rule.allow()

    result = generate(routemaps=routemaps, dev=arista())
    expected = scrub("""
route-map p permit 10
  match source-protocol isis
  match tag 100
route-map p permit 20
  match tag 7
route-map p permit 30
  set tag 5
""")
    assert result == expected


def test_cumulus_tag():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.protocol == "isis", R.tag == 100, number=10) as rule:
            rule.allow()
        with route(R.tag.has_any(7), number=20) as rule:
            rule.allow()
        with route(number=30) as rule:
            rule.set_tag(5)
            rule.allow()

    result = generate(routemaps=routemaps, dev=cumulus())
    expected = scrub("""
!
route-map p permit 10
  match source-protocol isis
  match tag 100
!
route-map p permit 20
  match tag 7
!
route-map p permit 30
  set tag 5
!
""")
    assert result == expected


@pytest.mark.parametrize("device", [huawei, arista, cumulus])
def test_tag_has_any_many_unsupported(device):
    # a repeated tag match would silently replace the previous one on these vendors
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.tag.has_any(64514, 64522), number=10) as rule:
            rule.allow()

    with pytest.raises(NotImplementedError):
        generate(routemaps=routemaps, dev=device())


def test_tag_has_any_empty():
    with pytest.raises(ValueError):
        R.tag.has_any()
