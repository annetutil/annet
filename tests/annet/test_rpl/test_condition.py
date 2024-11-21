from annet.rpl import SingleCondition, ConditionOperator

FIELD1 = "field1"
FIELD2 = "field2"
FIELD3 = "field3"


def test_action_list():
    c1 = SingleCondition(
        field=FIELD1,
        operator=ConditionOperator.EQ,
        value=1,
    )
    c2 = SingleCondition(
        field=FIELD2,
        operator=ConditionOperator.EQ,
        value=3,
    )
    c3 = SingleCondition(
        field=FIELD1,
        operator=ConditionOperator.EQ,
        value=3,
    )

    condition = c1 & c2 & c3

    assert repr(condition)
    assert len(condition) == 3
    assert condition[FIELD1] == c1
    assert FIELD1 in condition
    assert FIELD2 in condition
    assert FIELD3 not in condition
    assert list(condition) == [c1, c2, c3]
    assert list(condition.find_all(FIELD1)) == [c1, c3]
    assert list(condition.find_all(FIELD2)) == [c2]
    assert list(condition.find_all(FIELD3)) == []
