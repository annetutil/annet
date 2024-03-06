from dataclasses import dataclass

from adaptix import Retort, name_mapping, NameStyle
from dataclass_rest import get
from dataclass_rest.client_protocol import FactoryProtocol
from dataclass_rest.http.requests import RequestsClient
from requests import Session


@dataclass
class Status:
    netbox_version: str
    plugins: dict[str, str]


class NetboxStatusClient(RequestsClient):
    def __init__(self, url: str, token: str):
        url = url.rstrip("/") + "/api/"
        session = Session()
        session.verify = False
        if token:
            session.headers["Authorization"] = f"Token {token}"
        super().__init__(url, session)

    def _init_response_body_factory(self) -> FactoryProtocol:
        return Retort(recipe=[
            name_mapping(name_style=NameStyle.LOWER_KEBAB)
        ])

    @get("status")
    def status(self) -> Status:
        ...
