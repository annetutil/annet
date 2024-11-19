from typing import Any

from annet.rpl import R, RouteMap, Route

routemap = RouteMap()


@routemap
def example1(device: Any, route: Route):
    condition = (R.interface == "l0.0") & (R.protocol == "bgp")
    with route(condition, number=1, name="n1") as rule:
        rule.set_local_pref(100)
        rule.set_community("COMMUNITY_EXAMPLE_ADD")
        rule.allow()
    with route(R.protocol == "bgp", R.community.has("comm_name"), number=2, name="n2") as rule:
        rule.set_local_pref(100)
        rule.add_community("COMMUNITY_EXAMPLE_ADD")
        rule.remove_community("COMMUNITY_EXAMPLE_REMOVE")
        rule.allow()


@routemap
def example2(device: Any, route: Route):
    with route(R.as_path_filter("ASP_EXAMPLE"), number=3, name="n3") as rule:
        rule.deny()

    with route(R.match_v6("IPV6_LIST_EXAMPLE"), number=4, name="n4") as rule:
        rule.allow()
