from pprint import pprint, PrettyPrinter

from annet.rpl.condition import R, AndCondition
from annet.rpl.rule import Route, Rule


def example(route: Route):
    condition = (R.interface == "l0.0") & (R.protocol == "bgp")
    with route(condition, order=1, name="n1") as rule:
        rule.next_hop = "self"
        rule.allow()
    with route(R.protocol == "bgp", R.community.has("comm_name"), order=2, name="n2") as rule:
        rule.local_pref = 100
        rule.add_community("xxx")
        rule.allow()


route = Route()
example(route)

for rule in route.rules:
    pprint(rule)
