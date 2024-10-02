from annet.mesh.peer_models import MeshPeerGroup
from annet.mesh.registry import MeshRulesRegistry, GlobalOptions, Session, DirectPeer

registry = MeshRulesRegistry()


@registry.device("{name:.*}")
def foo(global_opts: GlobalOptions):
    global_opts.local_as = 12345


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}")
def foo(device: DirectPeer, neighbor: DirectPeer, session: Session):
    neighbor.addr = f"127.0.0.{neighbor.matched.x}"


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}")
def foo(device: DirectPeer, neighbor: DirectPeer, session: Session):
    neighbor.group = MeshPeerGroup(
        name="GROUP_NAME",
        update_source="",
        remote_as=12345,
    )
