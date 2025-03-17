import ssl
from adaptix import P
from adaptix.conversion import get_converter, link, link_constant, link_function
from annetbox.v42 import client_sync
from annetbox.v42 import models as api_models

from annet.adapters.netbox.common.adapter import NetboxAdapter, get_device_breed, get_device_hw
from annet.adapters.netbox.common.models import InterfaceT, IpAddressT, NetboxDeviceT, PrefixT
from annet.adapters.netbox.common.storage_base import BaseNetboxStorage
from annet.adapters.netbox.v37.storage import NetboxV37Adapter
from annet.adapters.netbox.v42.models import InterfaceV42, NetboxDeviceV42, PrefixV42, IpAddressV42
from annet.storage import Storage


class NetboxV42Adapter(NetboxV37Adapter):
    def __init__(
            self,
            storage: Storage,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
            threads: int,
    ):
        self.netbox = client_sync.NetboxV42(url=url, token=token, ssl_context=ssl_context, threads=threads)
        self.convert_device = get_converter(
            api_models.Device,
            NetboxDeviceV42,
            recipe=[
                link_function(get_device_breed, P[NetboxDeviceV42].breed),
                link_function(get_device_hw, P[NetboxDeviceV42].hw),
                link_constant(P[NetboxDeviceV42].interfaces, factory=list),
                link_constant(P[NetboxDeviceV42].storage, value=storage),
                link(P[api_models.Device].name, P[NetboxDeviceV42].hostname),
                link(P[api_models.Device].name, P[NetboxDeviceV42].fqdn),
            ]
        )
        self.convert_interface = get_converter(
            api_models.Interface,
            InterfaceV42,
            recipe=[
                link_constant(P[InterfaceV42].ip_addresses, factory=list),
                link_constant(P[InterfaceV42].lag_min_links, value=None),
            ]
        )
        self.convert_ip_address = get_converter(
            api_models.IpAddress,
            IpAddressV42,
            recipe=[
                link_constant(P[IpAddressV42].prefix, value=None),
            ]
        )


class NetboxStorageV42(BaseNetboxStorage[NetboxDeviceV42, InterfaceV42, IpAddressV42, PrefixV42]):
    def _init_adapter(
            self,
            url: str,
            token: str,
            ssl_context: ssl.SSLContext,
            threads: int,
    ) -> NetboxAdapter[NetboxDeviceT, InterfaceT, IpAddressT, PrefixT]:
        return NetboxV42Adapter(self, url, token, ssl_context, threads)
