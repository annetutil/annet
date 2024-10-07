from typing import List

from annet.generators import PartialGenerator, BaseGenerator
from annet.mesh.executor import MeshExecutor
from annet.storage import Device, Storage
from .mesh_logic import registry


class Bgp(PartialGenerator):
    TAGS = ["mgmt", "bgp"]

    def acl_huawei(self, device):
        return """
        bgp
            peer
        """

    def run_huawei(self, device: Device):
        executor = MeshExecutor(registry, device.storage)
        res = executor.execute_for(device)
        yield f"bgp {res.global_options.local_as}"
        for peer in res.peers:
            if peer.group_name:
                yield f"   peer {peer.addr} {peer.group_name}"
        for group in res.global_options.groups:
            yield f"   peer {group.name} remote-as {group.remote_as}"


def get_generators(store: Storage) -> List[BaseGenerator]:
    return [
        Bgp(store),
    ]
