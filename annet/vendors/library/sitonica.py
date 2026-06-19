from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.library.h3c import H3CVendor
from annet.vendors.registry import registry


@registry.register
class SitonicaVendor(H3CVendor):
    NAME = "sitonica"

    def match(self) -> list[str]:
        return ["Sitonica"]

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Sitonica")
