from typing import Any, Optional, Sequence

from annet.mesh.executor import Device
from annet.storage import Storage, Interface


class FakeInterface(Interface):
    def __init__(self, name: str, neighbor_fqdn: Optional[str], neighbor_port: Optional[str]):
        self._name = name
        self.addrs: list[tuple[str, Optional[str]]] = []
        self.neighbor_fqdn = neighbor_fqdn
        self.neighbor_port = neighbor_port

    @property
    def name(self) -> str:
        return self._name

    def add_addr(self, address_mask: str, vrf: Optional[str]) -> None:
        self.addrs.append((address_mask, vrf))


class FakeDevice(Device):
    def __init__(self, name: str, interfaces: list[FakeInterface]) -> None:
        self._name = name
        self.interfaces = interfaces
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
    def neighbours_ids(self) -> list["str"]:
        return list({n.neighbor_fqdn for n in self.interfaces if n.neighbor_fqdn})

    @property
    def neighbours_fqdns(self) -> list["str"]:
        return list({n.neighbor_fqdn for n in self.interfaces if n.neighbor_fqdn})

    @property
    def breed(self):
        pass

    def make_lag(self, lag: int, ports: Sequence[str], lag_min_links: Optional[int]) -> Interface:
        self.interfaces.append(FakeInterface(
            name=f"Trunk{lag}",
            neighbor_port=None,
            neighbor_fqdn=None,
        ))
        return self.interfaces[-1]

    def add_svi(self, svi: int) -> Interface:
        self.interfaces.append(FakeInterface(
            name=f"Vlan{svi}",
            neighbor_port=None,
            neighbor_fqdn=None,
        ))
        return self.interfaces[-1]

    def add_subif(self, interface: str, subif: int) -> Interface:
        self.interfaces.append(FakeInterface(
            name=f"{interface}.{subif}",
            neighbor_port=None,
            neighbor_fqdn=None,
        ))
        return self.interfaces[-1]

    def find_interface(self, name: str) -> Optional[Interface]:
        for iface in self.interfaces:
            if iface.name == name:
                return iface
        return None


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
        return [
            d.id for d in self.devices
            if d.fqdn in query
        ]

    def resolve_all_fdnds(self) -> list[str]:
        return [d.fqdn for d in self.devices]

    def resolve_fdnds_by_query(self, query: Any):
        return [
            d.fqdn for d in self.devices
            if d.fqdn in query
        ]

    def make_devices(self, query: Any, preload_neighbors: bool = False, use_mesh: Optional[bool] = None,
                     preload_extra_fields=False, **kwargs):
        return [
            d for d in self.devices
            if d.fqdn in query
        ]

    def get_device(self, obj_id, preload_neighbors=False, use_mesh=None, **kwargs) -> "Device":
        return next(d for d in self.devices if d.id == obj_id)

    def flush_perf(self):
        pass

    def search_connections(
        self, device: "FakeDevice", neighbor: "FakeDevice",
    ) -> list[tuple["FakeInterface", "FakeInterface"]]:
        res = []
        for local_port in device.interfaces:
            if local_port.neighbor_fqdn == neighbor.fqdn:
                for remote_port in neighbor.interfaces:
                    if remote_port.name == local_port.neighbor_port:
                        res.append((local_port, remote_port))
        return res