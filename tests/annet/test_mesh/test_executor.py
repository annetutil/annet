import pytest

from annet.mesh import MeshExecutor, MeshRulesRegistry, GlobalOptions, DirectPeer, MeshSession, IndirectPeer
from .fakes import FakeStorage, FakeDevice, FakeInterface

VRF = "testvrf"
GROUP = "test_group"


def on_device_x(device: GlobalOptions):
    device.vrf[VRF].groups[GROUP].mtu = 1499
    print(device.match.x)


def on_direct(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.1"
    neighbor.name = "XXX"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_unicast"}


def on_indirect(local: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.10"
    neighbor.name = "YYY"
    local.mtu = 1505
    neighbor.mtu = 1506
    session.asnum = 12340
    session.families = {"ipv6_unicast"}


@pytest.fixture
def registry():
    r = MeshRulesRegistry()
    r.device("{x:.*}")(on_device_x)
    r.direct("dev{num}.example.com", "dev_{x:.*}")(on_direct)
    r.indirect("dev{num}.example.com", "dev{num}.remote.example.com")(on_indirect)
    return r


DEV1 = "dev1.example.com"
DEV2 = "dev2.remote.example.com"
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

    assert res.global_options.groups == []
    assert res.global_options.vrf.keys() == {VRF}
    vrf = res.global_options.vrf[VRF]
    assert vrf.vrf_name == VRF
    assert vrf.static_label is None
    assert len(vrf.groups) == 1
    assert vrf.groups[0].mtu == 1499
    assert vrf.groups[0].name == GROUP

    peer_direct, peer_indirect = res.peers
    assert peer_direct.name == "XXX"
    assert peer_direct.addr == "192.168.1.1"
    assert peer_direct.options.mtu == 1501
    assert peer_direct.families == {"ipv4_unicast"}
    assert peer_direct.remote_as == 12345
    assert peer_direct.description == ""

    assert peer_indirect.name == "YYY"
    assert peer_indirect.addr == "192.168.1.10"
    assert peer_indirect.options.mtu == 1505
    assert peer_indirect.families == {"ipv6_unicast"}
    assert peer_indirect.remote_as == 12340
    assert peer_indirect.description == ""
