import sys
from abc import ABC, abstractmethod
from functools import cached_property
from importlib.metadata import entry_points
from typing import Generic, Optional, Type, TypeVar, List, Dict, Any, Tuple
import warnings
from annet.lib import get_context

T = TypeVar("T")


class Connector(ABC, Generic[T]):
    name: str
    # legacy
    ep_name: str
    ep_group: str = "annet.connectors"
    # right way just to use ep groups
    ep_by_group_only: str = ""
    _classes: Optional[List[Type[T]]] = None

    def _get_default(self) -> Type[T]:
        raise RuntimeError(f"{self.name} is not set")

    @cached_property
    def _entry_point(self) -> List[Type[T]]:
        ep = load_entry_point(self.ep_group, self.ep_name)
        if self.ep_by_group_only:
            ep.extend(load_entry_point_new(self.ep_by_group_only))
        return ep

    def get(self, *args, **kwargs) -> T:
        """
        Returns connector. If more than one is registered returns random and throw warning
        """
        if self._classes is None:
            self._classes = self._entry_point or [self._get_default()]
        if not self._classes:
            raise Exception(f"Not found registered class for group={self.ep_group}")
        if len(self._classes) > 1:
            warnings.warn(f"Multiple classes are registered with the group={self.ep_group} but "
                          f"{[cls for cls in self._classes]}", UserWarning)
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
        return []
    return [item.load() for item in ep]


def load_entry_point_new(group: str) -> List:
    if sys.version_info < (3, 10):
        ep = [item for item in entry_points().get(group, [])]
    else:
        ep = entry_points(group=group)  # pylint: disable=unexpected-keyword-arg
    if not ep:
        return []
    return [item.load() for item in ep]


class AdapterWithConfig(ABC, Generic[T]):
    @abstractmethod
    def with_config(self, **kwargs: Dict[str, Any]) -> T:
        pass


class AdapterWithName(ABC):
    @abstractmethod
    def name(self) -> str:
        pass


def get_connector_from_config(config_key: str, connectors: List[Connector]) -> Tuple[Connector, Dict[str, Any]]:
    seen: list[str] = []
    if not connectors:
        raise Exception("empty connectors")
    connector = connectors[0]  # default
    connector_params: Dict[str, Any] = {}
    if context_storage := get_context().get(config_key):
        adapter_name = context_storage.get("adapter", None)
        connector_params = context_storage.get("params", {})
        if adapter_name:
            for con in connectors:
                con_name = connector.__class__.__name__
                if isinstance(con, AdapterWithName):
                    con_name = con.name()
                seen.append(con_name)
                if adapter_name == con_name:
                    connector = con
                    break
            else:
                raise Exception("unknown %s %s: seen %s" % (config_key, adapter_name, seen))
        else:
            connector = connectors[0]
            if len(connectors) > 1:
                warnings.warn(f"Please specify adapter for '{config_key}'. Found more than one classes {connectors}", UserWarning)
    else:
        connector = connectors[0]
        if len(connectors) > 1:
            warnings.warn(f"Please specify '{config_key}'. Found more than one classes {connectors}", UserWarning)
    if isinstance(connector, AdapterWithConfig):
        connector = connector.with_config(**connector_params)
    # return connector_params only for storage
    # TODO: switch storage interface to AdapterWithConfig
    return connector, connector_params
