import ssl

from adaptix import P
from adaptix.conversion import get_converter, link_function, link_constant, link
from annetbox.v37 import models as api_models, client_sync

from annet.adapters.netbox.common.adapter import NetboxAdapter, get_device_breed, get_device_hw
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.storage import Storage
from .models import IpAddressV37, NetboxDeviceV37, InterfaceV37, PrefixV37


class NetboxV37Adapter(NetboxAdapter[NetboxDeviceV37, InterfaceV37, IpAddressV37, PrefixV37]):
    def __init__(
            self,
            storage: Storage,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext | None,
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
        self.convert_interfaces = get_converter(
            list[api_models.Interface],
            list[InterfaceV37],
            recipe=[
                link_constant(P[InterfaceV37].ip_addresses, factory=list),
                link_constant(P[InterfaceV37].lag_min_links, value=None),
            ]
        )
        self.convert_ip_addresses = get_converter(
            list[api_models.IpAddress],
            list[IpAddressV37],
            recipe=[
                link_constant(P[IpAddressV37].prefix, value=None),
            ]
        )
        self.convert_ip_prefixes = get_converter(
            list[api_models.Prefix],
            list[PrefixV37],
        )

    def list_all_fqdns(self) -> list[str]:
        return [
            d.name
            for d in self.netbox.dcim_all_devices_brief().results
        ]

    def list_devices(self, query: dict[str, list[str]]) -> list[NetboxDeviceV37]:
        return [
            self.convert_device(dev)
            for dev in self.netbox.dcim_all_devices(**query).results
        ]

    def get_device(self, device_id: int) -> NetboxDeviceV37:
        return self.convert_device(self.netbox.dcim_device(device_id))

    def list_interfaces_by_devices(self, device_ids: list[int]) -> list[InterfaceV37]:
        return self.convert_interfaces(self.netbox.dcim_all_interfaces(device_id=device_ids).results)

    def list_interfaces(self, ids: list[int]) -> list[InterfaceV37]:
        return self.convert_interfaces(self.netbox.dcim_all_interfaces(id=ids).results)

    def list_ipaddr_by_ifaces(self, iface_ids: list[int]) -> list[IpAddressV37]:
        return self.convert_ip_addresses(self.netbox.ipam_all_ip_addresses(interface_id=iface_ids).results)

    def list_ipprefixes(self, prefixes: list[str]) -> list[PrefixV37]:
        return self.convert_ip_prefixes(self.netbox.ipam_all_prefixes(prefix=prefixes).results)


class NetboxStorageV37(BaseNetboxStorage[NetboxDeviceV37, InterfaceV37, IpAddressV37, PrefixV37]):
    def _init_adapter(
            self,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext | None,
            threads: int,
    ) -> NetboxAdapter[NetboxDeviceV37, InterfaceV37, IpAddressV37, PrefixV37]:
        return NetboxV37Adapter(self, url, token, ssl_context, threads)
