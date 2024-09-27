from annet.mesh.match_args import Left
from annet.mesh.registry import MeshRulesRegistry


def foo(*args, **kwargs) -> None:
    pass


def bar(*args, **kwargs) -> None:
    pass


def baz(*args, **kwargs) -> None:
    pass


def test_global():
    registry = MeshRulesRegistry()
    registry.device("left1-{x}")(foo)
    registry.device("left1-{x}", Left.x.cast_(int) > 1)(bar)
    registry.device("left2-{x}")(baz)

    found = registry.lookup_global("left1-1")
    assert len(found) == 1
    assert found[0].handler is foo
    assert found[0].matched.x == '1'
