from annet.annlib.netdev.views.hardware import HardwareView

from annet.runner.deploy_protocols import VendorCommander
from annet.runner.deploy_protocols import VendorCommanderRegistry

from .vendors.arista import AristaCommander
from .vendors.compat import CompatCommander
from .vendors.huawei import HuaweiCommander
from .vendors.iosxe import IosXECommander
from .vendors.iosxr import IosXRCommander
from .vendors.juniper import JuniperCommander
from .vendors.pc import PCCommander


class UnknownVendorError(ValueError):
    def __init__(self) -> None:
        super().__init__("Unknown vendor")


class VendorCommanderRegistryImpl(VendorCommanderRegistry):
    def __init__(self) -> None:
        self._vendors = {
            "Arista": AristaCommander(),
            "Huawei.OptiXtrans": CompatCommander(),
            "Huawei": HuaweiCommander(),
            "Cisco.ASR": IosXRCommander(),
            "Cisco.XR": IosXRCommander(),
            "Cisco.XRV": IosXRCommander(),
            "Cisco": IosXECommander(),
            "Juniper": JuniperCommander(),
            "PC": PCCommander(),
        }
        self._compat = CompatCommander()

    def match(self, hw: HardwareView) -> VendorCommander:
        for match_item, vendor in self._vendors.items():
            if hw.match(match_item):
                return vendor
        return self._compat
