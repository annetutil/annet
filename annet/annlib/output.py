import abc
from typing import Any


class Dumpable(abc.ABC):
    def dump(self) -> Any:
        pass


class TextArgs:
    __slots__ = ("text", "color", "offset")

    def __init__(self, text: str, color: str | None = None,
                 offset: int | None = None) -> None:
        self.text = text
        self.color = color
        self.offset = offset  # смещение от начала линии

    def __repr__(self) -> str:
        return "%s(%r, %s, %s)" % (self.__class__.__name__, self.text, self.color, self.offset)
