from typing import TypeVar

from annet.bgp_models import extract_policies
from annet.mesh import MeshExecutor
from annet.rpl import RouteMap, RoutingPolicy
from annet.storage import MeshDevice


DeviceT = TypeVar("DeviceT", bound=MeshDevice)


def get_policies(routemap: RouteMap[DeviceT], mesh_executor: MeshExecutor, device: DeviceT) -> list[RoutingPolicy]:
    allowed_policies = extract_policies(mesh_executor.execute_for(device))
    return routemap.apply(device, allowed_policies)
