from __future__ import annotations

import functools
import re
from collections import OrderedDict as odict
from collections import namedtuple
from typing import Any, Callable

from annet.annlib.rbparser.exceptions import RulebookSyntaxError


Answer = namedtuple("Answer", ("text", "send_nl"))


def compile_messages(tree: dict[str, Any]) -> odict[MakeMessageMatcher, Answer]:
    dialogs: odict[MakeMessageMatcher, Answer] = odict()
    for attrs in tree.values():
        if attrs["type"] == "normal":
            row: str = attrs["row"]

            if row.startswith("dialog:"):
                if match := re.match(r"^dialog:(.+):::(.+)$", row):
                    dialogs[MakeMessageMatcher(match.group(1), attrs["raw_rule"])] = Answer(
                        text=match.group(2).strip(),
                        send_nl=attrs["params"]["send_nl"],
                    )

                else:
                    raise RulebookSyntaxError(f"invalid deploy rulebook row: {row!r}")

    return dialogs


class MakeMessageMatcher:
    def __init__(self, text: str, raw_row: str | None = None):
        if raw_row is None:
            self.raw_params = {}
        else:
            from annet.annlib.rbparser.syntax import get_row_and_raw_params

            self.raw_params = get_row_and_raw_params(raw_row)[1]
        self.__text = text.strip()
        if self.__text.startswith("/") and self.__text.endswith("/"):
            regexp = re.compile(self.__text[1:-1].strip(), flags=re.I)
            self._fn: Callable[[str], re.Match[str] | bool | None] = regexp.match
        else:
            self._fn = lambda arg: _simplify_text(self.__text) in _simplify_text(arg)

    @property
    def text(self) -> str:
        return self.__text

    def __str__(self) -> str:
        return "%s(%r)" % (self.__class__.__name__, self.__text)

    __repr__ = __str__

    def __call__(self, intext: str) -> re.Match[str] | bool | None:
        return self._fn(intext)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MakeMessageMatcher):
            return NotImplemented
        return type(other) is type(self) and self.__text == other.text

    def __hash__(self) -> int:
        return hash("%s_%s" % (self.__class__.__name__, self.__text))


@functools.lru_cache()
def _simplify_text(text: str) -> str:
    return re.sub(r"\s", "", text).lower()
