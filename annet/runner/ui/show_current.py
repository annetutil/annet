# ruff: noqa: T201
from pathlib import Path

import colorama
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.deploy_protocols import DeviceID
from annet.runner.protocols import ShowCurrentUI

from .common import format_header
from .common import show_header


class ConsoleShowCurrent(ShowCurrentUI):
    def show_current(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
    ) -> None:
        for device in devices:
            config = live_configs[device.id]
            self._show_device_config(device, config)

    def _show_device_config(self, device: Device, config: DeviceConfig) -> None:
        if config.config is not None:
            header = format_header(device.fqdn, "", "")
            show_header(header, colorama.Back.GREEN)
            print(config.config)
        paths = sorted(config.files)
        for path in paths:
            header = format_header(device.fqdn, "", path)
            show_header(header, colorama.Back.GREEN)
            print(config.files[path])
        if config.error:
            header = format_header(device.fqdn, "", "")
            show_header(header, colorama.Back.RED)
            print(config.error)


class StoreCurrent(ShowCurrentUI):
    def __init__(self, path: Path) -> None:
        self._path = path

    def show_current(
        self,
        devices: list[Device],
        live_configs: dict[DeviceID, DeviceConfig],
    ) -> None:
        for device in devices:
            config = live_configs[device.id]
            self._save_device_config(device, config)

    def _save_device_config(self, device: Device, config: DeviceConfig) -> None:
        path = self._path / (device.fqdn + ".cfg")
        if device.is_pc():
            for device_filepath, content in config.files.items():
                filepath = path / Path(device_filepath).relative_to("/")
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content, encoding="utf-8")
        else:
            path.write_text(config.config, encoding="utf-8")
