from datetime import datetime
from typing import List, Optional

import dateutil.parser
from adaptix import Retort, loader
from dataclass_rest import get

from annet.adapters.netbox.common.client import (
    BaseNetboxClient, collect, PagingResponse,
)
from .api_models import Device, Interface, IpAddress


class NetboxV24(BaseNetboxClient):
    def _init_response_body_factory(self) -> Retort:
        return Retort(recipe=[
            loader(datetime, dateutil.parser.parse)
        ])

    @get("dcim/interfaces")
    def interfaces(
            self,
            device_id: Optional[List[int]] = None,
            limit: int = 20,
            offset: int = 0,
    ) -> PagingResponse[Interface]:
        pass

    all_interfaces = collect(interfaces, field="device_id")

    @get("ipam/ip-addresses")
    def ip_addresses(
            self,
            interface_id: Optional[List[int]] = None,
            limit: int = 20,
            offset: int = 0,
    ) -> PagingResponse[IpAddress]:
        pass

    all_ip_addresses = collect(ip_addresses, field="interface_id")

    @get("dcim/devices")
    def devices(
            self,
            name: Optional[List[str]] = None,
            tag: Optional[str] = None,
            limit: int = 20,
            offset: int = 0,
    ) -> PagingResponse[Device]:
        pass

    all_devices = collect(devices)

    @get("dcim/devices/{device_id}")
    def get_device(
            self,
            device_id: int,
    ) -> Device:
        pass
