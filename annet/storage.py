from __future__ import annotations

import abc
from collections.abc import Collection, Iterable, Sequence
from types import TracebackType
from typing import Any, Protocol, TypeAlias

from annet.annlib.netdev.views.hardware import HardwareView
from annet.connectors import Connector, get_connector_from_config


# Device identifier: an integer PK (netbox/annushka) or a string key (file adapter).
DeviceId: TypeAlias = int | str


class _StorageConnector(Connector["StorageProvider"]):
    name = "Storage"  # legacy
    ep_name = "storage"  # legacy
    ep_by_group_only = "annet.connectors.storage"


storage_connector = _StorageConnector()


class StorageProvider(abc.ABC):
    @abc.abstractmethod
    def storage(self) -> type[Storage]:
        pass

    @abc.abstractmethod
    def opts(self) -> type[StorageOpts]:
        pass

    @abc.abstractmethod
    def query(self) -> type[Query]:
        pass

    @abc.abstractmethod
    def name(self) -> str:
        pass


class Storage(abc.ABC):
    @abc.abstractmethod
    def __enter__(self) -> Storage:
        pass

    @abc.abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        pass

    @abc.abstractmethod
    def resolve_object_ids_by_query(self, query: Any) -> Iterable[DeviceId]:
        pass

    @abc.abstractmethod
    def resolve_fdnds_by_query(self, query: Any) -> list[str]:
        pass

    @abc.abstractmethod
    def resolve_all_fdnds(self) -> list[str]:
        pass

    @abc.abstractmethod
    def search_connections(self, device: Device, neighbor: Device) -> list[tuple[Interface, Interface]]:
        pass

    @abc.abstractmethod
    def make_devices(
        self,
        query: Any,
        preload_neighbors: bool = False,
        use_mesh: bool | None = None,
        preload_extra_fields: bool = False,
        **kwargs: Any,
    ) -> Sequence[Device]:
        pass

    @abc.abstractmethod
    def get_device(
        self, obj_id: Any, preload_neighbors: bool = False, use_mesh: bool | None = None, **kwargs: Any
    ) -> Device:
        pass

    @abc.abstractmethod
    def flush_perf(self) -> dict[str, Any] | None:
        pass


class StorageOpts(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def parse_params(cls, conf_params: dict[str, str] | None, cli_opts: Any) -> Any:
        pass


class Query(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def new(cls, query: str | Iterable[str], hosts_range: slice | None = None) -> Query:
        pass

    def is_empty(self) -> bool:
        return False


class Interface(Protocol):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def add_addr(self, address_mask: str, vrf: str | None) -> None:
        raise NotImplementedError


class Device(Protocol):
    @property
    @abc.abstractmethod
    def storage(self) -> Storage:
        pass

    @abc.abstractmethod
    def __hash__(self) -> int:
        pass

    @abc.abstractmethod
    def is_pc(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def hw(self) -> HardwareView:
        pass

    @property
    @abc.abstractmethod
    def id(self) -> DeviceId:
        pass

    @property
    @abc.abstractmethod
    def fqdn(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def hostname(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def neighbours_ids(self) -> Collection[DeviceId]:
        pass

    @property
    @abc.abstractmethod
    def breed(self) -> str | None:
        pass


class MeshDevice(Device, Protocol):
    """A device that also exposes the topology / interface-building surface.

    These members are only needed by the mesh executor; most consumers work with
    the smaller ``Device`` protocol above.
    """

    @property
    @abc.abstractmethod
    def neighbours_fqdns(self) -> list[str]:
        pass

    @abc.abstractmethod
    def make_lag(self, lag: int, ports: Sequence[str], lag_min_links: int | None) -> Interface:
        raise NotImplementedError

    @abc.abstractmethod
    def add_svi(self, svi: int) -> Interface:
        """Add SVI interface or return existing one"""
        raise NotImplementedError

    @abc.abstractmethod
    def add_subif(self, interface: str, subif: int) -> Interface:
        """Add sub interface or return existing one"""
        raise NotImplementedError

    @abc.abstractmethod
    def find_interface(self, name: str) -> Interface | None:
        raise NotImplementedError


def get_storage() -> tuple[StorageProvider, dict[str, Any]]:
    connectors = storage_connector.get_all()
    return get_connector_from_config("storage", connectors)
