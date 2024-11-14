from pprint import pprint
from typing import Any

from annet.rpl.condition import R
from annet.rpl.rule import Route
from annet.rpl.routemap import RouteMap

routemap = RouteMap()

@routemap
def example(device: Any, route: Route):
    condition = (R.interface == "l0.0") & (R.protocol == "bgp")
    with route(condition, number=1, name="n1") as rule:
        rule.next_hop = "self"
        rule.local_pref = 100
        rule.allow()
    with route(R.protocol == "bgp", R.community.has("comm_name"), number=2, name="n2") as rule:
        rule.local_pref = 100
        rule.add_community("xxx")
        rule.allow()


policies = routemap.apply(None)

for policy in policies:
    print(f"=== {policy.name} ===")
    for rule in policy.statements:
        pprint(rule)
