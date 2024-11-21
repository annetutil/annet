import pytest
from annet.rpl import SingleCondition, ConditionOperator

FIELD1 = "field1"
FIELD2 = "field2"
FIELD3 = "field3"


def test_and_condition():
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


def test_merge_other_field():
    c1 = SingleCondition("f1", ConditionOperator.CUSTOM, "")
    c2 = SingleCondition("f2", ConditionOperator.CUSTOM, "")
    with pytest.raises(ValueError):
        c1.merge(c2)


@pytest.mark.parametrize(["v1", "op", "v2", "res"], [
    (1, ConditionOperator.LT, 2, 1),
    (1, ConditionOperator.LE, 2, 1),
    (1, ConditionOperator.GE, 2, 2),
    (1, ConditionOperator.GT, 2, 2),
])
def test_cmp(v1, op, v2, res):
    c1 = SingleCondition("f1", op, v1)
    c2 = SingleCondition("f1", op, v2)
    cres = c1.merge(c2)
    assert cres.field == c1.field
    assert cres.operator == op
    assert cres.value == res


def test_between():
    c1 = SingleCondition("f1", ConditionOperator.GE, 10)
    c2 = SingleCondition("f1", ConditionOperator.LE, 20)
    cres = c1.merge(c2)
    assert cres.field == c1.field
    assert cres.operator == ConditionOperator.BETWEEN_INCLUDED
    assert cres.value == (10, 20)
    assert c2.merge(c1) == cres