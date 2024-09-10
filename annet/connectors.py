import sys
from abc import ABC
from functools import cached_property
from importlib.metadata import entry_points
from typing import Generic, Optional, Type, TypeVar, List
from annet.lib import get_context

T = TypeVar("T")


class Connector(ABC, Generic[T]):
    name: str
    ep_name: str
    ep_group: str = "annet.connectors"
    _classes: Optional[List[Type[T]]] = None

    def _get_default(self) -> Type[T]:
        raise RuntimeError(f"{self.name} is not set")

    @cached_property
    def _entry_point(self) -> List[Type[T]]:
        return load_entry_point(self.ep_group, self.ep_name)

    def get(self, *args, **kwargs) -> T:
        if self._classes is None:
            self._classes = self._entry_point or [self._get_default()]
        if len(self._classes) > 1:
            raise RuntimeError(
                f"Multiple classes are registered with the same "
                f"group={self.ep_group} and name={self.ep_name}: "
                f"{[cls for cls in self._classes]}",
            )

        res = self._classes[0]
        return res(*args, **kwargs)

    def get_all(self, *args, **kwargs) -> List[T]:
        if self._classes is None:
            self._classes = self._entry_point or [self._get_default()]

        return [cls(*args, **kwargs) for cls in self._classes]

    def set(self, cls: Type[T]):
        if self._classes is not None:
            raise RuntimeError(f"Cannot reinitialize value of {self.name}")
        self._classes = [cls]

    def set_all(self, classes: List[Type[T]]):
        if self._classes is not None:
            raise RuntimeError(f"Cannot reinitialize value of {self.name}")
        self._classes = list(classes)

    def is_default(self) -> bool:
        return self._classes is self._entry_point is None


class CachedConnector(Connector[T], ABC):
    _cache: Optional[T] = None

    def get(self, *args, **kwargs) -> T:
        assert not (args or kwargs), "Arguments forwarding is not allowed for cached connectors"
        if self._cache is None:
            self._cache = super().get()
        return self._cache

    def set(self, cls: Type[T]):
        super().set(cls)
        self._cache = None


def load_entry_point(group: str, name: str):
    if sys.version_info < (3, 10):
        ep = [item for item in entry_points().get(group, []) if item.name == name]
    else:
        ep = entry_points(group=group, name=name)  # pylint: disable=unexpected-keyword-arg
    if not ep:
        return None
    return [item.load() for item in ep]
