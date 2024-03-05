from annet.storage import StorageProvider
from .query import NetboxQuery
from .v37.storage import NetboxStorage, NetboxStorageOpts


class NetboxProvider(StorageProvider):
    def storage(self):
        return NetboxStorage

    def opts(self):
        return NetboxStorageOpts

    def query(self):
        return NetboxQuery