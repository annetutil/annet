import abc
from typing import Any, Iterable, Optional, Type, Union, Protocol, Dict
from annet.connectors import Connector, get_context


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


def get_storage() -> (Storage, Dict[str, Any]):
    connectors = storage_connector.get_all()
    seen: list[str] = []
    if context_storage := get_context().get("storage"):
        for connector in connectors:
            con_name = connector.name()
            seen.append(con_name)
            if "adapter" not in context_storage:
                raise Exception("adapter is not set in %s" % context_storage)
            if context_storage["adapter"] == con_name:
                return connector, context_storage.get("params", {})
        else:
            raise Exception("unknown storage %s: seen %s" % (context_storage["adapter"], seen))
    else:
        return connectors[0], {}
