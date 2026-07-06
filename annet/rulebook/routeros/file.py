from collections.abc import Iterator
from typing import Any

from annet.annlib.types import Op


def change(
    key: tuple[str, ...], diff: dict[str, list[dict[str, Any]]], **kwargs: Any
) -> Iterator[tuple[bool, str, None]]:
    yield from [(True, add["row"], None) for add in diff[Op.ADDED]]
