from logging import getLogger

from annet.annlib.netdev.views.hardware import HardwareView

logger = getLogger(__name__)

_VENDORS = {
    "cisco": "Cisco",
    "catalyst": "Cisco Catalyst",
    "nexus": "Cisco Nexus",
    "huawei": "Huawei",
    "optixtrans": "Huawei OptiXtrans",
    "juniper": "Juniper",
    "arista": "Arista",
    "pc": "PC",
    "nokia": "Nokia",
    "aruba": "Aruba",
    "routeros": "RouterOS",
    "ribbon": "Ribbon",
    "b4com": "B4com",
    "h3c": "H3C",
}


def get_hw(manufacturer: str, model: str, platform_name: str):
    # by some reason Netbox calls Mellanox SN as MSN, so we fix them here
    if manufacturer == "Mellanox" and model.startswith("MSN"):
        model = model.replace("MSN", "SN", 1)
    vendor = manufacturer + " " + model
    hw = HardwareView(_VENDORS.get(vendor.lower(), vendor), platform_name)
    return hw


def get_breed(manufacturer: str, model: str):
    if manufacturer == "Huawei" and model.startswith("CE"):
        return "vrp85"
    elif manufacturer == "Huawei" and model.startswith("NE"):
        return "vrp85"
    elif manufacturer == "Huawei":
        return "vrp55"
    elif manufacturer == "H3C":
        return "h3c"
    elif manufacturer in ("Mellanox", "NVIDIA"):
        return "cuml2"
    elif manufacturer == "Juniper":
        return "jun10"
    elif manufacturer == "Cisco":
        return "ios12"
    elif manufacturer == "Adva":
        return "adva8"
    elif manufacturer == "Arista":
        return "eos4"
    elif manufacturer == "B4com":
        return "bcom-os"
    elif manufacturer == "MikroTik":
        return "routeros"
    elif manufacturer == "Moxa":
        return "moxa"
    elif manufacturer == "PC":
        return "pc"
    return ""
