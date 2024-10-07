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
    neighbor.addr = f"127.0.0.{neighbor.matched.x}"


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}")
def bar(device: DirectPeer, neighbor: DirectPeer, session: Session):
    session.asnum = 12345
    neighbor.name = "NEIGHBOR"
    neighbor.families = {"ipv4-unicast"}
    neighbor.group_name = "GROUP_NAME"

    device.name = "DEVICE"
