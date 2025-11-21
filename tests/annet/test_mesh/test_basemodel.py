from typing import Annotated
from dataclasses import dataclass, field

import pytest

from annet.mesh.basemodel import (
    UseFirst, UseLast, Special, Forbid, ForbidChange, Concat, DictMerge, BaseMeshModel, MergeForbiddenError, merge,
    Merge, merge_dataclass, MergeForbiddenError
)


@pytest.mark.parametrize(
    ["first", "second", "merger", "expected"],
    [
        ("a", "b", UseFirst(), "a"),
        (Special.NOT_SET, "b", UseFirst(), "b"),
        ("a", "b", UseLast(), "b"),
        ("a", Special.NOT_SET, UseLast(), "a"),
        ("a", Special.NOT_SET, Forbid(), "a"),
        (Special.NOT_SET, "b", Forbid(), "b"),
        (Special.NOT_SET, "b", ForbidChange(), "b"),
        ("a", Special.NOT_SET, ForbidChange(), "a"),
        ("a", "a", ForbidChange(), "a"),
        ("a", "b", Concat(), "ab"),
        ({"x": 1}, {"y": 2}, DictMerge(), {"x": 1, "y": 2}),
        ({"x": "a"}, {"x": "b"}, DictMerge(Concat()), {"x": "ab"}),
    ]
)
def test_merger_class(first, second, merger, expected):
    assert expected == merger("name", first, second)


@pytest.mark.parametrize(
    ["first", "second", "merger"],
    [
        ("a", "b", Forbid()),
        ("a", "b", ForbidChange()),
    ]
)
def test_merger_class_raise(first, second, merger):
    with pytest.raises(MergeForbiddenError):
        merger("name", first, second)


def test_merge_model():
    class A(BaseMeshModel):
        x: Annotated[int, UseLast()]
        y: Annotated[int, UseFirst()]

        def __eq__(self, other):
            return vars(self) == vars(other)

    assert merge(A(x=1), A(y=2)) == A(x=1, y=2)
    assert merge(A(x=1, y=1), A(x=2, y=2)) == A(x=2, y=1)

    merger = Merge()
    assert merger("x", A(x=1, y=1), A(x=2, y=2)) == A(x=2, y=1)


def test_merge_model_default():
    class A(BaseMeshModel):
        x: int

        def __eq__(self, other):
            return vars(self) == vars(other)

    assert merge(A(x=1), A()) == A(x=1)
    assert merge(A(x=1), A(x=1)) == A(x=1)
    with pytest.raises(MergeForbiddenError):
        merge(A(x=1), A(x=2))


def test_merge_dataclass():
    @dataclass
    class A:
        x: int = 123
        y: str = "YYY"

    @dataclass
    class B:
        a: A = field(default_factory=A)
        b: bool = True

    a1, a2 = A(), A()
    m = merge_dataclass(a1, a2)
    assert m.x == 123
    assert m.y == "YYY"

    a1, a2 = A(x=1), A(y="ZZZ")
    m = merge_dataclass(a1, a2)
    assert m.x == 1
    assert m.y == "ZZZ"

    a1, a2 = A(x=1), A(x=1, y="ZZZ")
    m = merge_dataclass(a1, a2)
    assert m.x == 1
    assert m.y == "ZZZ"

    a1, a2 = A(x=1, y="ZZZ"), A(x=1, y="ZZZ")
    m = merge_dataclass(a1, a2)
    assert m.x == 1
    assert m.y == "ZZZ"

    b1, b2 = B(), B()
    m = merge_dataclass(b1, b2)
    assert m.a.x == 123
    assert m.a.y == "YYY"
    assert m.b == True

    b1, b2 = B(a=A(x=1)), B(b=False)
    m = merge_dataclass(b1, b2)
    assert m.a.x == 1
    assert m.a.y == "YYY"
    assert m.b == False

    b1, b2 = B(b=False), B(a=A(x=1))
    m = merge_dataclass(b1, b2)
    assert m.a.x == 1
    assert m.a.y == "YYY"
    assert m.b == False

    a1, a2 = A(x=1), A(x=2)
    with pytest.raises(MergeForbiddenError):
        m = merge_dataclass(a1, a2)

    b1, b2 = B(a=A(x=1)), B(a=A(x=2))
    with pytest.raises(MergeForbiddenError):
        m = merge_dataclass(b1, b2)


def test_merge_model_with_dataclasses():
    @dataclass
    class X:
        m: int = 0
        n: int = 0

    class A(BaseMeshModel):
        x: Annotated[X, Merge]

        def __init__(self, **kwargs):
            kwargs.setdefault("x", X())
            super().__init__(**kwargs)

        def __eq__(self, other):
            return vars(self) == vars(other)

    assert merge(A(), A()) == A()
    assert merge(A(x=X()), A(x=X())) == A(x=X())
    assert merge(A(x=X(m=1)), A(x=X(n=2))) == A(x=X(m=1,n=2))
    with pytest.raises(MergeForbiddenError):
        merge(A(x=X(m=1)), A(x=X(m=2)))


def test_equal_not_default_dataclass():
    @dataclass
    class X:
        m: int

    class A(BaseMeshModel):
        x: X | None = None

        def __eq__(self, other):
            return vars(self) == vars(other)

    assert merge(A(x=X(1)), A(x=X(1))) == A(x=X(1))
