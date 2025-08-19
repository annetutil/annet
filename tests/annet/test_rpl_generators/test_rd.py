from unittest.mock import Mock

import pytest

from annet.rpl import R, RouteMap, Route
from annet.rpl_generators import RDFilter
from .helpers import scrub, iosxr, generate, juniper


def test_iosxr_rd_match():
    routemaps = RouteMap[Mock]()

    rd_filters = [
        RDFilter("rd1", 1, ["172.16.0.0/16:*", "172.16.0.0/16:100"]),
        RDFilter("rd2", 2, ["192:*", "192:100"]),
    ]

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.rd.has("rd1", "rd2"), name="n20", number=20) as rule:
            rule.allow()
        with route(R.rd.has_any("rd1", "rd2"), name="n20", number=20) as rule:
            rule.allow()

    result = generate(routemaps=routemaps, rd_filters=rd_filters, dev=iosxr())
    expected = scrub("""
rd-set rd1
  172.16.0.0/16:*,
  172.16.0.0/16:100
rd-set rd2
  192:*,
  192:100

route-policy policy
  if rd in rd1 and rd in rd2 then
    done
  if (rd in rd1 or rd in rd2) then
    done

""")
    assert result == expected


def test_juniper_rd_match():
    routemaps = RouteMap[Mock]()

    rd_filters = [
        RDFilter("rd1", 1, ["172.16.0.0:*", "172.17.0.0:*"]),
        RDFilter("rd2", 2, ["*:200", "*:250"]),
        RDFilter("rd3", 3, ["*:300"]),
    ]

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.rd.has_any("rd1", "rd2")) as rule:
            rule.allow()
        with route(R.rd.has("rd3")) as rule:  # one is ok, but not multiple
            rule.deny()

    result = generate(routemaps=routemaps, rd_filters=rd_filters, dev=juniper())
    expected = scrub("""
policy-options {
    route-distinguisher rd1 members [ 172.16.0.0:* 172.17.0.0:* ];
    route-distinguisher rd2 members [ *:200 *:250 ];
    route-distinguisher rd3 members *:300;
    policy-statement policy {
        term policy_0 {
            from route-distinguisher [ rd1 rd2 ];
            then accept;
        }
        term policy_1 {
            from route-distinguisher rd3;
            then reject;
        }
    }
}
""")
    assert result == expected


def test_juniper_both_rd_match_and_not_supported():
    routemaps = RouteMap[Mock]()

    rd_filters = [
        RDFilter("rd1", 1, ["172.16.0.0:*", "172.17.0.0:*"]),
        RDFilter("rd2", 2, ["*:200", "*:250"]),
    ]

    @routemaps
    def policy(device: Mock, route: Route):
        with route(R.rd.has("rd1", "rd2")) as rule:
            rule.allow()

    with pytest.raises(NotImplementedError):
      generate(routemaps=routemaps, rd_filters=rd_filters, dev=juniper())
