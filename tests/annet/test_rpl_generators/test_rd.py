from unittest.mock import Mock

from annet.rpl import R, RouteMap, Route
from annet.rpl_generators import RDFilter
from .helpers import scrub, iosxr, generate


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