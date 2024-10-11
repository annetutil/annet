import pytest

from annet.mesh.match_args import Left, Right
from annet.mesh.registry import MeshRulesRegistry


def foo(*args, **kwargs) -> None:
    pass


def bar(*args, **kwargs) -> None:
    pass


def baz(*args, **kwargs) -> None:
    pass


@pytest.mark.parametrize("short", [True, False])
def test_global(short):
    registry = MeshRulesRegistry(short)
    registry.device("left1-{x}")(foo)
    registry.device("left1-{x}", Left.x > 1)(bar)
    registry.device("left2-{x}")(baz)

    found = registry.lookup_global("left1-1")
    assert len(found) == 1
    assert found[0].handler is foo
    assert found[0].matched.x == 1

    short_found = registry.lookup_global("left1-1.example.com")
    if short:
        assert short_found == found
    else:
        assert short_found == []


@pytest.mark.parametrize("short", [True, False])
def test_direct(short):
    registry = MeshRulesRegistry(short)
    registry.direct("left1-{x}", "right1-{x}")(foo)
    registry.direct("left1-{x}", "right1-{x}", Left.x > Right.x)(bar)
    registry.direct("left2-{x}", "right1-{x}")(baz)

    found = registry.lookup_direct(
        "left1-1",
        ["right1-2", "right2"],
    )
    assert len(found) == 1
    assert found[0].handler is foo
    assert found[0].matched_left.x == 1
    assert found[0].matched_right.x == 2

    short_found = registry.lookup_direct(
        "left1-1.example.com",
        ["right1-2.example.com", "right2-2.example.com"],
    )
    if short:
        assert short_found == found
    else:
        assert short_found == []


@pytest.mark.parametrize("short", [True, False])
def test_indirect(short):
    registry = MeshRulesRegistry(short)
    registry.indirect("left1-{x}", "right1-{x}")(foo)
    registry.indirect("left1-{x}", "right1-{x}", Left.x > Right.x)(bar)
    registry.indirect("left2-{x}", "right1-{x}")(baz)

    found = registry.lookup_indirect(
        "left1-1",
        ["right1-2", "right2"],
    )
    assert len(found) == 1
    assert found[0].handler is foo
    assert found[0].matched_left.x == 1
    assert found[0].matched_right.x == 2

    short_found = registry.lookup_indirect(
        "left1-1.example.com",
        ["right1-2.example.com", "right2-2.example.com"],
    )
    if short:
        assert short_found == found
    else:
        assert short_found == []


def test_include():
    registry = MeshRulesRegistry()
    registry.device("left1-{x}")(foo)
    registry.direct("left1-{x}", "right1-{x}")(foo)
    registry.indirect("left1-{x}", "right1-{x}")(foo)
    main_registry = MeshRulesRegistry()
    main_registry.include(registry)

    found = registry.lookup_global("left1-1")
    assert len(found) == 1
    found = registry.lookup_indirect(
        "left1-1",
        ["right1-2", "right2"],
    )
    assert len(found) == 1
    found = registry.lookup_indirect(
        "left1-1",
        ["right1-2", "right2"],
    )
    assert len(found) == 1
