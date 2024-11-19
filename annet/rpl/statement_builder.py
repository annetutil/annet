from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Optional, Literal, TypeVar

from .action import Action, SingleAction, ActionType
from .condition import Condition, AndCondition
from .policy import RoutingPolicyStatement
from .result import ResultType


class ThenField(str, Enum):
    community = "community"
    local_pref = "local_pref"
    metric = "metric"
    rpki_valid_state = "rpki_valid_state"
    next_hop = "next_hop"


ValueT = TypeVar("ValueT")
_Setter = Callable[[ValueT], SingleAction[ValueT]]


@dataclass
class CommunityActionValue:
    replaced: Optional[list[str]] = None  # None means no replacement is done
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # check if any action required
        return bool(self.replaced is not None or self.added or self.removed)


class StatementBuilder:
    def __init__(self, statement: RoutingPolicyStatement) -> None:
        self._statement = statement
        self._added_as_path: list[int] = []
        self._community = CommunityActionValue()

    def _set(self, field: str, value: ValueT) -> None:
        action = self._statement.then
        if field in action:
            action[field].type = ActionType.SET
            action[field].value = value
        else:
            action.append(SingleAction(
                field=field,
                type=ActionType.SET,
                value=value,
            ))

    def set_local_pref(self, value: int) -> None:
        self._set(ThenField.local_pref, value)

    def set_metric(self, value: int) -> None:
        self._set(ThenField.metric, value)

    def add_metric(self, value: int) -> None:
        action = self._statement.then
        field = ThenField.metric
        if field in action:
            old_action = action[field]
            if old_action.type == ActionType.SET:
                action[field].value += value
            elif old_action.type == ActionType.ADD:
                action[field].value = value
            else:
                raise RuntimeError(f"Unknown action type {old_action.type} for metric")
        else:
            action.append(SingleAction(
                field=field,
                type=ActionType.ADD,
                value=value,
            ))

    def set_rpki_valid_state(self, value: str) -> None:
        self._set(ThenField.rpki_valid_state, value)

    def set_next_hop(self, value: Literal["self", "peer"]) -> None:  # ???
        self._set(ThenField.next_hop, value)

    def __enter__(self) -> "StatementBuilder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._community:
            self._statement.then.append(SingleAction(
                field=ThenField.community,
                type=ActionType.CUSTOM,
                value=self._community,
            ))
        return None

    def allow(self) -> None:
        self._statement.result = ResultType.ALLOW

    def deny(self) -> None:
        self._statement.result = ResultType.DENY

    def next(self) -> None:
        self._statement.result = ResultType.NEXT

    def next_policy(self) -> None:
        self._statement.result = ResultType.NEXT_POLICY

    def add_as_path(self, *as_path: int) -> None:
        self._added_as_path.extend(as_path)

    def add_community(self, *community: str) -> None:
        for c in community:
            while c in self._community.removed:
                self._community.removed.remove(c)
            if c not in self._community.removed and (not self._community.removed or c not in self._community.replaced):
                self._community.added.append(c)

    def remove_community(self, *community: str) -> None:
        for c in community:
            if self._community.replaced:
                while c in self._community.replaced:
                    self._community.replaced.remove(c)
            while c in self._community.added:
                self._community.added.remove(c)
            if c not in self._community.removed:
                self._community.removed.append(c)

    def set_community(self, *community: str) -> None:
        self._community.added.clear()
        self._community.removed.clear()
        self._community.replaced = list(community)


class Route:
    def __init__(self, name: str):
        self.name = name
        self.statements: list[RoutingPolicyStatement] = []

    def __call__(
            self,
            *conditions: Condition,
            name: Optional[str] = None,
            number: Optional[int] = None,
    ) -> "StatementBuilder":
        statement = RoutingPolicyStatement(
            name=name,
            number=number,
            match=AndCondition(*conditions),
            then=Action(),
            result=ResultType.NEXT,
        )
        self.statements.append(statement)
        return StatementBuilder(statement=statement)
