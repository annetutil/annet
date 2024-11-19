from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Optional, Literal, TypeVar, Union

from .action import Action, SingleAction, ActionType
from .condition import Condition, AndCondition
from .policy import RoutingPolicyStatement
from .result import ResultType


class ThenField(str, Enum):
    community = "community"
    as_path = "as_path"
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


class CommunityActionBuilder:
    def __init__(self, community: CommunityActionValue):
        self._community = community

    def add(self, *community: str) -> None:
        for c in community:
            while c in self._community.removed:
                self._community.removed.remove(c)
            if c not in self._community.removed and (not self._community.removed or c not in self._community.replaced):
                self._community.added.append(c)

    def remove(self, *community: str) -> None:
        for c in community:
            if self._community.replaced:
                while c in self._community.replaced:
                    self._community.replaced.remove(c)
            while c in self._community.added:
                self._community.added.remove(c)
            if c not in self._community.removed:
                self._community.removed.append(c)

    def set(self, *community: str) -> None:
        self._community.added.clear()
        self._community.removed.clear()
        self._community.replaced = list(community)


@dataclass
class AsPathActionValue:
    set: Optional[list[str]] = None  # None means no replacement is done
    prepend: list[str] = field(default_factory=list)
    expand: list[str] = field(default_factory=list)
    expand_last_as: str = ""
    delete: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # check if any action required
        return bool(
            self.set is not None or self.prepend or self.expand or self.expand_last_as or self.delete
        )


RawAsNum = Union[str, int]


class AsPathActionBuilder:
    def __init__(self, as_path_value: AsPathActionValue):
        self._as_path_value = as_path_value

    def prepend(self, *values: RawAsNum) -> None:
        self._as_path_value.prepend = list(map(str, values))

    def delete(self, *values: RawAsNum) -> None:
        self._as_path_value.delete = list(map(str, values))

    def expand(self, *values: RawAsNum) -> None:
        self._as_path_value.expand = list(map(str, values))

    def expand_last_as(self, value: RawAsNum) -> None:
        self._as_path_value.expand_last_as = str(value)

    def set(self, *values: RawAsNum) -> None:
        self._as_path_value.set = list(map(str, values))


class StatementBuilder:
    def __init__(self, statement: RoutingPolicyStatement) -> None:
        self._statement = statement
        self._added_as_path: list[int] = []
        self._community = CommunityActionValue()
        self._as_path = AsPathActionValue()

    @property
    def as_path(self) -> AsPathActionBuilder:
        return AsPathActionBuilder(self._as_path)

    @property
    def community(self) -> CommunityActionBuilder:
        return CommunityActionBuilder(self._community)

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
        if self._as_path:
            self._statement.then.append(SingleAction(
                field=ThenField.as_path,
                type=ActionType.CUSTOM,
                value=self._as_path,
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
