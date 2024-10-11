from annet.mesh.match_args import Right
from annet.mesh.peer_models import MeshPeerGroup
from annet.mesh.registry import MeshRulesRegistry, GlobalOptions, Session, DirectPeer

registry = MeshRulesRegistry()


@registry.device("{name:.*}")
def foo(global_opts: GlobalOptions):
    global_opts.local_as = 12345
    global_opts.groups.append(MeshPeerGroup(
        name="GROUP_NAME",
        remote_as=11111,
    ))


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}")
def foo(device: DirectPeer, neighbor: DirectPeer, session: Session):
    session.asnum = 12345
    neighbor.addr = f"192.168.1.{neighbor.matched.x}"


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}", Right.x.in_([0, 1]))
def bar(device: DirectPeer, neighbor: DirectPeer, session: Session):
    session.asnum = 12345
    device.addr = "192.168.1.254/24"
    device.lag = 1
    device.lag_links_min = neighbor.matched.x
    device.subif = 100
    neighbor.name = "NEIGHBOR"
    neighbor.families = {"ipv4-unicast"}
    neighbor.group_name = "GROUP_NAME"

    device.name = "DEVICE"