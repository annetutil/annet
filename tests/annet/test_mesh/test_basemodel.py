from typing import Annotated

import pytest

from annet.mesh.basemodel import (
    UseFirst, UseLast, Special, Forbid, ForbidChange, Concat, DictMerge, BaseMeshModel, MergeForbiddenError, merge,
    Merge,
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
