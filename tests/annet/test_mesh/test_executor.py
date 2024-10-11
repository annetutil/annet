import pytest

from annet.mesh.executor import MeshExecutor
from annet.mesh.registry import MeshRulesRegistry
from .fakes import FakeStorage, FakeDevice


def on_device_x(device):
    pass


@pytest.fixture
def registry():
    r = MeshRulesRegistry()
    r.device("{x}")(on_device_x)
    return r


@pytest.fixture()
def device():
    return FakeDevice("1", [])


@pytest.fixture
def storage(device):
    s = FakeStorage()
    s.add_device(device)
    return s


def test_storage(registry, storage, device):
    r = MeshExecutor(registry, storage)
    res = r.execute_for(device)
    print(res)
    assert False