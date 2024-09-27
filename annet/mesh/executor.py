from dataclasses import dataclass
from typing import Protocol, TypeVar

from .basemodel import merge
from .models import GlobalOptionsDTO, PeerDTO
from .registry import MeshRulesRegistry, GlobalOptions, DirectPeer, Session, IndirectPeer
from ..storage import Device


@dataclass
class MeshExecutionResult:
    global_options: GlobalOptionsDTO
    peer: PeerDTO


T = TypeVar('T')


class MeshExecutor:
    def __init__(self, registry: MeshRulesRegistry):
        self._registry = registry

    def _execute_globals(self, device: Device) -> GlobalOptionsDTO:
        global_opts = GlobalOptionsDTO()
        for rule in self._registry.lookup_global(device.fqdn):
            rule_global_opts = GlobalOptions(rule.matched, device)
            rule.handler(rule_global_opts)
            global_opts = merge(global_opts, rule_global_opts)
        return merge(GlobalOptionsDTO.default(), global_opts)

    def _execute_direct(
            self, device: Device, all_devices: dict[str, Device],
    ) -> PeerDTO:
        left = PeerDTO()

        neighbors = [n.fqdn for n in device.neighbours]

        for rule in self._registry.lookup_direct(device.fqdn, neighbors):
            if rule.direct_order:
                rule_left = DirectPeer(rule.matched_left, device, [])
                rule_right = DirectPeer(rule.matched_right, all_devices[rule.name_right], [])
                rule_session = Session()
                rule.handler(rule_left, rule_right, rule_session)
                left = merge(left, rule_left, rule_session)
            else:
                rule_left = DirectPeer(rule.matched_left, all_devices[rule.name_left], [])
                rule_right = DirectPeer(rule.matched_right, device, [])
                rule_session = Session()
                rule.handler(rule_left, rule_right, rule_session)
                left = merge(left, rule_left, rule_session)
        return left

    def _execute_indirect(
            self, device: Device, all_devices: dict[str, Device],
    ) -> PeerDTO:
        left = PeerDTO()

        for rule in self._registry.lookup_indirect(device.fqdn, list(all_devices)):
            if rule.direct_order:
                rule_left = IndirectPeer(rule.matched_left, device)
                rule_right = IndirectPeer(rule.matched_right, all_devices[rule.name_right])
                rule_session = Session()
                rule.handler(rule_left, rule_right, rule_session)
                left = merge(left, rule_left, rule_session)
            else:
                rule_left = IndirectPeer(rule.matched_left, all_devices[rule.name_left])
                rule_right = IndirectPeer(rule.matched_right, device)
                rule_session = Session()
                rule.handler(rule_left, rule_right, rule_session)
                left = merge(left, rule_left, rule_session)
        return left

    def execute_for(self, device: Device, all_devices: dict[str, Device]) -> MeshExecutionResult:
        return MeshExecutionResult(
            self._execute_globals(device),
            merge(
                self._execute_direct(device, all_devices),
                self._execute_indirect(device, all_devices),
                # TODO merge default
            )
        )
