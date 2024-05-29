from logging import getLogger
from typing import Optional, List, Union, Dict
from ipaddress import ip_interface
from collections import defaultdict

from adaptix import P
from adaptix.conversion import impl_converter, link
from annetbox.v37 import models as api_models
from annetbox.v37.client_sync import NetboxV37

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    is_supported, get_hw, get_breed,
)
from annet.adapters.netbox.common.query import NetboxQuery
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage


logger = getLogger(__name__)


@impl_converter(recipe=[
    link(P[api_models.Device].name, P[models.NetboxDevice].hostname),
    link(P[api_models.Device].name, P[models.NetboxDevice].fqdn),
])
def extend_device_base(
        device: api_models.Device,
        interfaces: List[models.Interface],
        hw: Optional[HardwareView],
        breed: str,
        neighbours: Optional[List[models.NetboxDevice]],
        storage: Storage,
) -> models.NetboxDevice:
    ...


def extend_device(
        device: api_models.Device,
        interfaces: List[models.Interface],
        neighbours: Optional[List[models.NetboxDevice]],
        storage: Storage,
) -> models.NetboxDevice:
    return extend_device_base(
        device=device,
        interfaces=interfaces,
        breed=get_breed(
            device.device_type.manufacturer.name,
            device.device_type.model,
        ),
        hw=get_hw(
            device.device_type.manufacturer.name,
            device.device_type.model,
        ),
        neighbours=neighbours,
        storage=storage,
    )


@impl_converter
def extend_interface(
        interface: api_models.Interface,
        ip_addresses: List[models.IpAddress],
) -> models.Interface:
    ...


@impl_converter
def extend_ip_address(
        ip_address: models.IpAddress, prefix: Optional[models.Prefix],
) -> models.IpAddress:
    ...


class NetboxStorageV37(Storage):
    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        self.netbox = NetboxV37(
            url=opts.url,
            token=opts.token,
        )

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        pass

    def resolve_object_ids_by_query(self, query: NetboxQuery):
        return [
            d.id for d in self._load_devices(query)
        ]

    def resolve_fdnds_by_query(self, query: NetboxQuery):
        return [
            d.name for d in self._load_devices(query)
        ]

    def make_devices(
            self,
            query: Union[NetboxQuery, list],
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> List[models.NetboxDevice]:
        if isinstance(query, list):
            query = NetboxQuery.new(query)
        device_ids = {
            device.id: extend_device(
                device=device,
                interfaces=[],
                neighbours=[],
                storage=self,
            )
            for device in self._load_devices(query)
        }
        if not device_ids:
            return []

        interfaces = self._load_interfaces(list(device_ids))
        neighbours = {x.id: x for x in self._load_neighbours(interfaces)}
        neighbours_seen = defaultdict(set)

        for interface in interfaces:
            device_ids[interface.device.id].interfaces.append(interface)
            for e in interface.connected_endpoints or []:
                neighbour = neighbours[e.device.id]
                if neighbour.id not in neighbours_seen[interface.device.id]:
                    neighbours_seen[interface.device.id].add(neighbour.id)
                    device_ids[interface.device.id].neighbours.append(neighbour)

        return list(device_ids.values())

    def _load_devices(self, query: NetboxQuery) -> List[api_models.Device]:
        if not query.globs:
            return []
        return [
            device
            for device in self.netbox.dcim_all_devices(
                name__ic=query.globs,
            ).results
            if _match_query(query, device)
            if is_supported(device.device_type.manufacturer.name)
        ]

    def _extend_interfaces(self, interfaces: List[models.Interface]) -> List[models.Interface]:
        extended_ifaces = {
            interface.id: extend_interface(interface, [])
            for interface in interfaces
        }

        ips = self.netbox.ipam_all_ip_addresses(interface_id=list(extended_ifaces))
        ip_to_cidrs: Dict[str, str] = {ip.address: str(ip_interface(ip.address).network) for ip in ips.results}
        prefixes = self.netbox.ipam_all_prefixes(prefix=list(ip_to_cidrs.values()))
        cidr_to_prefix: Dict[str, models.Prefix] = {x.prefix: x for x in prefixes.results}

        for ip in ips.results:
            cidr = ip_to_cidrs[ip.address]
            ip = extend_ip_address(ip, prefix=cidr_to_prefix.get(cidr))
            extended_ifaces[ip.assigned_object_id].ip_addresses.append(ip)
        return list(extended_ifaces.values())

    def _load_interfaces(self, device_ids: List[int]) -> List[
        models.Interface]:
        interfaces = self.netbox.dcim_all_interfaces(device_id=device_ids)
        return self._extend_interfaces(interfaces.results)

    def _load_interfaces_by_id(self, ids: List[int]) -> List[models.Interface]:
        interfaces = self.netbox.dcim_all_interfaces_by_id(id=ids)
        return self._extend_interfaces(interfaces.results)

    def _load_neighbours(self, interfaces: List[models.Interface]) -> List[models.NetboxDevice]:
        endpoints = [e for i in interfaces for e in i.connected_endpoints or []]
        remote_interfaces_ids = [e.id for e in endpoints]
        neighbours_ids = [e.device.id for e in endpoints]
        neighbours_ifaces_dics = defaultdict(list)
        # load only the connected interface to speed things up
        for iface in self._load_interfaces_by_id(remote_interfaces_ids):
            neighbours_ifaces_dics[iface.device.id].append(iface)
        neighbours = []
        for neighbour in self.netbox.dcim_all_devices_by_id(id=neighbours_ids).results:
            extended_neighbour = extend_device(
                device=neighbour,
                storage=self,
                interfaces=neighbours_ifaces_dics[neighbour.id],
                neighbours=None,  # do not load recursively
            )
            neighbours.append(extended_neighbour)
        return neighbours

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> models.NetboxDevice:
        device = self.netbox.dcim_device(obj_id)
        interfaces = self._load_interfaces([device.id])
        neighbours = self._load_neighbours(interfaces)

        res = extend_device(
            device=device,
            storage=self,
            interfaces=interfaces[device.id],
            neighbours=neighbours,
        )
        return res

    def flush_perf(self):
        pass


def _match_query(query: NetboxQuery, device_data: api_models.Device) -> bool:
    for subquery in query.globs:
        if subquery.strip() in device_data.name:
            return True
    return False
