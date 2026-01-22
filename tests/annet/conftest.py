import pytest

from annet.hardware import AnnetHardwareProvider, hardware_connector
from annet.rulebook import DefaultRulebookProvider, rulebook_provider_connector


@pytest.fixture(scope="session", autouse=True)
def ann_connectors():
    hardware_connector.set(AnnetHardwareProvider)
    rulebook_provider_connector.set(DefaultRulebookProvider)
