from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import AsrFormatter
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class IosXrVendor(AbstractVendor):
    NAME = "iosxr"

    def match(self) -> list[str]:
        return ["Cisco.ASR", "Cisco.XR", "Cisco.XRV"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Cisco ASR")

    def svi_name(self, num: int) -> str:
        return f"Vlan{num}"

    def make_formatter(self, **kwargs) -> AsrFormatter:
        return AsrFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "exit"
