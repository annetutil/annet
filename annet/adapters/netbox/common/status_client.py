from dataclasses import dataclass

from adaptix import Retort, name_mapping, NameStyle
from dataclass_rest import get
from dataclass_rest.client_protocol import FactoryProtocol

from .client import BaseNetboxClient


@dataclass
class Status:
    netbox_version: str
    plugins: dict[str, str]


class NetboxStatusClient(BaseNetboxClient):
    def _init_response_body_factory(self) -> FactoryProtocol:
        return Retort(recipe=[
            name_mapping(name_style=NameStyle.LOWER_KEBAB)
        ])

    @get("status")
    def status(self) -> Status:
        ...
