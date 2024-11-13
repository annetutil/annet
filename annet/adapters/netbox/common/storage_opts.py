import os
from typing import Any, Optional

DEFAULT_URL = "http://localhost"


class NetboxStorageOpts:
    def __init__(self, url: str, token: str, insecure: bool = False, exact_host_filter: bool = False):
        self.url = url
        self.token = token
        self.insecure = insecure
        self.exact_host_filter = exact_host_filter

    @classmethod
    def parse_params(cls, conf_params: Optional[dict[str, str]], cli_opts: Any):
        url = os.getenv("NETBOX_URL") or conf_params.get("url") or DEFAULT_URL
        token = os.getenv("NETBOX_TOKEN", "").strip() or conf_params.get("token") or ""
        insecure = False
        if insecure_env := os.getenv("NETBOX_INSECURE", "").lower():
            insecure = insecure_env in ("true", "1", "t")
        else:
            insecure = bool(conf_params.get("insecure") or False)
        if exact_host_filter_env := os.getenv("NETBOX_EXACT_HOST_FILTER", "").lower():
            exact_host_filter = exact_host_filter_env in ("true", "1", "t")
        else:
            exact_host_filter = bool(conf_params.get("exact_host_filter") or False)
        return cls(url=url, token=token, insecure=insecure, exact_host_filter=exact_host_filter)
