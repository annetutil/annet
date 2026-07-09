from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


FIRST_EXCEPTION = 1
ALL_COMPLETED = 2


@dataclass
class Question:
    question: str  # frame it using / if it is a regular expression
    answer: str
    is_regexp: bool | None = False
    not_send_nl: bool = False


@dataclass
class Command:
    cmd: str | bytes
    questions: list[Question] | None = None
    exc_handler: list[Question] | None = None
    timeout: int | None = None  # total timeout
    read_timeout: int | None = None  # timeout between consecutive reads
    suppress_nonzero: bool = False
    suppress_eof: bool = False
    suppress_errors: bool = False
    level: int = 0  # block nesting depth, set by the patch builder

    def __str__(self) -> str:
        if isinstance(self.cmd, bytes):
            return self.cmd.decode("utf-8")
        return self.cmd


@dataclass
class CommandList:
    cmss: list[Command] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.cmss:
            self.cmss = []

    def __iter__(self) -> Iterator[Command]:
        return iter(self.cmss)

    def __len__(self) -> int:
        return len(self.cmss)

    def add_cmd(self, cmd: Command) -> None:
        assert isinstance(cmd, Command)
        self.cmss.append(cmd)

    def as_list(self) -> list[Command]:  # TODO: delete
        return self.cmss
