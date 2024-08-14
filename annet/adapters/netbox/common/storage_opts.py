import os
from typing import Any


class NetboxStorageOpts:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    @classmethod
    def parse_params(cls, conf_params: dict[str, str] | None, cli_opts: Any):
        return cls(
            url=os.getenv("NETBOX_URL", "http://localhost"),
            token=os.getenv("NETBOX_TOKEN", "").strip(),
        )
