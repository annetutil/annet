from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors.base import AbstractVendor
from annet.vendors.registry import registry


@registry.register
class HuaweiVendor(AbstractVendor):
    NAME = "huawei"

    def match(self) -> list[str]:
        return ["Huawei"]

    @property
    def reverse(self) -> str:
        return "undo"

    def hardware(self, soft: str | None = None) -> HardwareView:
        return HardwareView("Huawei", soft)

    def svi_name(self, num: int) -> str:
        return f"Vlanif{num}"
