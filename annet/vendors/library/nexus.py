from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class NexusVendor(AbstractVendor):
    NAME = "nexus"

    def match(self) -> list[str]:
        return ["Cisco.Nexus"]

    @property
    def reverse(self) -> str:
        return "no"

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Cisco Nexus")
