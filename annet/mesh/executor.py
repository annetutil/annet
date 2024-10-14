from dataclasses import dataclass
from typing import Annotated

from annet.bgp_models import Peer, GlobalOptions
from annet.storage import Device, Storage
from .basemodel import merge, BaseMeshModel, Merge, UseLast
from .device_models import GlobalOptionsDTO
from .models_converter import to_bgp_global_options, to_bgp_peer, InterfaceChanges, to_interface_changes
from .peer_models import PeerDTO
from .registry import MeshRulesRegistry, GlobalOptions as MeshGlobalOptions, DirectPeer, MeshSession, IndirectPeer


@dataclass
class MeshExecutionResult:
    global_options: GlobalOptions
    peers: list[Peer]


class Pair(BaseMeshModel):
    local: Annotated[PeerDTO, Merge()]
    connected: Annotated[PeerDTO, Merge()]
    device: Annotated[Device, UseLast()]


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
            rule_global_opts = MeshGlobalOptions(rule.match, device)
            rule.handler(rule_global_opts)
            global_opts = merge(global_opts, rule_global_opts)
        return global_opts

    def _execute_direct(self, device: Device) -> list[Pair]:
        # we can have multiple rules for the same pair
        # we merge them according to remote fqdn
        neighbor_peers: dict[str, Pair] = {}
        # TODO batch resolve
        for rule in self._registry.lookup_direct(device.fqdn, device.neighbours_fqdns):
            session = MeshSession()
            if rule.direct_order:
                neighbor_device = self._storage.make_devices([rule.name_right])[0]
                peer_device = DirectPeer(rule.match_left, device, [])
                peer_neighbor = DirectPeer(rule.match_right, neighbor_device, [])
            else:
                neighbor_device = self._storage.make_devices([rule.name_left])[0]
                peer_neighbor = DirectPeer(rule.match_left, neighbor_device, [])
                peer_device = DirectPeer(rule.match_right, device, [])

            interfaces = self._storage.search_connections(device, neighbor_device)
            for local_port, remote_port in interfaces:
                peer_device.ports.append(local_port.name)
                peer_neighbor.ports.append(remote_port.name)

            if rule.direct_order:
                rule.handler(peer_device, peer_neighbor, session)
            else:
                rule.handler(peer_neighbor, peer_device, session)

            # TODO log merge error with handlers
            neighbor_dto = merge(PeerDTO(), peer_neighbor, session)
            device_dto = merge(PeerDTO(), peer_device, session)
            pair = Pair(local=device_dto, connected=neighbor_dto, device=neighbor_device)
            if neighbor_device.fqdn in neighbor_peers:
                pair = merge(neighbor_peers[neighbor_device.fqdn], pair)
            neighbor_peers[neighbor_device.fqdn] = pair
        return list(neighbor_peers.values())

    def _execute_indirect(self, device: Device, all_fqdns: list[str]) -> list[Pair]:
        # we can have multiple rules for the same pair
        # we merge them according to remote fqdn
        connected_peers: dict[str, Pair] = {}
        for rule in self._registry.lookup_indirect(device.fqdn, all_fqdns):
            session = MeshSession()
            if rule.direct_order:
                connected_device = self._storage.make_devices([rule.name_right])[0]
                peer_device = IndirectPeer(rule.match_left, device)
                peer_connected = IndirectPeer(rule.match_right, connected_device)
                rule.handler(peer_device, peer_connected, session)
            else:
                connected_device = self._storage.make_devices([rule.name_left])[0]
                peer_connected = IndirectPeer(rule.match_left, connected_device)
                peer_device = IndirectPeer(rule.match_right, device)
                rule.handler(peer_connected, peer_device, session)

            # TODO log merge error with handlers
            connected_dto = merge(PeerDTO(), peer_connected, session)
            device_dto = merge(PeerDTO(), peer_device, session)
            pair = Pair(local=device_dto, connected=connected_dto, device=connected_device)
            if connected_device.fqdn in connected_peers:
                pair = merge(connected_peers[connected_device.fqdn], pair)
            connected_peers[connected_device.fqdn] = pair

        return list(connected_peers.values())  # FIXME

    def _to_bgp_peer(self, pair: Pair) -> Peer:
        return to_bgp_peer(pair.local, pair.connected, pair.device)

    def _to_bgp_global(self, global_options: GlobalOptionsDTO) -> GlobalOptions:
        # TODO group options defaults
        return to_bgp_global_options(global_options)

    def _apply_interface_changes(self, device: Device, neighbor: Device, changes: InterfaceChanges) -> None:
        port_pairs = self._storage.search_connections(device, neighbor)
        if len(port_pairs) > 1:
            if changes.lag is changes.svi is None:
                raise ValueError(
                    f"Multiple connections found between {device.fqdn} and {neighbor.fqdn}."
                    "Specify LAG or SVI"
                )
        if changes.lag is not None:
            target_interface = device.make_lag(
                lag=changes.lag,
                ports=[local_port.name for local_port, remote_port in port_pairs],
                lag_min_links=changes.lag_links_min,
            )
            if changes.subif is not None:
                target_interface = device.add_subif(target_interface.name, changes.subif)
        elif changes.subif is not None:
            # single connection
            local_port, remote_port = port_pairs[0]
            target_interface = device.add_subif(local_port.name, changes.subif)
        elif changes.svi is not None:
            target_interface = device.add_svi(changes.svi)
        else:
            target_interface, _ = port_pairs[0]
        target_interface.add_addr(changes.addr, changes.vrf)

    def execute_for(self, device: Device) -> MeshExecutionResult:
        all_fqdns = self._storage.resolve_all_fdnds()
        result = []

        for neighbor in self._execute_direct(device):
            result.append(self._to_bgp_peer(neighbor))
            self._apply_interface_changes(device, neighbor.device, to_interface_changes(neighbor.local))

        for connected in self._execute_indirect(device, all_fqdns):
            result.append(self._to_bgp_peer(connected))

        return MeshExecutionResult(
            global_options=self._to_bgp_global(self._execute_globals(device)),
            peers=result,
        )
