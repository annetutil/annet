from logging import getLogger

from annet.annlib.netdev.views.hardware import HardwareView

logger = getLogger(__name__)

_VENDORS = {
    "cisco": "Cisco",
    "catalyst": "Cisco Catalyst",
    "nexus": "Cisco Nexus",
    "huawei": "Huawei",
    "juniper": "Juniper",
    "arista": "Arista",
    "pc": "PC",
    "nokia": "Nokia",
    "aruba": "Aruba",
    "routeros": "RouterOS",
    "ribbon": "Ribbon",
}


def _vendor_to_hw(vendor):
    return HardwareView(_VENDORS.get(vendor.lower(), vendor), None)


def get_hw(manufacturer: str, model: str):
    # by some reason Netbox calls Mellanox SN as MSN, so we fix them here
    if manufacturer == "Mellanox" and model.startswith("MSN"):
        model = model.replace("MSN", "SN", 1)
    hw = _vendor_to_hw(manufacturer + " " + model)
    if not hw:
        raise ValueError(f"unsupported manufacturer {manufacturer}")
    return hw


def get_breed(manufacturer: str, model: str):
    if manufacturer == "Huawei" and model.startswith("CE"):
        return "vrp85"
    elif manufacturer == "Huawei" and model.startswith("NE"):
        return "vrp85"
    elif manufacturer == "Huawei":
        return "vrp55"
    elif manufacturer == "Mellanox":
        return "cuml2"
    elif manufacturer == "Juniper":
        return "jun10"
    elif manufacturer == "Cisco":
        return "ios12"
    elif manufacturer == "Adva":
        return "adva8"
    elif manufacturer == "Arista":
        return "eos4"
    raise ValueError(f"unsupported manufacturer {manufacturer}")


def is_supported(manufacturer: str) -> bool:
    if manufacturer not in (
            "Huawei", "Mellanox", "Juniper", "Cisco", "Adva", "Arista",
    ):
        logger.warning("Unsupported manufacturer `%s`", manufacturer)
        return False
    return True
