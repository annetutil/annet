import sys
from abc import ABC
from functools import cached_property
from importlib.metadata import entry_points
from typing import Generic, Optional, Type, TypeVar


T = TypeVar("T")


class Connector(ABC, Generic[T]):
    name: str
    ep_name: str
    ep_group: str = "annet.connectors"
    _cls: Optional[Type[T]] = None

    def _get_default(self) -> Type[T]:
        raise RuntimeError(f"{self.name} is not set")

    @cached_property
    def _entry_point(self) -> Optional[Type[T]]:
        return load_entry_point(self.ep_group, self.ep_name)

    def get(self, *args, **kwargs) -> T:
        if self._cls is not None:
            res = self._cls
        else:
            res = self._entry_point or self._get_default()
        return res(*args, **kwargs)

    def set(self, cls: Type[T]):
        if self._cls is not None:
            raise RuntimeError(f"Cannot reinitialize value of {self.name}")
        self._cls = cls

    def is_default(self) -> bool:
        return self._cls is self._entry_point is None


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
    if len(ep) > 1:
        raise RuntimeError(f"Multiple entry points with the same {group=} and {name=}: {[item.value for item in ep]}")
    for item in ep:
        return item.load()
