from dataclasses import dataclass
from typing import Optional, Callable, Generic, TypeVar, Union

from .action import Action
from .condition import AndCondition, Condition
from .match_builder import merge_conditions
from .policy import RoutingPolicy, RoutingPolicyStatement
from .result import ResultType
from .statement_builder import StatementBuilder


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
            match=merge_conditions(AndCondition(*conditions)),
            then=Action(),
            result=ResultType.NEXT,
        )
        self.statements.append(statement)
        return StatementBuilder(statement=statement)


DeviceT = TypeVar("DeviceT")
RouteHandlerFunc = Callable[[DeviceT, Route], None]
Decorator = Callable[[RouteHandlerFunc[DeviceT]], RouteHandlerFunc[DeviceT]]


@dataclass
class Handler(Generic[DeviceT]):
    name: str
    func: RouteHandlerFunc[DeviceT]


class RouteMap(Generic[DeviceT]):
    def __init__(self) -> None:
        self.handlers: list[Handler[DeviceT]] = []
        self.submaps: list[RouteMap[DeviceT]] = []

    def __call__(
            self, func: Optional[RouteHandlerFunc[DeviceT]] = None, *, name: str = "",
    ) -> Union[RouteHandlerFunc[DeviceT], Decorator[DeviceT]]:
        def decorator(func: RouteHandlerFunc[DeviceT]) -> RouteHandlerFunc[DeviceT]:
            nonlocal name
            if not name:
                name = func.__name__
            self.handlers.append(Handler(name, func))
            return func

        if func is None:
            return decorator
        return decorator(func)

    def include(self, other: "RouteMap[DeviceT]") -> None:
        self.submaps.append(other)

    def apply(self, device: DeviceT) -> list[RoutingPolicy]:
        result: list[RoutingPolicy] = []

        for handler in self.handlers:
            route = Route(handler.name)
            handler.func(device, route)
            result.append(RoutingPolicy(route.name, route.statements))
        for submap in self.submaps:
            result.extend(submap.apply(device))
        return result
