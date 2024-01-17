import abc
from typing import Any, Iterable, Optional, Type, Union


try:
    from annet.connectors import Connector
except ImportError:
    from noc.annushka.annet.connectors import Connector  # noqa: F401


class _StorageConnector(Connector["StorageProvider"]):
    name = "Storage"
    ep_name = "storage"


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
    def from_cli_opts(cls, cli_opts) -> "StorageOpts":
        pass


class Query(abc.ABC):
    @classmethod
    @abc.abstractclassmethod
    def new(cls, query: Union[str, Iterable[str]], hosts_range: Optional[slice] = None) -> "Query":
        pass


class Device(abc.ABC):
    @abc.abstractmethod
    def __hash__(self):
        pass

    @abc.abstractmethod
    def is_pc(self):
        pass

    @property
    @abc.abstractmethod
    def hw(self):
        pass

    @property
    @abc.abstractmethod
    def id(self):
        pass

    @property
    @abc.abstractmethod
    def fqdn(self):
        pass

    @property
    @abc.abstractmethod
    def hostname(self):
        pass

    @property
    @abc.abstractmethod
    def neighbours_ids(self):
        pass

    @property
    @abc.abstractmethod
    def breed(self):
        pass
