import pytest

from annet.bgp_models import BFDTimers, Redistribute
from annet.mesh import (
    MeshExecutor,
    MeshRulesRegistry,
    GlobalOptions,
    DirectPeer,
    MeshSession,
    IndirectPeer,
    VirtualLocal,
    VirtualPeer,
    separate_ports,
)
from .fakes import FakeStorage, FakeDevice, FakeInterface

VRF = "testvrf"
GROUP = "test_group"
EXPORT_POLICY1 = "EXPORT_POLICY1"
EXPORT_POLICY2 = "EXPORT_POLICY2"

def on_device_x(device: GlobalOptions):
    device.vrf[VRF].groups[GROUP].mtu = 1499
    device.vrf[VRF].groups[GROUP].local_as = 11111
    device.vrf[VRF].groups[GROUP].remote_as = 22222
    device.vrf[VRF].groups[GROUP].families = {"ipv4_unicast"}
    device.vrf[VRF].groups[GROUP].export_policy = EXPORT_POLICY1
    device.vrf[VRF].ipv4_unicast.aggregate.export_policy = EXPORT_POLICY1
    device.vrf[VRF].as_path_relax = True
    device.ipv6_unicast.aggregate.export_policy = EXPORT_POLICY2
    device.ipv4_unicast.redistributes = (Redistribute(
        protocol="ipv4", policy="sss",
    ),)


def on_direct(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.1"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.bfd_timers = BFDTimers(multiplier=1)
    session.families = {"ipv4_unicast"}

def on_direct_alt(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    local.addr = "192.168.1.254"
    neighbor.addr = "192.168.1.2"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_labeled_unicast"}


def on_indirect(local: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
    local.addr = "192.168.2.254"
    local.svi = 100
    neighbor.addr = "192.168.2.10"
    local.mtu = 1505
    neighbor.mtu = 1506
    session.asnum = 12340
    session.families = {"ipv6_unicast"}


def on_indirect_alt(local: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
    local.addr = "192.168.2.254"
    neighbor.addr = "192.168.2.11"
    local.mtu = 1506
    neighbor.mtu = 1507
    session.asnum = 12340
    session.families = {"ipv6_unicast"}


def on_virtual(local: VirtualLocal, virtual: VirtualPeer, session: MeshSession):
    local.svi = 1
    local.addr = "192.168.3.254"
    local.mtu = 1506
    local.listen_network = ["10.0.0.0/8"]
    virtual.addr = f"192.168.3.{virtual.num}"
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
    r.virtual("dev{num}.example.com", num=[10, 20, 30])(on_virtual)
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
    assert vrf.groups[0].local_as == 11111
    assert vrf.groups[0].remote_as == 22222
    assert vrf.groups[0].families == {"ipv4_unicast"}
    assert vrf.groups[0].name == GROUP
    assert vrf.groups[0].export_policy == EXPORT_POLICY1
    assert vrf.ipv4_unicast.vrf_name == VRF
    assert vrf.ipv4_unicast.family == "ipv4_unicast"
    assert vrf.ipv4_unicast.aggregate.export_policy == EXPORT_POLICY1
    assert vrf.as_path_relax

    res.peers.sort(key=lambda p: p.addr)
    peer_direct, peer_direct_alt, peer_indirect, peer_indirect_alt, *virtual = res.peers
    assert peer_direct.addr == "192.168.1.1"
    assert peer_direct.options.mtu == 1501
    assert peer_direct.families == {"ipv4_unicast"}
    assert peer_direct.remote_as == 12345
    assert peer_direct.description == ""
    assert peer_direct.interface == "if1"

    assert peer_direct_alt.addr == "192.168.1.2"
    assert peer_direct_alt.options.mtu == 1501
    assert peer_direct_alt.families == {"ipv4_labeled_unicast"}
    assert peer_direct_alt.remote_as == 12345
    assert peer_direct_alt.description == ""
    assert peer_direct_alt.interface == "if1"

    assert peer_indirect.addr == "192.168.2.10"
    assert peer_indirect.options.mtu == 1505
    assert peer_indirect.families == {"ipv6_unicast"}
    assert peer_indirect.remote_as == 12340
    assert peer_indirect.description == ""
    assert peer_indirect.interface == "Vlan100"

    assert peer_indirect_alt.addr == "192.168.2.11"
    assert peer_indirect_alt.options.mtu == 1506
    assert peer_indirect_alt.families == {"ipv6_unicast"}
    assert peer_indirect_alt.remote_as == 12340
    assert peer_indirect_alt.description == ""
    assert peer_indirect_alt.interface is None

    assert len(virtual) == 3
    assert virtual[0].addr == "192.168.3.10"
    assert virtual[1].addr == "192.168.3.20"
    assert virtual[2].addr == "192.168.3.30"
    for peer in virtual:
        assert peer.options.local_as == 12340
        assert peer.interface == "Vlan1"
        assert peer.options.listen_network == ["10.0.0.0/8"]


@pytest.fixture()
def device_2ports():
    return FakeDevice(DEV1, [])


@pytest.fixture()
def device_neighbor_2ports(device_2ports):
    device_2ports.interfaces.append(FakeInterface(
        name="if1",
        neighbor_fqdn=DEV_NEIGHBOR,
        neighbor_port="if10"
    ))
    device_2ports.interfaces.append(FakeInterface(
        name="if2",
        neighbor_fqdn=DEV_NEIGHBOR,
        neighbor_port="if11"
    ))
    return FakeDevice(DEV_NEIGHBOR, [
        FakeInterface(
            name="if10",
            neighbor_fqdn=DEV1,
            neighbor_port="if2"
        ),
        FakeInterface(
            name="if11",
            neighbor_fqdn=DEV1,
            neighbor_port="if1"
        ),
    ])


def on_direct_2ports(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    port_number = local.all_connected_ports.index(local.ports[0])+1
    local.addr = f"192.168.1.{port_number}"
    neighbor.addr = f"192.168.1.{255-port_number}"
    local.mtu = 1501
    neighbor.mtu = 1502
    session.asnum = 12345
    session.families = {"ipv4_unicast"}


@pytest.fixture
def storage_2ports(device_2ports, device_neighbor_2ports):
    s = FakeStorage()
    s.add_device(device_2ports)
    s.add_device(device_neighbor_2ports)
    return s


def test_2ports(storage_2ports, device_2ports):
    registry = MeshRulesRegistry()
    registry.direct("dev{num}.example.com", "dev_{x:.*}", port_processor=separate_ports)(on_direct_2ports)
    r = MeshExecutor(registry, storage_2ports)
    res = r.execute_for(device_2ports)

    peer_ports = [
        (peer.addr, peer.interface)
        for peer in res.peers
    ]
    peer_ports.sort()
    assert peer_ports == [
        ("192.168.1.253", "if2"),
        ("192.168.1.254", "if1"),
    ]

    local_ports = [
        (interface.addrs, interface.name)
        for interface in device_2ports.interfaces
    ]
    local_ports.sort()
    assert local_ports == [
        ([("192.168.1.1", None)], "if1"),
        ([("192.168.1.2", None)], "if2"),
    ]


def do_nothing(*args, **kwargs):
    return


def test_empty_handler(storage, device1):
    registry = MeshRulesRegistry()
    registry.direct("{x:.*}", "{y:.*}")(do_nothing)
    registry.indirect("{x:.*}", "{y:.*}")(do_nothing)
    registry.virtual("{x:.*}", [1])(do_nothing)
    registry.device("{x:.*}")(do_nothing)

    r = MeshExecutor(registry, storage)
    res = r.execute_for(device1)
    assert res.peers == []
