from collections.abc import Callable
from enum import Enum
from typing import Optional, Literal, TypeVar

from .action import Action, SingleAction, ActionType
from .condition import Condition, AndCondition
from .policy import RoutingPolicyStatement
from .result import ResultType


class ThenField(str, Enum):
    local_pref = "local_pref"
    metric = "metric"
    rpki_valid_state = "rpki_valid_state"
    next_hop = "next_hop"


ValueT = TypeVar("ValueT")
_Setter = Callable[[ValueT], SingleAction[ValueT]]


class StatementBuilder:
    def __init__(self, statement: RoutingPolicyStatement) -> None:
        self._statement = statement
        self._added_as_path: list[int] = []
        self._replaced_community: Optional[list[str]] = None
        self._added_community: list[str] = []
        self._removed_community: list[str] = []

    def _set(self, field: str, value: ValueT) -> None:
        action = self._statement.then
        if field in action:
            action[field].value = value
        else:
            action.append(SingleAction(
                field=field,
                action_type=ActionType.SET,
                value=value,
            ))

    def set_local_pref(self, value: int) -> None:
        self._set(ThenField.local_pref, value)

    def set_metric(self, value: int) -> None:
        self._set(ThenField.metric, value)

    def set_rpki_valid_state(self, value: str) -> None:
        self._set(ThenField.rpki_valid_state, value)

    def set_next_hop(self, value: Literal["self", "peer"]) -> None:  # ???
        self._set(ThenField.next_hop, value)

    def __enter__(self) -> "StatementBuilder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
