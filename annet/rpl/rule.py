from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Literal

from annet.rpl.condition import Condition, AndCondition


class Action(Enum):
    ALLOW = "allow"
    DENY = "deny"
    SKIP = "skip"


@dataclass
class Rule:
    _conditions: AndCondition
    _name: Optional[str]
    _order: Optional[int]
    _action: Action = Action.SKIP
    _added_as_path: list[int] = field(default_factory=list)
    _replaced_community: Optional[list[str]] = None
    _added_community: list[str] = field(default_factory=list)
    _removed_community: list[str] = field(default_factory=list)
    local_pref: Optional[int] = None
    metric: Optional[int] = None
    rpki_valid_state: Optional[str] = None
    next_hop: Optional[Literal["self", "peer"]] = None

    def __enter__(self) -> "Rule":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

    def allow(self) -> "Rule":
        self._action = Action.ALLOW
        return self

    def deny(self) -> "Rule":
        self._action = Action.DENY
        return self

    def add_as_path(self, *as_path: int) -> None:
        self._added_as_path.extend(as_path)

    def add_community(self, *community: str) -> None:
        for c in community:
            while c in self._removed_community:
                self._removed_community.remove(c)
            if c not in self._removed_community and (not self._removed_community or c not in self._replaced_community):
                self._added_community.append(c)

    def remove_community(self, *community: str) -> None:
        for c in community:
            if self._replaced_community:
                while c in self._replaced_community:
                    self._replaced_community.remove(c)
            while c in self._added_community:
                self._added_community.remove(c)
            if c not in self._removed_community:
                self._removed_community.append(c)

    def set_community(self, *community: str) -> None:
        self._added_community.clear()
        self._removed_community.clear()
        self._replaced_community = list(community)


class Route:
    def __init__(self):
        self.rules: list[Rule] = []

    def __call__(
            self,
            *conditions: Condition,
            name: Optional[str] = None,
            order: Optional[int] = None,
    ) -> "Rule":
        rule = Rule(AndCondition(*conditions), name, order)
        self.rules.append(rule)
        return rule
