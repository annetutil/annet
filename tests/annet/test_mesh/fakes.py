from typing import Any, Sequence

from annet.mesh.executor import Device
from annet.storage import Storage, Interface


class FakeDevice(Device):
    def __init__(self, name: str, neigbors: list[Device]):
        self._name = name
        self._neighbors = neigbors
        self._storage = None

    @property
    def storage(self) -> Storage:
        return self._storage

    @storage.setter
    def storage(self, storage: Storage) -> None:
        self._storage = storage

    @property
    def id(self):
        return self._name

    @property
    def fqdn(self):
        return self._name

    @property
    def hostname(self):
        return self._name

    def __hash__(self):
        return hash(self._name)

    def is_pc(self):
        return False

    @property
    def hw(self):
        pass

    @property
    def neighbours_ids(self):
        return [n.id for n in self._neighbors]

    @property
    def neighbours(self) -> list["Device"]:
        return self._neighbors

    @property
    def breed(self):
        pass

    def make_lag(self, lag: int, ports: Sequence[str], lag_min_links: int | None) -> Interface:
        pass

    def add_svi(self, svi: int) -> Interface:
        pass

    def add_subif(self, interface: str, subif: int) -> Interface:
        pass


class FakeStorage(Storage):
    def __init__(self):
        self.devices: list[FakeDevice] = []

    def add_device(self, device: FakeDevice):
        self.devices.append(device)

    def __enter__(self):
        pass

    def __exit__(self, _, __, ___):
        pass

    def resolve_object_ids_by_query(self, query: Any):
        pass

    def resolve_all_fdnds(self) -> list[str]:
        return [d.fqdn for d in self.devices]

    def resolve_fdnds_by_query(self, query: Any):
        pass

    def make_devices(self, query: Any, preload_neighbors: bool = False, use_mesh: bool = None,
                     preload_extra_fields=False, **kwargs):
        return [
            d for d in self.devices
            if d.fqdn == query
        ]

    def get_device(self, obj_id, preload_neighbors=False, use_mesh=None, **kwargs) -> "Device":
        raise NotImplementedError()

    def flush_perf(self):
        pass

    def search_connections(self, device: "Device", neighbor: "Device") -> list[tuple["Interface", "Interface"]]:
        return []
