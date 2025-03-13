import ssl

from adaptix import P
from adaptix.conversion import get_converter, link_function, link_constant, link
from annetbox.v37 import models as api_models, client_sync

from annet.adapters.netbox.common.adapter import NetboxAdapter, get_device_breed, get_device_hw
from annet.adapters.netbox.common.models import Prefix, IpAddressT, InterfaceT, NetboxDeviceT
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.storage import Storage
from .models import IpAddressV37, NetboxDeviceV37, InterfaceV37


class NetboxV37Adapter(NetboxAdapter[NetboxDeviceV37, InterfaceV37, IpAddressV37]):
    def __init__(
            self,
            storage: Storage,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
            threads: int,
    ):
        self.netbox = client_sync.NetboxV37(url=url, token=token, ssl_context=ssl_context, threads=threads)
        self.convert_device = get_converter(
            api_models.Device,
            NetboxDeviceV37,
            recipe=[
                link_function(get_device_breed, P[NetboxDeviceV37].breed),
                link_function(get_device_hw, P[NetboxDeviceV37].hw),
                link_constant(P[NetboxDeviceV37].interfaces, factory=list),
                link_constant(P[NetboxDeviceV37].storage, value=storage),
                link(P[api_models.Device].name, P[NetboxDeviceV37].hostname),
                link(P[api_models.Device].name, P[NetboxDeviceV37].fqdn),
            ]
        )
        self.convert_interface = get_converter(
            api_models.Interface,
            InterfaceV37,
            recipe=[
                link_constant(P[InterfaceV37].ip_addresses, factory=list),
                link_constant(P[InterfaceV37].lag_min_links, value=None),
            ]
        )
        self.convert_ip_address = get_converter(
            api_models.IpAddress,
            IpAddressV37,
            recipe=[
                link_constant(P[IpAddressV37].prefix, value=None),
            ]
        )

    def list_all_fqdns(self) -> list[str]:
        return [
            d.name
            for d in self.netbox.dcim_all_devices_brief().results
        ]

    def list_devices(self, query: dict[str, list[str]]) -> list[NetboxDeviceT]:
        return [
            self.convert_device(dev)
            for dev in self.netbox.dcim_all_devices(**query).results
        ]

    def get_device(self, device_id: int) -> NetboxDeviceT:
        return self.convert_device(self.netbox.dcim_device(device_id))

    def list_interfaces_by_devices(self, device_ids: list[int]) -> list[InterfaceT]:
        return [
            self.convert_interface(interface)
            for interface in self.netbox.dcim_all_interfaces(device_id=device_ids).results
        ]

    def list_interfaces(self, ids: list[int]) -> list[InterfaceT]:
        return [
            self.convert_interface(interface)
            for interface in self.netbox.dcim_all_interfaces(id=ids).results
        ]

    def list_ipaddr_by_ifaces(self, iface_ids: list[int]) -> list[IpAddressT]:
        return [
            self.convert_ip_address(ipaddress)
            for ipaddress in self.netbox.ipam_all_ip_addresses(interface_id=iface_ids).results
        ]

    def list_ipprefixes(self, prefixes: list[str]) -> list[Prefix]:
        return self.netbox.ipam_all_prefixes(prefix=prefixes).results


class NetboxStorageV37(BaseNetboxStorage[NetboxDeviceV37, InterfaceV37, IpAddressV37]):
    def _init_adapter(
            self,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
            threads: int,
    ) -> NetboxAdapter[NetboxDeviceT, InterfaceT, IpAddressT]:
        return NetboxV37Adapter(self, url, token, ssl_context, threads)
