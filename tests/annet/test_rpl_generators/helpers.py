from .. import MockDevice


def scrub(text: str) -> str:
    splitted = text.split("\n")
    return "\n".join(filter(None, splitted))


def huawei():
    return MockDevice(
        "Huawei CE6870-48S6CQ-EI",
        "VRP V200R001C00SPC700 + V200R001SPH002",
        "vrp85",
    )


def arista():
    return MockDevice(
        "Arista DCS-7368",
        "EOS 4.29.9.1M",
        "arista",
    )


def cumulus():
    return MockDevice(
        "Mellanox SN3700-VS2RO",
        "Cumulus Linux 5.4.0",
        "pc",
    )
