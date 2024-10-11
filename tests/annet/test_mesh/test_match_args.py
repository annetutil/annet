from typing import Any

from annet.mesh.match_args import MatchExpr, match_safe, PeerNameTemplate

F = MatchExpr(lambda x: x)


class A:
    one = 1
    two = 2


def match(expr: MatchExpr, value) -> bool:
    return match_safe((expr,), value)


def test_match_expr():
    assert match(F == 1, 1)
    assert not match(F == 1, "1")
    assert not match(F == 2, 1)
    assert match(F >= 1, 1)
    assert match(F < 2, 1)
    assert not match(F > 10, 1)
    assert match(F != 10, 1)

    assert match(F.one == 1, A())
    assert not match(F.two == 1, A())
    assert not match(F.invalid == 1, A())

    assert match(F[0] == 10, [10])
    assert not match(F[0] == 10, [11])
    assert not match(F[100] == 10, [10])
    assert match(F["a"] == 10, {"a": 10})
    assert not match(F["invalid"] == 10, {"a": 1})

    assert match((F.one == 1) & (F.two == 2), A())
    assert match((F.one == 2) | (F.two == 2), A())
    assert not match((F.one == 2) & (F.two == 2), A())

    assert match(F.in_([1, 2]), 2)
    assert not match(F.in_([1, 2]), 100)

    assert match(F.cast_(str) == "1", 1)
    assert match(F.cast_(int) == 1, "1")


def match_name(template: str, name: str) -> dict[str, Any] | None:
    res = PeerNameTemplate(template).match(name)
    if res is None:
        return None
    return dict(res)


def test_peer_name_template():
    assert match_name("{x}", "12") == {"x": 12}
    assert match_name("{x}.example.com", "12.example.com") == {"x": 12}
    assert match_name("{x}", "12.example.com") is None
    assert match_name("{x}-{y}", "12-2") == {"x": 12, "y": 2}

    assert match_name("{x:.*}", "12") == {"x": "12"}
    assert match_name(".{x:(a|b)}.", ".a.") == {"x": "a"}
    assert match_name(".{x:(a|b)}.", ".x.") is None
    assert match_name(".{x:(a|b)}.", ".aa.") is None
    assert match_name(".{x:(a|b)+}.", ".aa.") == {"x": "aa"}
