# ruff: noqa: T201
import colorama
from annet.storage import Device

from annet.runner.deploy_protocols import DeviceConfig
from annet.runner.protocols import DeviceID
from annet.runner.protocols import GeneratedDataOutput
from annet.runner.protocols import GenerationResult
from annet.runner.ui.common import format_header
from annet.runner.ui.common import show_header


class ConsoleDataOutput(GeneratedDataOutput):
    def __init__(self, *, per_gen: bool) -> None:
        self._per_gen = per_gen

    def _print_gen_res(self, dev: Device, dev_res: GenerationResult) -> None:
        if dev_res.error:
            header = format_header(dev.fqdn, "", "")
            show_header(header, bg=colorama.Back.RED)
            print(dev_res.error)
        for data in dev_res.data:
            header = format_header(dev.fqdn, data.name, data.path)
            if data.error:
                show_header(header, bg=colorama.Back.RED)
                print(data.error)
                continue
            show_header(header, colorama.Back.GREEN)
            print(data.output)

    async def print(
        self,
        devices: list[Device],
        generators_results: dict[DeviceID, GenerationResult],
        results: dict[DeviceID, DeviceConfig],
    ) -> None:
        for device in devices:
            if self._per_gen:
                gen_res = generators_results[device.id]
                self._print_gen_res(device, gen_res)
            else:
                dev_res = results[device.id]
                self._print_device(device, dev_res)

    def _print_device(self, dev: Device, dev_res: DeviceConfig) -> None:
        header = format_header(dev.fqdn, "", "")
        if dev_res.error:
            show_header(header, bg=colorama.Back.RED)
            print(dev_res.error)
        if dev_res.config:
            show_header(header, colorama.Back.GREEN)
            print(dev_res.config)

        for path, data in dev_res.files.items():
            header = format_header(dev.fqdn, "", path)
            show_header(header, colorama.Back.GREEN)
            print(data)
