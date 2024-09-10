from annet.deploy import Fetcher, AdapterWithConfig
from typing import Dict, List, Any
from annet.storage import Device


class StubFetcher(Fetcher, AdapterWithConfig):
    def with_config(self, **kwargs: Dict[str, Any]) -> Fetcher:
        return self

    def fetch_packages(self, devices: List[Device],
                       processes: int = 1, max_slots: int = 0):
        raise NotImplementedError()

    def fetch(self, devices: List[Device],
              files_to_download: Dict[str, List[str]] = None,
              processes: int = 1, max_slots: int = 0):
        raise NotImplementedError()
