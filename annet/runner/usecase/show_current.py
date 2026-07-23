from logging import getLogger
from typing import Any

from annet.storage import Storage

from annet.runner.protocols import DeviceStateLoader
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import HandlerError
from annet.runner.protocols import ShowCurrentUI

logger = getLogger(__name__)


class CliShowCurrent:
    def __init__(
        self,
        storage: Storage,
        data_src: GeneratedDataSource,
        fetcher: DeviceStateLoader,
        output: ShowCurrentUI,
    ) -> None:
        self._storage = storage
        self._output = output
        self._fetcher = fetcher
        self._data_src = data_src

    async def handle(self, query: Any) -> HandlerError | None:
        logger.info("Loading devices")
        devices = self._storage.make_devices(query)
        if not devices:
            logger.error("No devices found for query: %s", query)
            return HandlerError("No devices found")

        logger.info("Loading live configs")
        files = self._data_src.list_files(devices)
        live_configs = await self._fetcher.fetch(devices, files)
        self._output.show_current(devices, live_configs)
        return None
