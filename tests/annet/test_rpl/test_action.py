from annet.rpl import Action, SingleAction, ActionType

FIELD1 = "field1"
FIELD2 = "field2"
FIELD3 = "field3"


def test_action_list():
    items = [
        SingleAction(
            field=FIELD1,
            type=ActionType.ADD,
            value=1,
        ), SingleAction(
            field=FIELD2,
            type=ActionType.ADD,
            value=3,
        ), SingleAction(
            field=FIELD1,
            type=ActionType.ADD,
            value=3,
        ),
    ]

    action = Action()
    for item in items:
        action.append(item)

    assert repr(action)
    assert len(action) == 3
    assert action[FIELD1] == SingleAction(
        field=FIELD1,
        type=ActionType.ADD,
        value=1,
    )
    assert FIELD1 in action
    assert FIELD2 in action
    assert FIELD3 not in action
    assert list(action) == items
    assert list(action.find_all(FIELD1)) == [items[0], items[2]]
    assert list(action.find_all(FIELD2)) == [items[1]]
    assert list(action.find_all(FIELD3)) == []
