from logging import getLogger
from typing import Any

from annet.storage import Storage

from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceID
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import DeviceStateLoader
from annet.runner.protocols import HandlerError
from annet.runner.protocols import RollbackShowUI

logger = getLogger(__name__)


class CliShowRollback:
    def __init__(
        self,
        storage: Storage,
        fetcher: DeviceStateLoader,
        output: RollbackShowUI,
        commander_registry: VendorCommanderRegistry,
    ) -> None:
        self._storage = storage
        self._output = output
        self._fetcher = fetcher
        self._commander_registry = commander_registry

    async def handle(self, query: Any) -> HandlerError | None:
        logger.info("Loading devices")
        devices = self._storage.make_devices(query)
        if not devices:
            logger.error("No devices found for query: %s", query)
            return HandlerError("No devices found")

        logger.info("Loading live configs")
        live_configs = await self._fetcher.fetch(devices, {})

        logger.info("Generating rollback commands")
        commands: dict[DeviceID, DeviceCommands] = {
            device.id: self._commander_registry.match(device.hw).rollback(
                live_configs[device.id].commit_state,
            )
            for device in devices
        }
        logger.info("Show result")
        self._output.show_rollback_commands(devices, commands)
        return None
