import abc
from typing import Any, Iterable, Optional, Type, Union, Protocol, Dict
from annet.connectors import Connector, get_connector_from_config
from annet.annlib.netdev.views.hardware import HardwareView


class _StorageConnector(Connector["StorageProvider"]):
    name = "Storage"  # legacy
    ep_name = "storage"  # legacy
    ep_by_group_only = "annet.connectors.storage"


storage_connector = _StorageConnector()


class StorageProvider(abc.ABC):
    @abc.abstractmethod
    def storage(self) -> Type["Storage"]:
        pass

    @abc.abstractmethod
    def opts(self) -> Type["StorageOpts"]:
        pass

    @abc.abstractmethod
    def query(self) -> Type["Query"]:
        pass

    @abc.abstractmethod
    def name(self) -> str:
        pass


class Storage(abc.ABC):
    @abc.abstractmethod
    def __enter__(self):
        pass

    @abc.abstractmethod
    def __exit__(self, _, __, ___):
        pass

    @abc.abstractmethod
    def resolve_object_ids_by_query(self, query: Any):
        pass

    @abc.abstractmethod
    def resolve_fdnds_by_query(self, query: Any):
        pass

    @abc.abstractmethod
    def make_devices(
        self,
        query: Any,
        preload_neighbors: bool = False,
        use_mesh: bool = None,
        preload_extra_fields=False,
        **kwargs,
    ):
        pass

    @abc.abstractmethod
    def get_device(self, obj_id, preload_neighbors=False, use_mesh=None, **kwargs) -> "Device":
        pass

    @abc.abstractmethod
    def flush_perf(self):
        pass


class StorageOpts(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def parse_params(cls, conf_params: Optional[Dict[str, str]], cli_opts: Any):
        pass


class Query(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def new(cls, query: Union[str, Iterable[str]], hosts_range: Optional[slice] = None) -> "Query":
        pass

    def is_empty(self) -> bool:
        return False


class Device(Protocol):
    @property
    @abc.abstractmethod
    def storage(self) -> Storage:
        pass

    @abc.abstractmethod
    def __hash__(self):
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
    def id(self):
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
    def neighbours_ids(self):
        pass

    @property
    @abc.abstractmethod
    def breed(self) -> str:
        pass


def get_storage() -> tuple[StorageProvider, Dict[str, Any]]:
    connectors = storage_connector.get_all()
    return get_connector_from_config("storage", connectors)
