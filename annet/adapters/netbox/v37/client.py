from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Generic, TypeVar, List, Optional, Callable

import dateutil.parser
from adaptix import Retort, loader, Chain
from dataclass_rest import get
from dataclass_rest.client_protocol import FactoryProtocol
from dataclass_rest.http.requests import RequestsClient

from annet.adapters.netbox.common_models import IpAddress
from .models import Device, Interface

Model = TypeVar("Model")


@dataclass
class PagingResponse(Generic[Model]):
    next: Optional[str]
    previous: Optional[str]
    count: int
    results: List[Model]


Func = TypeVar("Func", bound=Callable)


def collect(func: Func) -> Func:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        kwargs.setdefault("offset", 0)
        limit = kwargs.setdefault("limit", 100)
        results = []
        method = func.__get__(self, self.__class__)
        has_next = True
        while has_next:
            page = method(*args, **kwargs)
            kwargs["offset"] += limit
            results.extend(page.results)
            has_next = bool(page.next)
            print(func.name, kwargs["offset"])
        return PagingResponse(
            None, None,
            count=len(results),
            results=results,
        )

    return wrapper


def fix_display(data):
    if "display_name" in data and "display" not in data:
        data["display"] = data["display_name"]
    return data


class Netbox(RequestsClient):
    def _init_response_body_factory(self) -> FactoryProtocol:
        return Retort(recipe=[
            loader(Device, fix_display, Chain.FIRST),
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

    all_interfaces = collect(interfaces)

    @get("ipam/ip-addresses")
    def ip_addresses(
            self,
            interface_id: Optional[List[int]] = None,
            limit: int = 20,
            offset: int = 0,
    ) -> PagingResponse[IpAddress]:
        pass

    all_ip_addresses = collect(ip_addresses)

    @get("dcim/devices")
    def devices(
            self,
            name: Optional[List[str]] = None,
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
