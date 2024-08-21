from annet.storage import Query
from dataclasses import dataclass, fields
from typing import List, Iterable, Any
from annet.storage import StorageProvider, Storage
from annet.annlib.netdev.views.hardware import vendor_to_hw
import yaml


@dataclass
class Interface:
    name: str
    description: str
    enabled: bool = True


@dataclass
class Device:
    fqdn: str
    vendor: str
    hostname: str | None = None
    serial: str | None = None
    id: str | None = None
    interfaces: list[Interface] | None = None

    def __hash__(self):
        return hash((self.id, type(self)))

    def __eq__(self, other):
        return type(self) is type(other) and self.fqdn == other.fqdn and self.vendor == other.vendor

    def __post_init__(self):
        if not self.id:
            self.id = self.fqdn
        if not self.hostname:
            self.hostname = self.fqdn.split(".")[0]
        hw = vendor_to_hw(self.vendor)
        if not hw:
            raise Exception("unknown vendor")
        self.hw = hw
        if isinstance(self.interfaces, list):
            interfaces = []
            for iface in self.interfaces:
                try:
                    interfaces.append(Interface(**iface))
                except Exception as e:
                    raise Exception("unable to parse %s as Interface %s" % (iface, e))
            self.interfaces = interfaces

    def is_pc(self):
        return False


@dataclass
class Devices:
    devices: list[Device]

    def __post_init__(self):
        if isinstance(self.devices, list):
            devices = []
            for dev in self.devices:
                try:
                    devices.append(Device(**dev))
                except Exception as e:
                    raise Exception("unable to parse %s as Device %s" % (dev, e))
            self.devices = devices


class Provider(StorageProvider):
    def storage(self):
        return storage_factory

    def opts(self):
        return StorageOpts

    def query(self):
        return Query

    def name(self) -> str:
        return "file"


@dataclass
class Query(Query):
    query: List[str]

    @classmethod
    def new(cls, query: str | Iterable[str], hosts_range: slice | None = None) -> "Query":
        if hosts_range is not None:
            raise ValueError("host_range is not supported")
        return cls(query=list(query))

    @property
    def globs(self):
        return self.query


class StorageOpts:
    def __init__(self, path: str):
        self.path = path

    @classmethod
    def parse_params(cls, conf_params: dict[str, str] | None, cli_opts: Any):
        path = conf_params.get("path")
        if not path:
            raise Exception("empty path")
        return cls(path=path)


def storage_factory(opts: StorageOpts) -> Storage:
    return FS(opts)


class FS(Storage):
    def __init__(self, opts: StorageOpts):
        self.opts = opts
        self.inventory: Devices = read_inventory(opts.path, self)

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        pass

    def resolve_object_ids_by_query(self, query: Query) -> list[str]:
        result = filter_query(self.inventory.devices, query)
        return [dev.fqdn for dev in result]

    def resolve_fdnds_by_query(self, query: Query) -> list[str]:
        result = filter_query(self.inventory.devices, query)
        return [dev.fqdn for dev in result]

    def make_devices(
            self,
            query: Query | list,
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> list[Device]:
        if isinstance(query, list):
            query = Query.new(query)
        result = filter_query(self.inventory.devices, query)
        return result

    def get_device(self, obj_id: str, preload_neighbors=False, use_mesh=None, **kwargs) -> Device:
        result = filter_query(self.inventory.devices, Query.new(obj_id))
        if not result:
            raise Exception("not found")
        return result[0]

    def flush_perf(self):
        pass


def filter_query(devices: list[Device], query: Query) -> list[Device]:
    result: list[Device] = []
    for dev in devices:
        if dev.fqdn in query.query:
            result.append(dev)
    return result


def read_inventory(path: str, storage: Storage) -> Devices:
    with open(path, "r") as f:
        data = f.read()
    file_data = yaml.load(data, Loader=yaml.BaseLoader)
    res = dataclass_from_dict(Devices, file_data)
    for dev in res.devices:
        dev.storage = storage
    return res


def dataclass_from_dict(klass: type, d: dict[str, Any]):
    try:
        fieldtypes = {f.name: f.type for f in fields(klass)}
    except TypeError:
        return d
    return klass(**{f: dataclass_from_dict(fieldtypes[f], d[f]) for f in d})
