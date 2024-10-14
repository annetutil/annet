import pytest

from annet.mesh.executor import MeshExecutor
from annet.mesh.registry import MeshRulesRegistry
from .fakes import FakeStorage, FakeDevice, FakeInterface


def on_device_x(device):
    pass


@pytest.fixture
def registry():
    r = MeshRulesRegistry()
    r.device("{x}")(on_device_x)
    return r


DEV1 = "dev1.example.com"
DEV2 = "dev2.example.com"
DEV_NEIGHBOR = "dev_neighbor.example.com"


@pytest.fixture()
def device1():
    return FakeDevice(DEV1, [
        FakeInterface("if20", None, None),
    ])


@pytest.fixture()
def device2():
    return FakeDevice("dev1", [
        FakeInterface("if20", None, None),
    ])


@pytest.fixture()
def device_neighbor(device1):
    device1.interfaces.append(FakeInterface(
        name="if1",
        neighbor_fqdn=DEV_NEIGHBOR,
        neighbor_port="if10"
    ))
    return FakeDevice("dev_neighbor", [
        FakeInterface(
            name="if10",
            neighbor_fqdn=DEV1,
            neighbor_port="if1"
        )
    ])


@pytest.fixture
def storage(device1, device2, device_neighbor):
    s = FakeStorage()
    s.add_device(device1)
    s.add_device(device2)
    s.add_device(device_neighbor)
    return s


def test_storage(registry, storage, device1):
    r = MeshExecutor(registry, storage)
    res = r.execute_for(device1)
    print(res)
    assert False
