from pprint import pprint

import pytest

from annet.mesh import MeshExecutor, MeshRulesRegistry, GlobalOptions, DirectPeer, MeshSession
from .fakes import FakeStorage, FakeDevice, FakeInterface

VRF = "testvrf"
GROUP = "test_group"


def on_device_x(device: GlobalOptions):
    device.vrf[VRF].groups[GROUP].mtu = 1499
    print(device.matched.x)


def on_direct(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.1"
    neighbor.name = "XXX"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_unicast"}


@pytest.fixture
def registry():
    r = MeshRulesRegistry()
    r.device("{x:.*}")(on_device_x)
    r.direct("dev{num}.example.com", "{x:.*}")(on_direct)
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
    return FakeDevice(DEV2, [
        FakeInterface("if20", None, None),
    ])


@pytest.fixture()
def device_neighbor(device1):
    device1.interfaces.append(FakeInterface(
        name="if1",
        neighbor_fqdn=DEV_NEIGHBOR,
        neighbor_port="if10"
    ))
    return FakeDevice(DEV_NEIGHBOR, [
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
    pprint(res)
    assert False
