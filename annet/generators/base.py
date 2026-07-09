from __future__ import annotations

import abc
import contextlib
import re
import textwrap
from collections.abc import Callable, Iterator, Sequence
from typing import Union, cast

from annet import tracing
from annet.storage import Device, Storage
from annet.tracing import tracing_connector
from annet.vendors import tabparser

from .exceptions import InvalidValueFromGenerator


# A single value that a generator may yield and that _filter_str can render.
Token = Union[str, int, float, tabparser.JuniperList, "GenStringable"]


NONE_SEARCHER = re.compile(r"\bNone\b")


class DefaultBlockIfCondition:
    pass


ParamsList = tabparser.JuniperList


class GenStringable(abc.ABC):
    @abc.abstractmethod
    def gen_str(self) -> str:
        pass


def _filter_str(value: Token) -> str:
    if isinstance(
        value,
        (
            str,
            int,
            float,
            tabparser.JuniperList,
            ParamsList,
        ),
    ):
        return str(value)

    if hasattr(value, "gen_str") and callable(value.gen_str):
        return value.gen_str()

    raise InvalidValueFromGenerator("Invalid yield type: %s(%s)" % (type(value).__name__, value))


def _split_and_strip(text: str) -> list[str]:
    if "\n" in text:
        rows = textwrap.dedent(text).strip().split("\n")
    else:
        rows = [text]
    return rows


# =====
class BaseGenerator:
    TYPE: str
    TAGS: list[str] = []
    ALLOW_NONE = False
    storage: Storage

    def supports_device(self, device: Device) -> bool:  # pylint: disable=unused-argument
        return True

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod
    def get_aliases(cls) -> set[str]:
        return {cls.get_name(), *cls.TAGS}


class TreeGenerator(BaseGenerator):
    def __init__(self, indent: str = "  ") -> None:
        self._indents: list[str] = []
        self._rows: list[str] = []
        self._block_path: list[str] = []
        self._indent = indent

    @tracing.contextmanager(min_duration="0.1")
    @contextlib.contextmanager
    def block(self, *tokens: Token, indent: str | None = None) -> Iterator[None]:
        span = tracing_connector.get().get_current_span()
        if span:
            span.set_attribute("tokens", " ".join(map(str, tokens)))

        indent = self._indent if indent is None else indent
        block = " ".join(map(_filter_str, tokens))
        self._block_path.append(block)
        self._append_text(block)
        self._indents.append(indent)
        yield
        self._indents.pop(-1)
        self._block_path.pop(-1)

    @contextlib.contextmanager
    def block_if(self, *tokens: Token | None, condition: object = DefaultBlockIfCondition) -> Iterator[None]:
        if condition is DefaultBlockIfCondition:
            condition = None not in tokens and "" not in tokens
        if condition:
            # In the default mode a truthy condition means no None token slipped through;
            # an explicitly-passed condition leaves token validity to the caller.
            with self.block(*cast("tuple[Token, ...]", tokens)):
                yield
                return
        yield

    @contextlib.contextmanager
    def multiblock(self, *blocks: Token | Sequence[Token]) -> Iterator[None]:
        if blocks:
            blk = blocks[0]
            tokens = blk if isinstance(blk, (list, tuple)) else [blk]
            with self.block(*tokens):
                with self.multiblock(*blocks[1:]):
                    yield
                    return
        yield

    @contextlib.contextmanager
    def multiblock_if(
        self, *blocks: Token | Sequence[Token], condition: object = DefaultBlockIfCondition
    ) -> Iterator[None]:
        if condition is DefaultBlockIfCondition:
            condition = None not in blocks
            if condition:
                if blocks:
                    blk = blocks[0]
                    tokens = blk if isinstance(blk, (list, tuple)) else [blk]
                    with self.block(*tokens):
                        with self.multiblock(*blocks[1:]):
                            yield
                            return
        yield

    # ===
    def _append_text(self, text: str) -> None:
        self._append_text_cb(text)

    def _append_text_cb(self, text: str, row_cb: Callable[[str], str] | None = None) -> None:
        for row in _split_and_strip(text):
            if row_cb:
                row = row_cb(row)
            self._rows.append("".join(self._indents) + row)


class TextGenerator(TreeGenerator):
    def __add__(self, line: str) -> TextGenerator:
        self._append_text(line)
        return self

    def __iter__(self) -> Iterator[str]:
        yield from self._rows
