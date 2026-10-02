from typing import FrozenSet
from unittest.mock import Mock

import pytest

from annet.generators import Entire, check_entire_generators_required_packages
from annet.storage import Device, Storage


class StaticPackages(Entire):
    REQUIRED_PACKAGES = frozenset({"telegraf", "linux-commit-api"})


class DevicePackages(StaticPackages):
    def required_packages(self, device: Device) -> FrozenSet[str]:
        if device.hw.soft.startswith("SwitchDev"):
            return self.REQUIRED_PACKAGES
        if device.hw.soft.startswith("SONiC"):
            return frozenset({"telegraf"})
        return frozenset()


@pytest.mark.parametrize(
    "installed, missing",
    [
        (frozenset({"telegraf", "linux-commit-api"}), []),
        (frozenset({"telegraf"}), ["linux-commit-api"]),
        (frozenset(), ["linux-commit-api", "telegraf"]),
    ],
)
def test_static_required_packages(installed: FrozenSet[str], missing: list[str]) -> None:
    generator = StaticPackages(Mock(spec=Storage))
    errors = check_entire_generators_required_packages([generator], installed, Mock(spec=Device))
    if missing:
        label = "package" if len(missing) == 1 else "packages"
        packages = ", ".join(f"`{package}'" for package in missing)
        assert errors == [f"missing {label} {packages} required for {generator}"]
    else:
        assert errors == []


@pytest.mark.parametrize(
    "software, installed, missing",
    [
        ("SwitchDev 2.0", frozenset({"telegraf"}), ["linux-commit-api"]),
        ("SwitchDev 2.0", frozenset({"telegraf", "linux-commit-api"}), []),
        ("SONiC 2024", frozenset({"telegraf"}), []),
        ("SONiC 2024", frozenset(), ["telegraf"]),
        ("FreeBSD 14", frozenset(), []),
    ],
)
def test_device_required_packages(software: str, installed: FrozenSet[str], missing: list[str]) -> None:
    device = Mock(spec=Device)
    device.hw.soft = software
    generator = DevicePackages(Mock(spec=Storage))
    errors = check_entire_generators_required_packages([generator], installed, device)
    if missing:
        assert errors == [f"missing package `{missing[0]}' required for {generator}"]
    else:
        assert errors == []


def test_no_required_packages() -> None:
    generator = Entire(Mock(spec=Storage))
    assert check_entire_generators_required_packages([generator], frozenset(), Mock(spec=Device)) == []
