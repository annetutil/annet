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
        """

    def run_huawei(self, device: Device):
        executor = MeshExecutor(registry, device.storage)
        res = executor.execute_for(device)
        yield f"bgp {res.global_options.local_as}"


def get_generators(store: Storage) -> List[BaseGenerator]:
    return [
        Bgp(store),
    ]
