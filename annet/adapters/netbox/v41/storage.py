import ssl
from adaptix import P
from adaptix.conversion import get_converter, link, link_constant, link_function
from annetbox.v41 import client_sync
from annetbox.v41 import models as api_models

from annet.adapters.netbox.common.adapter import NetboxAdapter, get_device_breed, get_device_hw
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.adapters.netbox.v41.models import InterfaceV41, IpAddressV41, NetboxDeviceV41, PrefixV41
from annet.storage import Storage


class NetboxV41Adapter(NetboxAdapter[NetboxDeviceV41, InterfaceV41, IpAddressV41, PrefixV41]):
    def __init__(
            self,
            storage: Storage,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext | None,
            threads: int,
    ):
        self.netbox = client_sync.NetboxV41(url=url, token=token, ssl_context=ssl_context, threads=threads)
        self.convert_device = get_converter(
            api_models.Device,
            NetboxDeviceV41,
            recipe=[
                link_function(get_device_breed, P[NetboxDeviceV41].breed),
                link_function(get_device_hw, P[NetboxDeviceV41].hw),
                link_constant(P[NetboxDeviceV41].interfaces, factory=list),
                link_constant(P[NetboxDeviceV41].storage, value=storage),
                link(P[api_models.Device].name, P[NetboxDeviceV41].hostname),
                link(P[api_models.Device].name, P[NetboxDeviceV41].fqdn),
            ]
        )
        self.convert_interfaces = get_converter(
            list[api_models.Interface],
            list[InterfaceV41],
            recipe=[
                link_constant(P[InterfaceV41].ip_addresses, factory=list),
                link_constant(P[InterfaceV41].lag_min_links, value=None),
            ]
        )
        self.convert_ip_addresses = get_converter(
            list[api_models.IpAddress],
            list[IpAddressV41],
            recipe=[
                link_constant(P[IpAddressV41].prefix, value=None),
            ]
        )
        self.convert_ip_prefixes = get_converter(
            list[api_models.Prefix],
            list[PrefixV41],
        )

    def list_all_fqdns(self) -> list[str]:
        return [
            d.name
            for d in self.netbox.dcim_all_devices_brief().results
        ]

    def list_devices(self, query: dict[str, list[str]]) -> list[NetboxDeviceV41]:
        return [
            self.convert_device(dev)
            for dev in self.netbox.dcim_all_devices(**query).results
        ]

    def get_device(self, device_id: int) -> NetboxDeviceV41:
        return self.convert_device(self.netbox.dcim_device(device_id))

    def list_interfaces_by_devices(self, device_ids: list[int]) -> list[InterfaceV41]:
        return self.convert_interfaces(self.netbox.dcim_all_interfaces(device_id=device_ids).results)

    def list_interfaces(self, ids: list[int]) -> list[InterfaceV41]:
        return self.convert_interfaces(self.netbox.dcim_all_interfaces(id=ids).results)

    def list_ipaddr_by_ifaces(self, iface_ids: list[int]) -> list[IpAddressV41]:
        return self.convert_ip_addresses(self.netbox.ipam_all_ip_addresses(interface_id=iface_ids).results)

    def list_ipprefixes(self, prefixes: list[str]) -> list[PrefixV41]:
        return self.convert_ip_prefixes(self.netbox.ipam_all_prefixes(prefix=prefixes).results)


class NetboxStorageV41(BaseNetboxStorage[NetboxDeviceV41, InterfaceV41, IpAddressV41, PrefixV41]):
    def _init_adapter(
            self,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext | None,
            threads: int,
    ) -> NetboxAdapter[NetboxDeviceV41, InterfaceV41, IpAddressV41, PrefixV41]:
        return NetboxV41Adapter(self, url, token, ssl_context, threads)
