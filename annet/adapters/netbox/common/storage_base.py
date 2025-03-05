import ssl
from ipaddress import ip_interface
from logging import getLogger
from typing import Any, Optional, List, Union, Dict, cast

from adaptix import P
from adaptix.conversion import impl_converter, link, link_constant
from annetbox.v37 import models as api_models

from annet.adapters.netbox.common import models
from annet.adapters.netbox.common.manufacturer import (
    get_hw, get_breed,
)
from annet.adapters.netbox.common.query import NetboxQuery, FIELD_VALUE_SEPARATOR
from annet.adapters.netbox.common.storage_opts import NetboxStorageOpts
from annet.annlib.netdev.views.hardware import HardwareView
from annet.storage import Storage, Device, Interface


logger = getLogger(__name__)


class BaseNetboxStorage(Storage):
    """
    Base class for Netbox storage adapters.
    Attributes:
        netbox_class: The Netbox class to use for API interactions from Annetbox.
        api_models: The API models used by the storage from Annetbox.
        device_model: The model for Netbox devices.
        prefix_model: The model for Netbox prefixes.
        interface_model: The model for Netbox interfaces.
        ipaddress_model: The model for Netbox IP addresses.
    """
    netbox_class = None
    api_models = api_models
    device_model = models.NetboxDevice
    prefix_model = models.Prefix
    interface_model = models.Interface
    ipaddress_model = models.IpAddress

    def __init__(self, opts: Optional[NetboxStorageOpts] = None):
        ctx: Optional[ssl.SSLContext] = None
        url = ""
        token = ""
        self.exact_host_filter = False
        threads = 1
        if opts:
            if opts.insecure:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            url = opts.url
            token = opts.token
            threads = opts.threads
            self.exact_host_filter = opts.exact_host_filter

        if self.netbox_class is None:
            raise ValueError("netbox_class is not set in the derived class")
        self.netbox = self.netbox_class(url=url, token=token, ssl_context=ctx, threads=threads)
        self._initialize_impl_converter_methods()
        self._all_fqdns: Optional[list[str]] = None
        self._id_devices: dict[int, self.device_model] = {}
        self._name_devices: dict[str, self.device_model] = {}
        self._short_name_devices: dict[str, self.device_model] = {}

    def _initialize_impl_converter_methods(self):
        @impl_converter(recipe=[
            link(P[self.api_models.Device].name, P[self.device_model].hostname),
            link(P[self.api_models.Device].name, P[self.device_model].fqdn),
        ])
        def extend_device_base(
                device: self.api_models.Device,
                interfaces: List[self.interface_model],
                hw: Optional[HardwareView],
                breed: str,
                storage: Storage,
        ) -> self.device_model:
            ...

        def extend_device(
                device: self.api_models.Device,
                interfaces: List[self.interface_model],
                storage: Storage,
        ) -> self.device_model:
            platform_name: str = ""
            breed: str = ""
            hw = HardwareView("", "")
            if device.platform:
                platform_name = device.platform.name
            if device.device_type and device.device_type.manufacturer:
                breed = get_breed(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                )
                hw = get_hw(
                    device.device_type.manufacturer.name,
                    device.device_type.model,
                    platform_name,
                )
            res = extend_device_base(
                device=device,
                interfaces=interfaces,
                breed=breed,
                hw=hw,
                storage=storage,
            )
            return res

        @impl_converter(
            recipe=[link_constant(P[self.interface_model].lag_min_links, value=None)],
        )
        def extend_interface(
                interface: self.api_models.Interface,
                ip_addresses: List[self.ipaddress_model],
        ) -> self.interface_model:
            ...

        @impl_converter
        def extend_ip_address(
                ip_address: self.ipaddress_model, prefix: Optional[self.prefix_model],
        ) -> self.ipaddress_model:
            ...

        self.extend_device_base = extend_device_base
        self.extend_device = extend_device
        self.extend_interface = extend_interface
        self.extend_ip_address = extend_ip_address

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

    def resolve_all_fdnds(self) -> list[str]:
        if self._all_fqdns is None:
            self._all_fqdns = [
                d.name
                for d in self.netbox.dcim_all_devices_brief().results
            ]
        return self._all_fqdns

    def make_devices(
            self,
            query: Union[NetboxQuery, list],
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> List[device_model]:
        if isinstance(query, list):
            query = NetboxQuery.new(query)

        devices = []
        if query.is_host_query():
            globs = []
            for glob in query.globs:
                if glob in self._name_devices:
                    devices.append(self._name_devices[glob])
                if glob in self._short_name_devices:
                    devices.append(self._short_name_devices[glob])
                else:
                    globs.append(glob)
            if not globs:
                return devices
            query = NetboxQuery.new(globs)

        return devices + self._make_devices(
            query=query,
            preload_neighbors=preload_neighbors,
            use_mesh=use_mesh,
            preload_extra_fields=preload_extra_fields,
            **kwargs
        )

    def _make_devices(
            self,
            query: NetboxQuery,
            preload_neighbors=False,
            use_mesh=None,
            preload_extra_fields=False,
            **kwargs,
    ) -> List[device_model]:
        device_ids = {
            device.id: self.extend_device(
                device=device,
                interfaces=[],
                storage=self,
            )
            for device in self._load_devices(query)
        }
        if not device_ids:
            return []

        for device in device_ids.values():
            self._record_device(device)

        interfaces = self._load_interfaces(list(device_ids))
        for interface in interfaces:
            device_ids[interface.device.id].interfaces.append(interface)

        return list(device_ids.values())

    def _record_device(self, device: device_model):
        self._id_devices[device.id] = device
        self._short_name_devices[device.name] = device
        if not self.exact_host_filter:
            short_name = device.name.split(".")[0]
            self._short_name_devices[short_name] = device

    def _load_devices(self, query: NetboxQuery) -> List[api_models.Device]:
        if not query.globs:
            return []
        query_groups = parse_glob(self.exact_host_filter, query)
        return [
            device
            for device in self.netbox.dcim_all_devices(**query_groups).results
            if _match_query(self.exact_host_filter, query, device)
        ]

    def _extend_interfaces(self, interfaces: List[interface_model]) -> List[interface_model]:
        extended_ifaces = {
            interface.id: self.extend_interface(interface, [])
            for interface in interfaces
        }

        ips = self.netbox.ipam_all_ip_addresses(interface_id=list(extended_ifaces))
        ip_to_cidrs: Dict[str, str] = {ip.address: str(ip_interface(ip.address).network) for ip in ips.results}
        prefixes = self.netbox.ipam_all_prefixes(prefix=list(ip_to_cidrs.values()))
        cidr_to_prefix: Dict[str, models.Prefix] = {x.prefix: x for x in prefixes.results}

        for ip in ips.results:
            cidr = ip_to_cidrs[ip.address]
            ip = self.extend_ip_address(ip, prefix=cidr_to_prefix.get(cidr))
            extended_ifaces[ip.assigned_object_id].ip_addresses.append(ip)
        return list(extended_ifaces.values())

    def _load_interfaces(self, device_ids: List[int]) -> List[interface_model]:
        interfaces = self.netbox.dcim_all_interfaces(device_id=device_ids)
        return self._extend_interfaces(interfaces.results)

    def _load_interfaces_by_id(self, ids: List[int]) -> List[interface_model]:
        interfaces = self.netbox.dcim_all_interfaces_by_id(id=ids)
        return self._extend_interfaces(interfaces.results)

    def get_device(
            self, obj_id, preload_neighbors=False, use_mesh=None,
            **kwargs,
    ) -> device_model:
        if obj_id in self._id_devices:
            return self._id_devices[obj_id]

        device = self.netbox.dcim_device(obj_id)
        interfaces = self._load_interfaces([device.id])

        res = self.extend_device(
            device=device,
            storage=self,
            interfaces=interfaces,
        )
        self._record_device(res)
        return res

    def flush_perf(self):
        pass

    def search_connections(self, device: Device, neighbor: Device) -> list[tuple[Interface, Interface]]:
        if device.storage is not self:
            raise ValueError("device does not belong to this storage")
        if neighbor.storage is not self:
            raise ValueError("neighbor does not belong to this storage")
        # both devices are NetboxDevice if they are loaded from this storage
        res = []
        for local_port in device.interfaces:
            if not local_port.connected_endpoints:
                continue
            for endpoint in local_port.connected_endpoints:
                if endpoint.device.id == neighbor.id:
                    for remote_port in neighbor.interfaces:
                        if remote_port.name == endpoint.name:
                            res.append((local_port, remote_port))
                            break
        return res


def _match_query(exact_host_filter: bool, query: NetboxQuery, device_data: api_models.Device) -> bool:
    """
    Additional filtering after netbox due to limited backend logic.
    """
    if exact_host_filter:
        return True  # nothing to check, all filtering is done by netbox
    hostnames = [subquery.strip() for subquery in query.globs if FIELD_VALUE_SEPARATOR not in subquery]
    if not hostnames:
        return True  # no hostnames to check

    short_name = device_data.name.split(".")[0]
    for hostname in hostnames:
        hostname = hostname.strip().rstrip(".")
        if short_name == hostname or device_data.name == hostname:
            return True
    return False


def _hostname_dot_hack(raw_query: str) -> str:
    # there is no proper way to lookup host by its hostname
    # ie find "host" with fqdn "host.example.com"
    # besides using name__ic (ie startswith)
    # since there is no direct analogue for this field in netbox
    # so we need to add a dot to hostnames (top-level fqdn part)
    # so we would not receive devices with a common name prefix
    def add_dot(raw_query: Any) -> Any:
        if isinstance(raw_query, str) and "." not in raw_query:
            raw_query = raw_query + "."
        return raw_query

    if isinstance(raw_query, list):
        for i, name in enumerate(raw_query):
            raw_query[i] = add_dot(name)
    elif isinstance(raw_query, str):
        raw_query = add_dot(raw_query)

    return raw_query


def parse_glob(exact_host_filter: bool, query: NetboxQuery) -> dict[str, list[str]]:
    query_groups = cast(dict[str, list[str]], query.parse_query())
    if names := query_groups.pop("name", None):
        if exact_host_filter:
            query_groups["name__ie"] = names
        else:
            query_groups["name__ic"] = [_hostname_dot_hack(name) for name in names]
    return query_groups
