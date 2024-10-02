from dataclasses import dataclass
from typing import Callable, Any

from .match_args import MatchExpr, PairMatcher, SingleMatcher
from .match_args import MatchedArgs
from .device_models import GlobalOptionsDTO
from .peer_models import PeerDTO, SessionDTO


class DirectPeer(PeerDTO):
    def __init__(self, matched: MatchedArgs, device: Any, ports: list[str]) -> None:
        super().__init__()
        self.matched = matched
        self.device = device
        self.ports = ports


class IndirectPeer(PeerDTO):
    def __init__(self, matched: MatchedArgs, device: Any) -> None:
        super().__init__()
        self.matched = matched
        self.device = device


class Session(SessionDTO):
    pass


class GlobalOptions(GlobalOptionsDTO):
    def __init__(self, matched: MatchedArgs, device: Any) -> None:
        super().__init__()
        self.matched = matched
        self.device = device


GlobalHandler = Callable[[GlobalOptions], None]


@dataclass(slots=True)
class GlobalRule:
    matcher: SingleMatcher
    handler: GlobalHandler


DirectHandler = Callable[[DirectPeer, DirectPeer, Session], None]
IndirectHandler = Callable[[IndirectPeer, IndirectPeer, Session], None]


@dataclass(slots=True)
class DirectRule:
    matcher: PairMatcher
    handler: DirectHandler


@dataclass(slots=True)
class IndirectRule:
    matcher: PairMatcher
    handler: IndirectHandler


@dataclass(slots=True)
class MatchedGlobal:
    handler: GlobalHandler
    matched: MatchedArgs


@dataclass(slots=True)
class MatchedDirectPair:
    handler: DirectHandler
    direct_order: bool
    name_left: str
    name_right: str
    matched_left: MatchedArgs
    matched_right: MatchedArgs


@dataclass(slots=True)
class MatchedIndirectPair:
    handler: IndirectHandler
    direct_order: bool
    name_left: str
    name_right: str
    matched_left: MatchedArgs
    matched_right: MatchedArgs


class MeshRulesRegistry:
    def __init__(self):
        self.direct_rules: list[DirectRule] = []
        self.indirect_rules: list[IndirectRule] = []
        self.global_rules: list[GlobalRule] = []
        self.nested: list[MeshRulesRegistry] = []

    def include(self, nested_registry: "MeshRulesRegistry") -> None:
        self.nested.append(nested_registry)

    def device(self, peer_mask: str, match: MatchExpr | None = None) -> Callable[[GlobalHandler], GlobalHandler]:
        matcher = SingleMatcher(peer_mask, match)

        def register(handler: GlobalHandler) -> GlobalHandler:
            self.global_rules.append(GlobalRule(matcher, handler))
            return handler

        return register

    def direct(
            self, left_mask: str, right_mask: str, match: MatchExpr | None = None,
    ) -> Callable[[DirectHandler], DirectHandler]:
        matcher = PairMatcher(left_mask, right_mask, match)

        def register(handler: DirectHandler) -> DirectHandler:
            self.direct_rules.append(DirectRule(matcher, handler))
            return handler

        return register

    def indirect(
            self, left_mask: str, right_mask: str, match: MatchExpr | None = None,
    ) -> Callable[[IndirectHandler], IndirectHandler]:
        matcher = PairMatcher(left_mask, right_mask, match)

        def register(handler: IndirectHandler) -> IndirectHandler:
            self.indirect_rules.append(IndirectRule(matcher, handler))
            return handler

        return register

    def lookup_direct(self, device: str, neighbors: list[str]) -> list[MatchedDirectPair]:
        found = []
        for neighbor in neighbors:
            for rule in self.direct_rules:
                if args := rule.matcher.match_pair(device, neighbor):
                    found.append(MatchedDirectPair(
                        handler=rule.handler,
                        direct_order=True,
                        name_left=device,
                        name_right=neighbor,
                        matched_left=args[0],
                        matched_right=args[1],
                    ))
                if args := rule.matcher.match_pair(device, neighbor):
                    found.append(MatchedDirectPair(
                        handler=rule.handler,
                        direct_order=False,
                        name_left=neighbor,
                        name_right=device,
                        matched_left=args[0],
                        matched_right=args[1],
                    ))
        for registry in self.nested:
            found.extend(registry.lookup_direct(device, neighbors))
        return found

    def lookup_indirect(self, device: str, devices: list[str]) -> list[MatchedIndirectPair]:
        found = []
        for other_device in devices:
            for rule in self.indirect_rules:
                if args := rule.matcher.match_pair(device, other_device):
                    found.append(MatchedIndirectPair(
                        handler=rule.handler,
                        direct_order=True,
                        name_left=device,
                        name_right=other_device,
                        matched_left=args[0],
                        matched_right=args[1],
                    ))
                if args := rule.matcher.match_pair(device, other_device):
                    found.append(MatchedIndirectPair(
                        handler=rule.handler,
                        direct_order=False,
                        name_left=other_device,
                        name_right=device,
                        matched_left=args[0],
                        matched_right=args[1],
                    ))
        for registry in self.nested:
            found.extend(registry.lookup_indirect(device, devices))
        return found

    def lookup_global(self, device: str) -> list[MatchedGlobal]:
        found = []
        for rule in self.global_rules:
            if args := rule.matcher.match_one(device):
                found.append(MatchedGlobal(
                    handler=rule.handler,
                    matched=args,
                ))
        for registry in self.nested:
            found.extend(registry.lookup_global(device))
        return found
