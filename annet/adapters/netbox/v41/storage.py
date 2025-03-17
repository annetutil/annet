import ssl
from adaptix import P
from adaptix.conversion import get_converter, link, link_constant, link_function
from annetbox.v41 import client_sync
from annetbox.v41 import models as api_models

from annet.adapters.netbox.common.adapter import NetboxAdapter, get_device_breed, get_device_hw
from annet.adapters.netbox.common.models import InterfaceT, IpAddressT, NetboxDeviceT, PrefixT
from annet.adapters.netbox.v37.storage import NetboxV37Adapter
from annet.adapters.netbox.v41.models import InterfaceV41, IpAddressV41, NetboxDeviceV41, PrefixV41
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.storage import Storage


class NetboxV41Adapter(NetboxV37Adapter):
    def __init__(
            self,
            storage: Storage,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
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
        self.convert_interface = get_converter(
            api_models.Interface,
            InterfaceV41,
            recipe=[
                link_constant(P[InterfaceV41].ip_addresses, factory=list),
                link_constant(P[InterfaceV41].lag_min_links, value=None),
            ]
        )
        self.convert_ip_address = get_converter(
            api_models.IpAddress,
            IpAddressV41,
            recipe=[
                link_constant(P[IpAddressV41].prefix, value=None),
            ]
        )


class NetboxStorageV41(BaseNetboxStorage[NetboxDeviceV41, InterfaceV41, IpAddressV41, PrefixV41]):
    def _init_adapter(
            self,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
            threads: int,
    ) -> NetboxAdapter[NetboxDeviceT, InterfaceT, IpAddressT, PrefixT]:
        return NetboxV41Adapter(self, url, token, ssl_context, threads)
