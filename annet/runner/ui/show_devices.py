# ruff: noqa: T201
from logging import getLogger
from pathlib import Path

import colorama
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceID
from annet.runner.protocols import DeviceDump
from annet.runner.protocols import ShowDeviceUI
from annet.runner.ui.common import format_header
from annet.runner.ui.common import show_header

logger = getLogger(__name__)


class ConsoleShowDevice(ShowDeviceUI):
    def show_devices(self, devices: list[Device], data: dict[DeviceID, DeviceDump]) -> None:
        for device in devices:
            self._show_device(device, data[device.id])

    def _show_device(self, device: Device, dump: DeviceDump) -> None:
        header = format_header(device.fqdn, "", "")
        if dump.error:
            show_header(header, colorama.Back.RED)
            print(dump.error)
        else:
            show_header(header, colorama.Back.GREEN)
            for row in dump.rows:
                print(row)


class StoreDevice(ShowDeviceUI):
    def __init__(self, path: Path) -> None:
        self._path = path

    def show_devices(self, devices: list[Device], data: dict[DeviceID, DeviceDump]) -> None:
        for device in devices:
            self._show_device(device, data[device.id])

    def _show_device(self, device: Device, dump: DeviceDump) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        path = self._path / device.fqdn
        path.write_text("\n".join(dump.rows), encoding="utf-8")
