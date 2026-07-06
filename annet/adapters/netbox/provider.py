from __future__ import annotations

from typing import Any, cast

from dataclass_rest.exceptions import ClientError, ClientLibraryError

from annet.connectors import AdapterWithConfig, AdapterWithName
from annet.storage import Storage, StorageOpts, StorageProvider

from .common.query import NetboxQuery
from .common.status_client import NetboxStatusClient
from .common.storage_base import BaseNetboxStorage
from .common.storage_opts import NetboxStorageOpts
from .v37.storage import NetboxStorageV37
from .v41.storage import NetboxStorageV41
from .v42.storage import NetboxStorageV42


def storage_factory(opts: NetboxStorageOpts) -> Storage:
    client = NetboxStatusClient(opts.url, opts.token, opts.insecure)
    version_class_map: dict[str, type[BaseNetboxStorage[Any, Any, Any, Any, Any, Any]]] = {
        "3.4": NetboxStorageV37,
        "3.7": NetboxStorageV37,
        "4.0": NetboxStorageV41,
        "4.1": NetboxStorageV41,
        "4.2": NetboxStorageV42,
        "4.3": NetboxStorageV42,
        "4.4": NetboxStorageV42,
        "4.5": NetboxStorageV42,
        "4.6": NetboxStorageV42,
    }

    status = None

    try:
        status = client.status()
        for version_prefix, storage_class in version_class_map.items():
            if version_prefix == status.minor_version:
                return storage_class(opts)

    except ClientError as e:
        raise ValueError(f"API error: Unexpected response from Netbox at URL: {opts.url}/api/status, Code: {e}")
    except ClientLibraryError:
        raise ValueError(f"Connection error: Unable to reach Netbox at URL: {opts.url}")
    raise Exception(f"Unsupported version: {status.netbox_version}")


class NetboxProvider(StorageProvider, AdapterWithName, AdapterWithConfig["NetboxProvider"]):
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        insecure: bool = False,
        exact_host_filter: bool = False,
        threads: int = 1,
        all_hosts_filter: dict[str, list[str]] | None = None,
        cache_path: str = "",
        cache_ttl: int = 0,
    ):
        self.url = url
        self.token = token
        self.insecure = insecure
        self.exact_host_filter = exact_host_filter
        self.threads = threads
        self.all_hosts_filter = all_hosts_filter

    @classmethod
    def with_config(cls, **kwargs: Any) -> "NetboxProvider":
        return cls(**kwargs)

    def storage(self) -> type[Storage]:
        return cast("type[Storage]", storage_factory)

    def opts(self) -> type[StorageOpts]:
        return cast("type[StorageOpts]", NetboxStorageOpts)

    def query(self) -> type[NetboxQuery]:
        return NetboxQuery

    @classmethod
    def name(cls) -> str:
        return "netbox"
