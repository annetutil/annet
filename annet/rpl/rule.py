from dataclasses import dataclass, field
from typing import Optional, Literal, Any

from .action import Action, SingleAction, ActionType
from .condition import Condition, AndCondition
from .policy import RoutingPolicyStatement
from .result import ResultType


class Field:
    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance: "StatementBuilder", value: Any):
        action = instance._statement.then
        if self.name in action:
            action[self.name].value = value
        else:
            action.append(SingleAction(
                field=self.name,
                action_type=ActionType.SET,
                value=value,
            ))

    def __get__(self, instance: "StatementBuilder", objtype=None):
        return instance._statement.then[self.name]

class StatementBuilder:
    def __init__(self, statement: RoutingPolicyStatement) -> None:
        self._statement = statement
        self._added_as_path: list[int] = []
        self._replaced_community: Optional[list[str]] = None
        self._added_community: list[str] = []
        self._removed_community: list[str] = []

    local_pref: int = Field()
    metric: int = Field()
    rpki_valid_state: str = Field()
    next_hop: Literal["self", "peer"] = Field()  # ???


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
