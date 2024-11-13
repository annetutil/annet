import pytest

from annet.mesh import MeshExecutor, MeshRulesRegistry, GlobalOptions, DirectPeer, MeshSession, IndirectPeer
from .fakes import FakeStorage, FakeDevice, FakeInterface

VRF = "testvrf"
GROUP = "test_group"
EXPORT_POLICY1 = "EXPORT_POLICY1"
EXPORT_POLICY2 = "EXPORT_POLICY2"

def on_device_x(device: GlobalOptions):
    device.vrf[VRF].groups[GROUP].mtu = 1499
    device.vrf[VRF].ipv4_unicast.aggregate.export_policy = EXPORT_POLICY1
    device.ipv6_unicast.aggregate.export_policy = EXPORT_POLICY2
    print(device.match.x)


def on_direct(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.1"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_unicast"}

def on_direct_alt(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.2"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_labeled"}


def on_indirect(local: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.10"
    local.mtu = 1505
    neighbor.mtu = 1506
    session.asnum = 12340
    session.families = {"ipv6_unicast"}


def on_indirect_alt(local: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.11"
    local.mtu = 1506
    neighbor.mtu = 1507
    session.asnum = 12340
    session.families = {"ipv6_unicast"}


@pytest.fixture
def registry():
    r = MeshRulesRegistry()
    r.device("{x:.*}")(on_device_x)
    r.direct("dev{num}.example.com", "dev_{x:.*}")(on_direct)
    r.direct("dev{num}.example.com", "dev_{x:.*}")(on_direct_alt)
    r.indirect("dev{num}.example.com", "dev{num}.remote.example.com")(on_indirect)
    r.indirect("dev{num}.example.com", "dev{num}.remote.example.com")(on_indirect_alt)
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

    assert res.global_options.ipv6_unicast.vrf_name == ""
    assert res.global_options.ipv6_unicast.family == "ipv6_unicast"
    assert res.global_options.ipv6_unicast.aggregate.export_policy == EXPORT_POLICY2

    assert res.global_options.groups == []
    assert res.global_options.vrf.keys() == {VRF}
    vrf = res.global_options.vrf[VRF]
    assert vrf.vrf_name == VRF
    assert vrf.static_label is None
    assert len(vrf.groups) == 1
    assert vrf.groups[0].mtu == 1499
    assert vrf.groups[0].name == GROUP
    assert vrf.ipv4_unicast.vrf_name == VRF
    assert vrf.ipv4_unicast.family == "ipv4_unicast"
    assert vrf.ipv4_unicast.aggregate.export_policy == EXPORT_POLICY1

    peer_direct, peer_direct_alt, peer_indirect, peer_indirect_alt = res.peers
    assert peer_direct.addr == "192.168.1.1"
    assert peer_direct.options.mtu == 1501
    assert peer_direct.families == {"ipv4_unicast"}
    assert peer_direct.remote_as == 12345
    assert peer_direct.description == ""
    assert peer_direct.interface == "if1"

    assert peer_direct_alt.addr == "192.168.1.2"
    assert peer_direct_alt.options.mtu == 1501
    assert peer_direct_alt.families == {"ipv4_labeled"}
    assert peer_direct_alt.remote_as == 12345
    assert peer_direct_alt.description == ""
    assert peer_direct_alt.interface == "if1"

    assert peer_indirect.addr == "192.168.1.10"
    assert peer_indirect.options.mtu == 1505
    assert peer_indirect.families == {"ipv6_unicast"}
    assert peer_indirect.remote_as == 12340
    assert peer_indirect.description == ""
    assert peer_indirect.interface is None

    assert peer_indirect_alt.addr == "192.168.1.11"
    assert peer_indirect_alt.options.mtu == 1506
    assert peer_indirect_alt.families == {"ipv6_unicast"}
    assert peer_indirect_alt.remote_as == 12340
    assert peer_indirect_alt.description == ""
    assert peer_indirect_alt.interface is None
