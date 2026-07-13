from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from types import TracebackType
from typing import Any, cast

import yaml

from annet.adapters.netbox.common.manufacturer import get_breed
from annet.annlib.netdev.views.dump import DumpableView
from annet.annlib.netdev.views.hardware import HardwareView
from annet.connectors import AdapterWithName
from annet.hardware import hardware_connector
from annet.storage import Device as DeviceProtocol
from annet.storage import DeviceId, Storage, StorageProvider
from annet.storage import Interface as StorageInterface
from annet.storage import Query as QueryProtocol
from annet.storage import StorageOpts as StorageOptsBase


@dataclass
class Interface(DumpableView):
    name: str
    description: str
    enabled: bool = True
    vrf: str | None = None

    @property
    def _dump__list_key(self) -> str:
        return self.name

    def set_vrf(self, vrf: str | None) -> None:
        self.vrf = vrf


@dataclass
class DeviceStorage:
    fqdn: str

    vendor: str | None = None
    hw_model: str | None = None
    sw_version: str | None = None
    breed: str | None = None

    hostname: str | None = None
    serial: str | None = None
    id: str | None = None
    interfaces: list[Interface] | None = None
    storage: Storage | None = None

    hw: HardwareView = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.fqdn
        if not self.hostname:
            self.hostname = self.fqdn.split(".")[0]

        if self.hw_model:
            hw = HardwareView(self.hw_model, self.sw_version)
            if self.vendor and self.vendor != hw.vendor:
                raise Exception(f"Vendor {self.vendor} is not vendor from hw model ({hw.vendor})")
            else:
                self.vendor = hw.vendor
        else:
            if not self.vendor:
                raise Exception("unknown vendor")
            hw_provider = hardware_connector.get()
            hw = hw_provider.vendor_to_hw(self.vendor)
            if not hw:
                raise Exception("unknown vendor")
            self.hw_model = hw.model
        self.hw = hw

        if not self.breed:
            if self.hw.model:
                parts = self.hw.model.split(maxsplit=1)
                if len(parts) >= 2:
                    self.breed = get_breed(parts[0], parts[1])
            if not self.breed:
                self.breed = self.hw.vendor

        if isinstance(self.interfaces, list):
            interfaces = []
            # interfaces arrive as raw dicts from the parsed inventory
            for iface in cast(list[dict[str, Any]], self.interfaces):
                try:
                    interfaces.append(Interface(**iface))
                except Exception as e:
                    raise Exception("unable to parse %s as Interface: %s" % (iface, e))
            self.interfaces = interfaces

    def set_storage(self, storage: Storage) -> None:
        self.storage = storage


@dataclass
class Device(DeviceProtocol, DumpableView):
    dev: DeviceStorage

    def __hash__(self) -> int:
        return hash((self.id, type(self)))

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        return self.fqdn == other.fqdn and self.dev.vendor == other.dev.vendor

    def is_pc(self) -> bool:
        return False

    @property
    def hostname(self) -> str:
        assert self.dev.hostname is not None
        return self.dev.hostname

    @property
    def fqdn(self) -> str:
        return self.dev.fqdn

    @property
    def id(self) -> str:
        assert self.dev.id is not None
        return self.dev.id

    @property
    def storage(self) -> Storage:
        assert self.dev.storage is not None
        return self.dev.storage

    @property
    def hw(self) -> HardwareView:
        return self.dev.hw

    @property
    def breed(self) -> str:
        assert self.dev.breed is not None
        return self.dev.breed

    @property
    def neighbours_ids(self) -> list[DeviceId]:
        return []

    @property
    def neighbours_fqdns(self) -> list[str]:
        return []

    def make_lag(self, lag: int, ports: Sequence[str], lag_min_links: int | None) -> StorageInterface:
        raise NotImplementedError

    def add_svi(self, svi: int) -> StorageInterface:
        raise NotImplementedError

    def add_subif(self, interface: str, subif: int) -> StorageInterface:
        raise NotImplementedError

    def find_interface(self, name: str) -> StorageInterface | None:
        raise NotImplementedError

    def flush_perf(self) -> None:
        pass


@dataclass
class Devices:
    devices: list[Device]

    def __post_init__(self) -> None:
        if isinstance(self.devices, list):
            devices = []

            for dev_params in self.devices:
                if isinstance(dev_params, Device):
                    dev = dev_params
                else:
                    try:
                        dev = Device(dev=DeviceStorage(**dev_params))
                    except Exception as e:
                        raise Exception(f"unable to parse {dev!r} as Device") from e

                devices.append(dev)

            self.devices = devices


class Provider(StorageProvider, AdapterWithName):
    def storage(self) -> type[Storage]:
        return cast("type[Storage]", storage_factory)

    def opts(self) -> type[StorageOptsBase]:
        return cast("type[StorageOptsBase]", StorageOpts)

    def query(self) -> type[Query]:
        return Query

    @classmethod
    def name(cls) -> str:
        return "file"


@dataclass
class Query(QueryProtocol):
    query: list[str]

    @classmethod
    def new(cls, query: str | Iterable[str], hosts_range: slice | None = None) -> Query:
        if hosts_range is not None:
            raise ValueError("host_range is not supported")
        return cls(query=list(query))

    @property
    def globs(self) -> list[str]:
        return self.query

    def is_empty(self) -> bool:
        return len(self.query) == 0


class StorageOpts:
    def __init__(self, path: str):
        self.path = path

    @classmethod
    def parse_params(cls, conf_params: dict[str, str] | None, cli_opts: Any) -> "StorageOpts":
        path = conf_params.get("path") if conf_params else None
        if not path:
            raise Exception("empty path")
        return cls(path=path)


def storage_factory(opts: StorageOpts) -> Storage:
    return FS(opts)


class FS(Storage):
    def __init__(self, opts: StorageOpts):
        self.opts = opts
        self.inventory: Devices = read_inventory(opts.path, self)

    def __enter__(self) -> FS:
        return self

    def __exit__(
        self,
        _: type[BaseException] | None,
        __: BaseException | None,
        ___: TracebackType | None,
    ) -> bool | None:
        pass

    def resolve_object_ids_by_query(self, query: Query) -> list[str]:
        result = filter_query(self.inventory.devices, query)
        return [dev.fqdn for dev in result]

    def resolve_fdnds_by_query(self, query: Query) -> list[str]:
        result = filter_query(self.inventory.devices, query)
        return [dev.fqdn for dev in result]

    def make_devices(
        self,
        query: Query | list[str],
        preload_neighbors: bool = False,
        use_mesh: bool | None = None,
        preload_extra_fields: bool = False,
        **kwargs: Any,
    ) -> list[Device]:
        if isinstance(query, list):
            query = Query.new(query)
        result = filter_query(self.inventory.devices, query)
        return result

    def get_device(
        self, obj_id: str, preload_neighbors: bool = False, use_mesh: bool | None = None, **kwargs: Any
    ) -> Device:
        result = filter_query(self.inventory.devices, Query.new(obj_id))
        if not result:
            raise Exception("not found")
        return result[0]

    def flush_perf(self) -> None:
        pass

    def resolve_all_fdnds(self) -> list[str]:
        return [d.fqdn for d in self.inventory.devices]

    def search_connections(
        self, device: DeviceProtocol, neighbor: DeviceProtocol
    ) -> list[tuple[StorageInterface, StorageInterface]]:
        return []


def filter_query(devices: list[Device], query: Query) -> list[Device]:
    result: list[Device] = []
    for dev in devices:
        if dev.fqdn in query.query:
            result.append(dev)
    return result


def read_inventory(path: str, storage: Storage) -> Devices:
    with open(path, "r") as f:
        file_data = yaml.load(f, Loader=yaml.SafeLoader)
    res = cast(Devices, dataclass_from_dict(Devices, file_data))
    for dev in res.devices:
        dev.dev.set_storage(storage)
    return res


def dataclass_from_dict(klass: type, d: dict[str, Any]) -> Any:
    try:
        fieldtypes = {f.name: f.type for f in fields(klass)}
    except TypeError:
        return d
    return klass(**{f: dataclass_from_dict(cast(type, fieldtypes[f]), d[f]) for f in d})
