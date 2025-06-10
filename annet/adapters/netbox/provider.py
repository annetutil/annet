from typing import Dict, Any, Optional

from dataclass_rest.exceptions import ClientError, ClientLibraryError

from annet.storage import StorageProvider, Storage
from annet.connectors import AdapterWithName, AdapterWithConfig, T
from .common.status_client import NetboxStatusClient
from .common.storage_opts import NetboxStorageOpts
from .common.query import NetboxQuery
from .v24.storage import NetboxStorageV24
from .v37.storage import NetboxStorageV37
from .v41.storage import NetboxStorageV41
from .v42.storage import NetboxStorageV42


def storage_factory(opts: NetboxStorageOpts) -> Storage:
    client = NetboxStatusClient(opts.url, opts.token, opts.insecure)
    version_class_map = {
        "3.4": NetboxStorageV37,
        "3.7": NetboxStorageV37,
        "4.0": NetboxStorageV41,
        "4.1": NetboxStorageV41,
        "4.2": NetboxStorageV42,
        "4.3": NetboxStorageV42,
    }

    status = None

    try:
        status = client.status()
        for version_prefix, storage_class in version_class_map.items():
            if version_prefix == status.minor_version:
                return storage_class(opts)

    except ClientError as e:
        if e.status_code == 404:
            return NetboxStorageV24(opts)
        else:
            raise ValueError(f"Unsupported version: {status.netbox_version}")
    except ClientLibraryError:
        raise ValueError(
            f"Connection error: Unable to reach Netbox at URL: {opts.url}")
    raise Exception(f"Unsupported version: {status.netbox_version}")


class NetboxProvider(StorageProvider, AdapterWithName, AdapterWithConfig):
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None, insecure: bool = False,
                 exact_host_filter: bool = False, threads: int = 1):
        self.url = url
        self.token = token
        self.insecure = insecure
        self.exact_host_filter = exact_host_filter
        self.threads = threads

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
