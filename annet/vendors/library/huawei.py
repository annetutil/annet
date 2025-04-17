from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.tabparser import HuaweiFormatter
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

    @property
    def hardware(self) -> HardwareView:
        return HardwareView("Huawei")

    def svi_name(self, num: int) -> str:
        return f"Vlanif{num}"

    def make_formatter(self, **kwargs) -> HuaweiFormatter:
        return HuaweiFormatter(**kwargs)

    @property
    def exit(self) -> str:
        return "quit"
