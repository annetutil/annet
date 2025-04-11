from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class IosXrVendor(AbstractVendor):
    NAME = "iosxr"

    def match(self) -> list[str]:
        return ["Cisco.XR", "Cisco.ASR", "Cisco.XRV"]

    @property
    def reverse(self) -> str:
        return "no"

    def hardware(self, soft: str | None = None) -> HardwareView:
        return HardwareView("Cisco XR", soft)

    def svi_name(self, num: int) -> str:
        return f"Vlan{num}"
