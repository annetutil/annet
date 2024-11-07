from pprint import pprint

from annet.rpl.condition import R
from annet.rpl.rule import Route


def example(route: Route):
    condition = (R.interface == "l0.0") & (R.protocol == "bgp")
    with route(condition, order=1) as rule:
        rule.next_hop = "self"
        rule.allow()
    with route(R.protocol == "bgp", order=2) as rule:
        rule.local_pref = 100
        rule.add_community("xxx").allow()


route = Route()
example(route)
for rule in route.rules:
    pprint(rule)
