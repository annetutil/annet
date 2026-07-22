import traceback
from logging import getLogger
from typing import Any

from annet.storage import Device
from annet.storage import Storage

from annet.runner.protocols import DeviceDump
from annet.runner.protocols import HandlerError
from annet.runner.protocols import ShowDeviceUI

logger = getLogger(__name__)


class CliShowDeviceDump:
    def __init__(
        self,
        storage: Storage,
        output: ShowDeviceUI,
    ) -> None:
        self._storage = storage
        self._output = output

    def _dump_device(self, device: Device) -> DeviceDump:
        if not hasattr(device, "dump"):
            return DeviceDump([], f"method `dump` not implemented for {type(device)}")
        try:
            return DeviceDump(device.dump("device"), None)
        except Exception:  # noqa: BLE001
            return DeviceDump([], traceback.format_exc())

    async def handle(self, query: Any) -> HandlerError | None:
        logger.info("Loading devices")
        devices = self._storage.make_devices(query)
        if not devices:
            logger.error("No devices found for query: %s", query)
            return HandlerError("No devices found")

        self._output.show_devices(devices, {d.id: self._dump_device(d) for d in devices})
        return None
