from annet.deploy import Fetcher
from annet.connectors import AdapterWithConfig
from typing import Dict, List, Any
from annet.storage import Device


class StubFetcher(Fetcher, AdapterWithConfig):
    @classmethod
    def with_config(cls, **kwargs: Dict[str, Any]) -> Fetcher:
        return cls(**kwargs)

    def fetch_packages(self, devices: List[Device],
                       processes: int = 1, max_slots: int = 0):
        raise NotImplementedError()

    def fetch(self, devices: List[Device],
              files_to_download: Dict[str, List[str]] = None,
              processes: int = 1, max_slots: int = 0):
        raise NotImplementedError()
