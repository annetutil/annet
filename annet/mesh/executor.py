from dataclasses import dataclass

from annet.bgp_models import Peer, GlobalOptions
from annet.storage import Device, Storage
from .basemodel import merge
from .device_models import GlobalOptionsDTO
from .models_converter import to_bgp_global_options, to_bgp_peer
from .peer_models import PeerDTO
from .registry import MeshRulesRegistry, GlobalOptions as MeshGloabalsOptions, DirectPeer, Session, IndirectPeer


@dataclass
class MeshExecutionResult:
    global_options: GlobalOptions
    peers: list[Peer]


class MeshExecutor:
    def __init__(
            self,
            registry: MeshRulesRegistry,
            storage: Storage,
    ):
        self._registry = registry
        self._storage = storage

    def _execute_globals(self, device: Device) -> GlobalOptionsDTO:
        global_opts = GlobalOptionsDTO()
        for rule in self._registry.lookup_global(device.fqdn):
            rule_global_opts = MeshGloabalsOptions(rule.matched, device)
            rule.handler(rule_global_opts)
            global_opts = merge(global_opts, rule_global_opts)
        return global_opts

    def _execute_direct(self, device: Device) -> list[PeerDTO]:
        neighbors = {n.fqdn: n for n in device.neighbours}
        neighbor_peers: dict[str, PeerDTO] = {}
        for rule in self._registry.lookup_direct(device.fqdn, list(neighbors)):
            # TODO find matched ports
            session = Session()
            if rule.direct_order:
                peer_device = DirectPeer(rule.matched_left, device, [])
                peer_neighbor = DirectPeer(rule.matched_right, neighbors[rule.name_right], [])
                rule.handler(peer_device, peer_neighbor, session)
            else:
                peer_neighbor = DirectPeer(rule.matched_left, neighbors[rule.name_left], [])
                peer_device = DirectPeer(rule.matched_right, device, [])
                rule.handler(peer_neighbor, peer_device, session)

            neighbor_result = neighbor_peers.get(peer_neighbor.device.fqdn) or PeerDTO()
            neighbor_peers[peer_neighbor.device.fqdn] = merge(neighbor_result, peer_neighbor, session)
        return list(neighbor_peers.values())

    def _execute_indirect(self, device: Device, all_fqdns: list[str]) -> list[PeerDTO]:
        connected_peers: dict[str, PeerDTO] = {}
        for rule in self._registry.lookup_indirect(device.fqdn, all_fqdns):
            session = Session()
            if rule.direct_order:
                connected_device = self._storage.make_devices(rule.name_right)[0]
                peer_device = IndirectPeer(rule.matched_left, device)
                peer_connected = IndirectPeer(rule.matched_right, connected_device)
                rule.handler(peer_device, peer_connected, session)
            else:
                connected_device = self._storage.make_devices(rule.name_left)[0]
                peer_connected = IndirectPeer(rule.matched_left, connected_device)
                peer_device = IndirectPeer(rule.matched_right, device)
                rule.handler(peer_connected, peer_device, session)

            neighbor_result = connected_peers.get(peer_connected.device.fqdn) or PeerDTO()
            connected_peers[peer_connected.device.fqdn] = merge(neighbor_result, peer_connected, session)
        return list(connected_peers.values())

    def _to_bgp_peer(self, peer: PeerDTO) -> Peer:
        return to_bgp_peer(peer)

    def _to_bgp_global(self, global_options: GlobalOptionsDTO) -> GlobalOptions:
        return to_bgp_global_options(global_options)

    def execute_for(self, device: Device) -> MeshExecutionResult:
        all_fqdns = self._storage.resolve_all_fdnds()
        result = []
        for neighbor in self._execute_direct(device):
            result.append(self._to_bgp_peer(neighbor))
        for connected in self._execute_indirect(device, all_fqdns):
            result.append(self._to_bgp_peer(connected))

        return MeshExecutionResult(
            global_options=self._to_bgp_global(self._execute_globals(device)),
            peers=result,
        )
