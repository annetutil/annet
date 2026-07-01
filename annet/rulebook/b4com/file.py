from typing import Any

from annet.annlib.rulebook.common import DiffDict, LogicResult
from annet.annlib.types import Op


def change(key: tuple[str, ...], diff: DiffDict, **kwargs: Any) -> LogicResult:
    yield from [(True, add["row"], None) for add in diff[Op.ADDED]]
