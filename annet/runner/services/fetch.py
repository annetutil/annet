from logging import getLogger

from annet.storage import Device

from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import DeviceDriverFactory
from annet.runner.deploy_protocols import DeviceResult
from annet.runner.deploy_protocols import VendorCommander
from annet.runner.deploy_protocols import VendorCommanderRegistry
from annet.runner.protocols import DeviceID
from annet.runner.protocols import DeviceStateLoader

logger = getLogger(__name__)


def parse(cmd_res: DeviceResult, vendor: VendorCommander) -> DeviceConfig:
    errors_text = "\n".join(map(str, cmd_res.all_errors)).strip()
    if errors_text:
        return DeviceConfig(error=errors_text)
    return vendor.parse_fetch(cmd_res)


class DeviceDriverLoader(DeviceStateLoader):
    def __init__(
        self,
        driver: DeviceDriverFactory,
        commander_registry: VendorCommanderRegistry,
    ) -> None:
        self._driver = driver
        self._commander_registry = commander_registry

    async def fetch(
        self,
        devices: list[Device],
        files: dict[DeviceID, list[str]],
    ) -> dict[DeviceID, DeviceConfig]:
        vendors = {d.id: self._commander_registry.match(d.hw) for d in devices}
        fetch_cmds = {device.id: vendors[device.id].fetch(device, files.get(device.id, [])) for device in devices}
        quit_cmds = {device.id: vendors[device.id].quit() for device in devices}
        async with self._driver.make_driver(devices, quit_cmds) as driver:
            cmds_res = await driver.execute(devices, fetch_cmds, None)
        res = {d.id: parse(cmds_res[d.id], vendors[d.id]) for d in devices}
        for device in devices:
            logger.info("Fetched device state: %s - %s", device.fqdn, res[device.id].commit_state)
        return res
