from dataclass_rest.exceptions import ClientError

from annet.storage import StorageProvider, Storage
from .query import NetboxQuery
from .status_client import NetboxStatusClient
from .v24.storage import NetboxStorage, NetboxStorageOpts
from .v37.storage import NetboxStorage as NetboxStorageV27


def storage_factory(opts: NetboxStorageOpts) -> Storage:
    client = NetboxStatusClient(opts.url, opts.token)
    try:
        status = client.status()
    except ClientError as e:
        if e.status_code == 404:
            # old version do not support status reqeust
            return NetboxStorage(opts)
        raise
    if status.netbox_version.startswith("3."):
        return NetboxStorageV27(opts)
    else:
        raise ValueError(f"Unsupported version: {status.netbox_version}")


class NetboxProvider(StorageProvider):
    def storage(self):
        return storage_factory

    def opts(self):
        return NetboxStorageOpts

    def query(self):
        return NetboxQuery
