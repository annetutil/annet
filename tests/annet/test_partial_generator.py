from types import SimpleNamespace

import pytest

from annet.generators import _run_partial_generator
from annet.generators.exceptions import GeneratorError, InvalidValueFromGenerator
from annet.generators.partial import PartialGenerator
from annet.types import GeneratorPartialRunArgs


class ReturnsNone(PartialGenerator):
    def run_arista(self, device):
        return None


class FailsBeforeYield(PartialGenerator):
    def run_arista(self, device):
        raise ValueError("missing inventory")


def _run(gen_cls: type[PartialGenerator]) -> None:
    storage = SimpleNamespace(flush_perf=lambda: None)
    device = SimpleNamespace(id=1, hostname="dev1", hw=SimpleNamespace(vendor="arista"))
    _run_partial_generator(gen_cls(storage=storage), GeneratorPartialRunArgs(device=device))


@pytest.mark.parametrize(
    ("gen_cls", "cause"),
    [(ReturnsNone, InvalidValueFromGenerator), (FailsBeforeYield, ValueError)],
)
def test_error_before_generation_starts_is_wrapped(gen_cls, cause):
    with pytest.raises(GeneratorError) as exc_info:
        _run(gen_cls)
    assert isinstance(exc_info.value.__cause__, cause)
