from unittest.mock import Mock

import pytest

from annet.rpl import R, Route, RouteMap

from .helpers import arista, cumulus, generate, huawei, iosxr, juniper, scrub


def test_iosxr_vendor_knob():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.tag == 100) as rule:
            rule.set_vendor_knob(iosxr="fallback-vrf-lookup")
            rule.allow()

    result = generate(routemaps=routemaps, dev=iosxr())
    expected = scrub("""
route-policy p
  if tag is 100 then
    set fallback-vrf-lookup
    done
""")
    assert result == expected


def test_juniper_vendor_knob():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(R.tag == 100) as rule:
            rule.set_vendor_knob(juniper="analyze")
            rule.allow()

    result = generate(routemaps=routemaps, dev=juniper())
    expected = scrub("""
policy-options {
    policy-statement p {
        term p_0 {
            from tag 100;
            then {
                analyze;
                accept;
            }
        }
    }
}
""")
    assert result == expected


def test_huawei_vendor_knob():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(number=10) as rule:
            rule.set_vendor_knob(huawei="some-knob 1")
            rule.allow()

    result = generate(routemaps=routemaps, dev=huawei())
    expected = scrub("""
route-policy p permit node 10
  apply some-knob 1
""")
    assert result == expected


def test_arista_vendor_knob():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(number=10) as rule:
            rule.set_vendor_knob(arista="some-knob 1")
            rule.allow()

    result = generate(routemaps=routemaps, dev=arista())
    expected = scrub("""
route-map p permit 10
  set some-knob 1
""")
    assert result == expected


def test_cumulus_vendor_knob():
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(number=10) as rule:
            rule.set_vendor_knob(cumulus="some-knob 1")
            rule.allow()

    result = generate(routemaps=routemaps, dev=cumulus())
    expected = scrub("""
!
route-map p permit 10
  set some-knob 1
!
""")
    assert result == expected


@pytest.mark.parametrize("device", [huawei, arista, iosxr, cumulus])
def test_vendor_knob_for_other_vendor(device):
    routemaps = RouteMap[Mock]()

    @routemaps
    def p(device: Mock, route: Route):
        with route(number=10) as rule:
            rule.set_vendor_knob(juniper="analyze")
            rule.allow()

    with pytest.raises(NotImplementedError):
        generate(routemaps=routemaps, dev=device())
