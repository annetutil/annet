from dataclasses import dataclass
from logging import getLogger
from typing import Annotated, Callable, Optional, Union

from annet.bgp_models import Peer, GlobalOptions
from annet.storage import Device, Storage
from .basemodel import merge, BaseMeshModel, Merge, UseLast, MergeForbiddenError
from .device_models import GlobalOptionsDTO
from .models_converter import to_bgp_global_options, to_bgp_peer, InterfaceChanges, to_interface_changes
from .peer_models import DirectPeerDTO, IndirectPeerDTO, VirtualLocalDTO, VirtualPeerDTO
from .registry import (
    DirectPeer,
    GlobalOptions as MeshGlobalOptions,
    IndirectPeer,
    MeshRulesRegistry,
    MeshSession,
    VirtualLocal,
    VirtualPeer,
)

logger = getLogger(__name__)


@dataclass
class MeshExecutionResult:
    global_options: GlobalOptions
    peers: list[Peer]


@dataclass(frozen=True)
class PeerKey:
    fqdn: str
    addr: str
    vrf: str


class Pair(BaseMeshModel):
    local: Annotated[Union[DirectPeerDTO, IndirectPeerDTO], Merge()]
    connected: Annotated[Union[DirectPeerDTO, IndirectPeerDTO], Merge()]
    device: Annotated[Device, UseLast()]


class VirtualPair(BaseMeshModel):
    local: Annotated[VirtualLocalDTO, Merge()]
    connected: Annotated[VirtualPeerDTO, Merge()]


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
            handler_name = self._handler_name(rule.handler)
            rule_global_opts = MeshGlobalOptions(rule.match, device)
            logger.debug("Running device handler: %s", handler_name)
            rule.handler(rule_global_opts)
            try:
                global_opts = merge(global_opts, rule_global_opts)
            except MergeForbiddenError as e:
                raise ValueError(
                    f"Handler `{handler_name}` global options conflicting with "
                    f"previously loaded for device `{device.fqdn}`:\n" + str(e)
                ) from e
        return global_opts

    def _handler_name(self, handler: Callable) -> str:
        try:
            return f"{handler.__module__}.{handler.__qualname__}"
        except AttributeError:
            return str(handler)

    def _execute_direct(self, device: Device) -> list[Pair]:
        # we can have multiple rules for the same pair
        # we merge them according to remote fqdn
        neighbor_peers: dict[PeerKey, Pair] = {}
        # TODO batch resolve
        for rule in self._registry.lookup_direct(device.fqdn, device.neighbours_fqdns):
            session = MeshSession()
            handler_name = self._handler_name(rule.handler)
            logger.debug("Running direct handler: %s", handler_name)
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

            try:
                neighbor_dto = merge(DirectPeerDTO(), peer_neighbor, session)
            except MergeForbiddenError as e:
                raise ValueError(
                    f"Handler `{handler_name}` provided session data conflicting with "
                    f"peer data for device `{neighbor_device.fqdn}`:\n" + str(e)
                ) from e
            try:
                device_dto = merge(DirectPeerDTO(), peer_device, session)
            except MergeForbiddenError as e:
                raise ValueError(
                    f"Handler `{handler_name}` provided session data conflicting with "
                    f"peer data for device `{device.fqdn}`:\n" + str(e)
                ) from e

            pair = Pair(local=device_dto, connected=neighbor_dto, device=neighbor_device)
            addr = getattr(neighbor_dto, "addr", None)
            if addr is None:
                raise ValueError(f"Handler `{handler_name}` returned no peer addr")
            peer_key = PeerKey(
                fqdn=neighbor_device.fqdn,
                addr=addr,
                vrf=getattr(neighbor_dto, "vrf", "")
            )
            try:
                if peer_key in neighbor_peers:
                    pair = merge(neighbor_peers[peer_key], pair)
            except MergeForbiddenError as e:
                if rule.direct_order:
                    pair_names = device.fqdn, neighbor_device.fqdn
                else:
                    pair_names = neighbor_device.fqdn, device.fqdn
                raise ValueError(
                    f"Handler `{handler_name}` provides data conflicting with "
                    f"previously loaded for device pair {pair_names} "
                    f"with addr={peer_key.addr}, vrf{peer_key.vrf}:\n" + str(e)
                ) from e
            neighbor_peers[peer_key] = pair
        return list(neighbor_peers.values())

    def _execute_virtual(self, device: Device) -> list[VirtualPair]:
        virtual_peers: list[VirtualPair] = []
        for rule in self._registry.lookup_virtual(device.fqdn):
            for order_number in rule.num:
                handler_name = self._handler_name(rule.handler)
                logger.debug("Running direct handler: %s", handler_name)
                session = MeshSession()
                peer_device = VirtualLocal(rule.match, device)
                peer_virtual = VirtualPeer(num=order_number)

                rule.handler(peer_device, peer_virtual, session)

                try:
                    virtual_dto = merge(VirtualPeerDTO(), peer_virtual, session)
                except MergeForbiddenError as e:
                    raise ValueError(
                        f"Handler `{handler_name}` provided session data conflicting with "
                        f"virtual peer data for device `{device.fqdn}` and num={order_number}:\n" + str(e)
                    ) from e
                try:
                    device_dto = merge(VirtualLocalDTO(), peer_device, session)
                except MergeForbiddenError as e:
                    raise ValueError(
                        f"Handler `{handler_name}` provided session data conflicting with "
                        f"peer data for device `{device.fqdn}`:\n" + str(e)
                    ) from e

                if not hasattr(device_dto, "svi"):
                    raise ValueError(
                        f"Handler `{handler_name}` did not provide `svi` number. "
                        "Virtual peer must be connected to SVI interface."
                    )
                pair = VirtualPair(local=device_dto, connected=virtual_dto)
                virtual_peers.append(pair)
        return virtual_peers

    def _execute_indirect(self, device: Device, all_fqdns: list[str]) -> list[Pair]:
        # we can have multiple rules for the same pair
        # we merge them according to remote fqdn
        connected_peers: dict[PeerKey, Pair] = {}
        for rule in self._registry.lookup_indirect(device.fqdn, all_fqdns):
            session = MeshSession()
            handler_name = self._handler_name(rule.handler)
            logger.debug("Running indirect handler: %s", handler_name)
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

            try:
                connected_dto = merge(IndirectPeerDTO(), peer_connected, session)
            except MergeForbiddenError as e:
                raise ValueError(
                    f"Handler `{handler_name}` provided session data conflicting with "
                    f"peer data for device `{connected_device.fqdn}`:\n" + str(e)
                ) from e
            try:
                device_dto = merge(IndirectPeerDTO(), peer_device, session)
            except MergeForbiddenError as e:
                raise ValueError(
                    f"Handler `{handler_name}` provided session data conflicting with "
                    f"peer data for device `{device.fqdn}`:\n" + str(e)
                ) from e

            pair = Pair(local=device_dto, connected=connected_dto, device=connected_device)
            addr = getattr(connected_dto, "addr", None)
            if addr is None:
                raise ValueError(f"Handler `{handler_name}` returned no peer addr")
            peer_key = PeerKey(
                fqdn=connected_device.fqdn,
                addr=addr,
                vrf=getattr(connected_dto, "vrf", "")
            )
            try:
                if peer_key in connected_peers:
                    pair = merge(connected_peers[peer_key], pair)
            except MergeForbiddenError as e:
                if rule.direct_order:
                    pair_names = device.fqdn, connected_device.fqdn
                else:
                    pair_names = connected_device.fqdn, device.fqdn
                raise ValueError(
                    f"Handler `{handler_name}` provides data conflicting with "
                    f"previously loaded for device pair {pair_names} "
                    f"with addr={peer_key.addr}, vrf{peer_key.vrf}:\n" + str(e)
                ) from e
            connected_peers[peer_key] = pair

        return list(connected_peers.values())  # FIXME

    def _to_bgp_peer(self, pair: Pair, interface: Optional[str]) -> Peer:
        return to_bgp_peer(pair.local, pair.connected, pair.device.hostname, interface)

    def _virtual_to_bgp_peer(self, pair: VirtualPair, interface: Optional[str]) -> Peer:
        return to_bgp_peer(pair.local, pair.connected, "", interface)

    def _to_bgp_global(self, global_options: GlobalOptionsDTO) -> GlobalOptions:
        return to_bgp_global_options(global_options)

    def _apply_interface_changes(self, device: Device, neighbor: Device, changes: InterfaceChanges) -> str:
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
        return target_interface.name

    def _apply_virtual_interface_changes(self, device: Device, local: VirtualLocalDTO) -> str:
        return device.add_svi(local.svi).name  # we check if SVI configured in execute method

    def execute_for(self, device: Device) -> MeshExecutionResult:
        all_fqdns = self._storage.resolve_all_fdnds()

        global_options = self._to_bgp_global(self._execute_globals(device))

        peers = []
        for direct_pair in self._execute_direct(device):
            target_interface = self._apply_interface_changes(
                device,
                direct_pair.device,
                to_interface_changes(direct_pair.local),
            )
            peers.append(self._to_bgp_peer(direct_pair, target_interface))

        for virtual_pair in self._execute_virtual(device):
            target_interface = self._apply_virtual_interface_changes(
                device,
                virtual_pair.local,
            )
            peers.append(self._virtual_to_bgp_peer(virtual_pair, target_interface))

        for connected_pair in self._execute_indirect(device, all_fqdns):
            peers.append(self._to_bgp_peer(connected_pair, None))

        return MeshExecutionResult(
            global_options=global_options,
            peers=peers,
        )
