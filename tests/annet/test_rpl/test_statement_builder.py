from annet.rpl import RoutingPolicyStatement, Action, AndCondition, ResultType, SingleAction, ActionType, \
    CommunityActionValue
from annet.rpl.statement_builder import StatementBuilder, AsPathActionValue, NextHopActionValue


def new_statement():
    return RoutingPolicyStatement(
        name="stub",
        match=AndCondition(),
        then=Action(),
        number=1,
        result=None,
    )


def single_action(statement: RoutingPolicyStatement):
    actions = list(statement.then)
    assert len(actions) == 1
    return actions[0]


def test_result():
    with StatementBuilder(stmt := new_statement()) as b:
        b.allow()
    assert stmt.result == ResultType.ALLOW

    with StatementBuilder(stmt := new_statement()) as b:
        b.deny()
    assert stmt.result == ResultType.DENY

    with StatementBuilder(stmt := new_statement()) as b:
        b.next()
    assert stmt.result == ResultType.NEXT

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_policy()
    assert stmt.result == ResultType.NEXT_POLICY


def test_metric_action():
    with StatementBuilder(stmt := new_statement()) as b:
        b.add_metric(100)
    assert single_action(stmt) == SingleAction(
        field="metric",
        type=ActionType.ADD,
        value=100,
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.set_metric(100)
    assert single_action(stmt) == SingleAction(
        field="metric",
        type=ActionType.SET,
        value=100,
    )


def test_community_action():
    with StatementBuilder(stmt := new_statement()) as b:
        b.community.add("ABC")
        b.community.set("ABC", "DEF")
    assert single_action(stmt) == SingleAction(
        field="community",
        type=ActionType.CUSTOM,
        value=CommunityActionValue(
            replaced=["ABC", "DEF"],
            removed=[],
            added=[],
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.community.add("ABC")
        b.community.remove("XYZ")
    assert single_action(stmt) == SingleAction(
        field="community",
        type=ActionType.CUSTOM,
        value=CommunityActionValue(
            replaced=None,
            added=["ABC"],
            removed=["XYZ"],
        ),
    )


def test_as_path_action():
    with StatementBuilder(stmt := new_statement()) as b:
        b.as_path.expand("123")
        b.as_path.delete("ABC", 1)
        b.as_path.prepend("ABC", "DEF")
    assert single_action(stmt) == SingleAction(
        field="as_path",
        type=ActionType.CUSTOM,
        value=AsPathActionValue(
            delete=["ABC", "1"],
            expand=["123"],
            prepend=["ABC", "DEF"],
        ),
    )


def test_next_hop_action():
    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.self()
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="self",
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.peer()
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="peer",
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.discard()
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="discard",
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.ipv4_addr("127.0.0.1")
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="ipv4_addr",
            addr="127.0.0.1",
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.mapped_ipv4("127.0.0.1")
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="mapped_ipv4",
            addr="127.0.0.1",
        ),
    )

    with StatementBuilder(stmt := new_statement()) as b:
        b.next_hop.ipv6_addr("::1")
    assert single_action(stmt) == SingleAction(
        field="next_hop",
        type=ActionType.CUSTOM,
        value=NextHopActionValue(
            target="ipv6_addr",
            addr="::1",
        ),
    )
