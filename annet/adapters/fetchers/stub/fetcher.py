from typing import Any

from annet.connectors import AdapterWithConfig
from annet.deploy import Fetcher
from annet.storage import Device


class StubFetcher(Fetcher, AdapterWithConfig[Fetcher]):
    @classmethod
    def with_config(cls, **kwargs: Any) -> Fetcher:
        return cls(**kwargs)

    async def fetch_packages(
        self,
        devices: list[Device],
        processes: int = 1,
        max_slots: int = 0,
    ) -> tuple[dict[Device, frozenset[str]], dict[Device, Any]]:
        raise NotImplementedError()

    async def fetch(
        self,
        devices: list[Device],
        files_to_download: dict[Device, list[str] | Exception] | None = None,
        processes: int = 1,
        max_slots: int = 0,
    ) -> tuple[dict[Device, Any], dict[Device, Exception]]:
        raise NotImplementedError()
