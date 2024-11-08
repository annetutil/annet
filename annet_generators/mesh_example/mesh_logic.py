from annet.mesh import Right, MeshRulesRegistry, GlobalOptions, MeshSession, DirectPeer

registry = MeshRulesRegistry()


@registry.device("{name:.*}")
def device_handler(global_opts: GlobalOptions):
    global_opts.local_as = 12345
    global_opts.groups["GROP_NAME"].remote_as = 11111


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}")
def direct_handler(device: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    session.asnum = 12345
    device.addr = "192.168.1.254"
    neighbor.addr = f"192.168.1.{neighbor.match.x}"


@registry.direct("{name:.*}", "m9-sgw{x}.{domain:.*}", Right.x.in_([0, 1]))
def direct_handler2(device: DirectPeer, neighbor: DirectPeer, session: MeshSession):
    session.asnum = 12345
    device.addr = "192.168.1.254/24"
    device.lag = 1
    device.lag_links_min = neighbor.match.x
    device.subif = 100
    neighbor.families = {"ipv4_unicast"}
    neighbor.group_name = "GROUP_NAME"
    neighbor.addr = "192.168.1.200/24"
