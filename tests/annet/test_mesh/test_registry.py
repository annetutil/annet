from types import SimpleNamespace

import pytest

from annet.mesh import united_ports
from annet.mesh.match_args import Left, Right
from annet.mesh.registry import MeshRulesRegistry, MatchedIndirectPair, MatchedDirectPair


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
    assert found[0].match.x == 1

    short_found = registry.lookup_global("left1-1.example.com")
    if short:
        assert short_found == found
    else:
        assert short_found == []

@pytest.mark.parametrize("short", [True, False])
def test_virtual(short):
    registry = MeshRulesRegistry(short)
    registry.virtual("left1-{x}", (1, 2))(foo)
    registry.virtual("left1-{x}", (2, 3), Left.x > 1)(bar)
    registry.virtual("left2-{x}", (4, 5))(baz)

    found = registry.lookup_virtual("left1-1")
    assert len(found) == 1
    assert found[0].handler is foo
    assert found[0].match.x == 1
    assert found[0].num == (1,2)

    short_found = registry.lookup_virtual("left1-1.example.com")
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
    assert found[0].match_left.x == 1
    assert found[0].match_right.x == 2

    short_found = registry.lookup_direct(
        "left1-1.example.com",
        ["right1-2.example.com", "right2-2.example.com"],
    )
    if short:
        assert short_found == [MatchedDirectPair(
            handler=foo,
            port_processor=united_ports,
            direct_order=True,
            name_left="left1-1.example.com",
            match_left=SimpleNamespace(x=1),
            name_right="right1-2.example.com",
            match_right=SimpleNamespace(x=2),
        )]
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
    assert found[0].match_left.x == 1
    assert found[0].match_right.x == 2

    short_found = registry.lookup_indirect(
        "left1-1.example.com",
        ["right1-2.example.com", "right2-2.example.com"],
    )
    if short:
        assert short_found == [MatchedIndirectPair(
            handler=foo,
            direct_order=True,
            name_left="left1-1.example.com",
            match_left=SimpleNamespace(x=1),
            name_right="right1-2.example.com",
            match_right=SimpleNamespace(x=2),
        )]
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
