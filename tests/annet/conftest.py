import pytest
from annet.hardware import hardware_connector
from annet.rulebook import rulebook_provider_connector

from annet.hardware import AnnetHardwareProvider
from annet.rulebook import DefaultRulebookProvider


@pytest.fixture(scope="session", autouse=True)
def ann_connectors():
    hardware_connector.set(AnnetHardwareProvider)
    rulebook_provider_connector.set(DefaultRulebookProvider)
