from typing import Dict, Any, Optional

from dataclass_rest.exceptions import ClientError

from annet.storage import StorageProvider, Storage
from annet.connectors import AdapterWithName, AdapterWithConfig, T
from .common.status_client import NetboxStatusClient
from .common.storage_opts import NetboxStorageOpts
from .common.query import NetboxQuery
from .v24.storage import NetboxStorageV24
from .v37.storage import NetboxStorageV37


def storage_factory(opts: NetboxStorageOpts) -> Storage:
    client = NetboxStatusClient(opts.url, opts.token, opts.insecure)
    try:
        status = client.status()
    except ClientError as e:
        if e.status_code == 404:
            # old version do not support status reqeust
            return NetboxStorageV24(opts)
        raise
    if status.netbox_version.startswith("3."):
        return NetboxStorageV37(opts)
    else:
        raise ValueError(f"Unsupported version: {status.netbox_version}")


class NetboxProvider(StorageProvider, AdapterWithName, AdapterWithConfig):
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None, insecure: bool = False,
                 exact_host_filter: bool = False):
        self.url = url
        self.token = token
        self.insecure = insecure
        self.exact_host_filter = exact_host_filter

    @classmethod
    def with_config(cls, **kwargs: Dict[str, Any]) -> T:
        return cls(**kwargs)

    def storage(self):
        return storage_factory

    def opts(self):
        return NetboxStorageOpts

    def query(self):
        return NetboxQuery

    @classmethod
    def name(cls) -> str:
        return "netbox"
