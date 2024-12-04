from annet.rpl import R, ConditionOperator, PrefixMatchValue


def test_community():
    c1 = R.community.has("A", "B")
    assert c1.field == "community"
    assert c1.operator == ConditionOperator.HAS
    assert c1.value == ("A", "B")


def test_match_v4():
    c1 = R.match_v4("n1", "n2", or_longer=(1, 3))
    assert c1.field == "ip_prefix"
    assert c1.operator == ConditionOperator.CUSTOM
    assert c1.value == PrefixMatchValue(names=("n1", "n2"), greater_equal=1, less_equal=3)

    c1 = R.match_v4("n1", "n2")
    assert c1.field == "ip_prefix"
    assert c1.operator == ConditionOperator.CUSTOM
    assert c1.value == PrefixMatchValue(names=("n1", "n2"), greater_equal=None, less_equal=None)


def test_match_v6():
    c1 = R.match_v6("n1", "n2", or_longer=(1, 3))
    assert c1.field == "ipv6_prefix"
    assert c1.operator == ConditionOperator.CUSTOM
    assert c1.value == PrefixMatchValue(names=("n1", "n2"), greater_equal=1, less_equal=3)

    c1 = R.match_v6("n1", "n2")
    assert c1.field == "ipv6_prefix"
    assert c1.operator == ConditionOperator.CUSTOM
    assert c1.value == PrefixMatchValue(names=("n1", "n2"), greater_equal=None, less_equal=None)
