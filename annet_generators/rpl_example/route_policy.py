from annet.adapters.netbox.common.models import NetboxDevice
from annet.rpl import R, RouteMap, Route

routemap = RouteMap[NetboxDevice]()


@routemap
def example1(device: NetboxDevice, route: Route):
    condition = (R.interface == "l0.0") & (R.protocol == "bgp")
    with route(condition, number=1, name="n1") as rule:
        rule.set_local_pref(100)
        rule.set_metric(100)
        rule.add_metric(200)
        rule.community.set("COMMUNITY_EXAMPLE_ADD")
        rule.as_path.set(12345, "123456")
        rule.allow()
    with route(R.protocol == "bgp", R.community.has("comm_name"), number=2, name="n2") as rule:
        rule.set_local_pref(100)
        rule.add_metric(200)
        rule.community.add("COMMUNITY_EXAMPLE_ADD")
        rule.community.remove("COMMUNITY_EXAMPLE_REMOVE")
        rule.allow()


@routemap
def example2(device: NetboxDevice, route: Route):
    with route(R.as_path_filter("ASP_EXAMPLE"), number=3, name="n3") as rule:
        rule.deny()
    with route(R.match_v6("IPV6_LIST_EXAMPLE"), number=4, name="n4") as rule:
        rule.allow()

    with route(R.as_path_length >= 1, R.as_path_length <= 20, number=4, name="n4") as rule:
        rule.allow()
