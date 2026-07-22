from logging import getLogger
from typing import Any

from annet.storage import Storage

from annet.runner.protocols import GeneratedDataOutput
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GeneratorMerger
from annet.runner.protocols import HandlerError

logger = getLogger(__name__)


class CliGenerate:
    def __init__(
        self,
        storage: Storage,
        data_src: GeneratedDataSource,
        output: GeneratedDataOutput,
        merger: GeneratorMerger,
    ) -> None:
        self._storage = storage
        self._data_src = data_src
        self._output = output
        self._merger = merger

    async def handle(self, query: Any) -> HandlerError | None:
        logger.info("Loading devices")
        devices = self._storage.make_devices(query)
        if not devices:
            logger.error("No devices found for query: %s", query)
            return HandlerError("No devices found")
        logger.info("Generating data")
        res = self._data_src.generate(devices)
        logger.info("Preparing new configs")
        configs = {device.id: self._merger.make_device_config(device, res[device.id].data) for device in devices}
        logger.info("Show result")
        await self._output.print(devices, res, configs)
        return None
