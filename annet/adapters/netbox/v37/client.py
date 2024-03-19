from datetime import datetime
from typing import List, Optional

import dateutil.parser
from adaptix import Retort, loader
from dataclass_rest import get
from dataclass_rest.client_protocol import FactoryProtocol

from annet.adapters.netbox.common.client import (
    BaseNetboxClient, collect, PagingResponse,
)
from annet.adapters.netbox.common.models import IpAddress
from .api_models import Device, Interface


class NetboxV37(BaseNetboxClient):
    def _init_response_body_factory(self) -> FactoryProtocol:
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
            name__ic: Optional[List[str]] = None,
            tag: Optional[List[str]] = None,
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
