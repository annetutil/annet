from dataclasses import dataclass
from typing import Protocol, TypeVar

from .basemodel import merge
from .models import GlobalOptionsDTO, PeerDTO
from .registry import MeshRulesRegistry, GlobalOptions, DirectPeer, Session, IndirectPeer
from annet.storage import Device, Storage


@dataclass
class MeshExecutionResult:
    global_options: GlobalOptionsDTO
    peer: PeerDTO


T = TypeVar('T')


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
            rule_global_opts = GlobalOptions(rule.matched, device)
            rule.handler(rule_global_opts)
            global_opts = merge(global_opts, rule_global_opts)
        return merge(GlobalOptionsDTO.default(), global_opts)

    def _execute_direct(self, device: Device) -> PeerDTO:
        result = PeerDTO()

        neighbors = {n.fqdn: n for n in device.neighbours}
        for rule in self._registry.lookup_direct(device.fqdn, list(neighbors)):
            # TODO find matched ports
            if rule.direct_order:
                peer_left = DirectPeer(rule.matched_left, device, [])
                peer_right = DirectPeer(rule.matched_right, neighbors[rule.name_right], [])
            else:
                peer_left = DirectPeer(rule.matched_left, neighbors[rule.name_left], [])
                peer_right = DirectPeer(rule.matched_right, device, [])
            rule_session = Session()
            rule.handler(peer_left, peer_right, rule_session)
            result = merge(result, peer_left, rule_session)
        return result

    def _execute_indirect(
            self, device: Device, all_fqdns: list[str],
    ) -> PeerDTO:
        result = PeerDTO()

        for rule in self._registry.lookup_indirect(device.fqdn,all_fqdns):
            if rule.direct_order:
                connected_device = self._storage.make_devices(rule.name_right)[0]
                peer_left = IndirectPeer(rule.matched_left, device)
                peer_right = IndirectPeer(rule.matched_right, connected_device)
            else:
                connected_device = self._storage.make_devices(rule.name_left)[0]
                peer_left = IndirectPeer(rule.matched_left, connected_device)
                peer_right = IndirectPeer(rule.matched_right, device)

            session = Session()
            rule.handler(peer_left, peer_right, session)
            result = merge(result, peer_left, session)
        return result

    def execute_for(self, device: Device) -> MeshExecutionResult:
        all_fqdns = self._storage.resolve_all_fdnds()
        return MeshExecutionResult(
            self._execute_globals(device),
            merge(
                self._execute_direct(device),
                self._execute_indirect(device, all_fqdns),
                # TODO merge default
            )
        )
