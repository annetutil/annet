import os
from typing import Any, Optional

DEFAULT_URL = "http://localhost"


class NetboxStorageOpts:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    @classmethod
    def parse_params(cls, conf_params: Optional[dict[str, str]], cli_opts: Any):
        url = os.getenv("NETBOX_URL") or conf_params.get("url") or DEFAULT_URL
        token = os.getenv("NETBOX_TOKEN", "").strip() or conf_params.get("token") or ""
        return cls(url=url, token=token)
