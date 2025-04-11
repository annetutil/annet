from logging import getLogger

from annet.annlib.netdev.views.hardware import HardwareView
from annet.vendors import registry_connector

logger = getLogger(__name__)


def get_hw(manufacturer: str, model: str, platform_name: str):
    vendor_registry = registry_connector.get()

    # By some reason Netbox calls Mellanox SN as MSN, so we fix them here
    if manufacturer == "Mellanox" and model.startswith("MSN"):
        model = model.replace("MSN", "SN", 1)

    if (vendor := manufacturer.strip().lower()) and vendor in vendor_registry:
        hw = vendor_registry[vendor].hardware
    else:
        hw = HardwareView(manufacturer + " " + model)
    hw.soft = platform_name
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
    elif manufacturer in ("Moxa", "Nebius"):
        return "moxa"
    elif manufacturer == "PC":
        return "pc"
    return ""
