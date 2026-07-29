import logging
from pathlib import Path

from adaptix import Retort
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.protocols import DeviceID
from annet.runner.protocols import DeviceStateLoader

logger = logging.getLogger(__name__)
retort = Retort()


class LocalDeviceStateLoader(DeviceStateLoader):
    def __init__(self, path: Path) -> None:
        self._path = path

    async def fetch(
        self,
        devices: list[Device],
        files: dict[DeviceID, list[str]],
    ) -> dict[DeviceID, DeviceConfig]:
        logger.info("Fetching device configs from dir %r", str(self._path))
        return {d.id: self._load_device(d, files.get(d.id, [])) for d in devices}

    def _load_device(self, device: Device, files: list[str]) -> DeviceConfig:
        path = self._path / (device.fqdn + ".cfg")
        if not path.exists():
            return DeviceConfig(error="File not found")
        if path.is_file():
            if files:
                return DeviceConfig(error="Cannot fetch files as cli config found")
            return DeviceConfig(config=path.read_text(), files={})

        dev_files = {}
        if device.is_pc():
            for name in files:
                file = path / name.lstrip("/")
                if file.exists():
                    dev_files[name] = file.read_text()
        return DeviceConfig(config=None, files=dev_files)
