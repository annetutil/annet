from dataclasses import dataclass

import pytest

from annet.rpl import Route, RouteMap, R, SingleAction, ActionType, SingleCondition, ConditionOperator

DEVICE_NAME = "dev1"


@dataclass
class Device:
    name: str


def example_rule1(device: Device, route: Route):
    assert device.name == DEVICE_NAME
    with route(R.protocol == "bgp", R.net_len == 10, name="n1", number=10) as rule:
        rule.set_metric(100)
        rule.allow()

    with route(R.as_path_length >= 1, R.as_path_length <= 10, name="n2", number=20) as rule:
        rule.deny()


def test_routemap():
    subroutemap = RouteMap[Device]()
    subroutemap(example_rule1)

    routemap = RouteMap[Device]()
    routemap.include(subroutemap)

    device = Device(DEVICE_NAME)
    res = routemap.apply(device)
    assert len(res) == 1
    policy = res[0]
    assert policy.name == "example_rule1"
    assert len(policy.statements) == 2
    s1 = policy.statements[0]
    assert s1.result == "allow"
    assert s1.name == "n1"
    assert s1.number == 10
    assert len(s1.match) == 2
    assert s1.match["protocol"] == SingleCondition(
        field="protocol",
        operator=ConditionOperator.EQ,
        value="bgp",
    )
    assert s1.match["net_len"] == SingleCondition(
        field="net_len",
        operator=ConditionOperator.EQ,
        value=10,
    )
    assert len(s1.then) == 1
    assert s1.then["metric"] == SingleAction(
        field="metric",
        type=ActionType.SET,
        value=100,
    )

    s2 = policy.statements[1]
    assert s2.result == "deny"
    assert s2.name == "n2"
    assert s2.number == 20
    assert len(s2.then) == 0
    assert len(s2.match) == 1
    assert s2.match["as_path_length"] == SingleCondition(
        field="as_path_length",
        operator=ConditionOperator.BETWEEN_INCLUDED,
        value=(1, 10),
    )


@pytest.mark.parametrize(["allowed_rules", "expected_rules"], [
    (["example_rule1"], ["example_rule1"]),
    (["invalid"], []),
    (["invalid", "example_rule1"], ["example_rule1"]),
])
def test_routemap_filter(allowed_rules, expected_rules):
    subroutemap = RouteMap[Device]()
    subroutemap(example_rule1)

    routemap = RouteMap[Device]()
    routemap.include(subroutemap)

    device = Device(DEVICE_NAME)
    res = routemap.apply(device, allowed_rules)
    found_rules = [r.name for r in res]
    assert found_rules == expected_rules