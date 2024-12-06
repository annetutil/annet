from abc import abstractmethod, ABC
from collections.abc import Sequence
from ipaddress import ip_interface
from typing import Any, Literal, Iterable, Iterator, Optional, cast

from annet.generators import PartialGenerator, Entire
from annet.rpl import (
    RouteMap, RoutingPolicy, PrefixMatchValue, SingleCondition, MatchField, RoutingPolicyStatement, ResultType,
    SingleAction, ConditionOperator, ThenField, ActionType,
)
from annet.rpl.statement_builder import NextHopActionValue, AsPathActionValue, CommunityActionValue
from .entities import IpPrefixList, mangle_ranged_prefix_list_name, CommunityList, CommunityLogic, CommunityType
from .prefix_lists import get_used_prefix_lists

FRR_RESULT_MAP = {
    ResultType.ALLOW: "permit",
    ResultType.DENY: "deny",
    ResultType.NEXT: "permit",
}
FRR_MATCH_COMMAND_MAP: dict[str, str] = {
    MatchField.as_path_filter: "as-path-list {option_value}",
    MatchField.metric: "metric {option_value}",
    MatchField.protocol: "source-protocol {option_value}",
    MatchField.interface: "interface {option_value}",
    # unsupported: as_path_length
    # unsupported: rd
}
FRR_THEN_COMMAND_MAP: dict[str, str] = {
    ThenField.local_pref: "local-preference {option_value}",
    ThenField.metric_type: "metric-type {option_value}",
    ThenField.origin: "origin {option_value}",
    ThenField.tag: "tag {option_value}",
    # unsupported: resolution
    # unsupported: rpki_valid_state
    # unsupported: mpls-label
}

FRR_INDENT = " "


def mangle_united_community_list_name(values: Sequence[str]) -> str:
    return "_OR_".join(values)


class CumulusPolicyGenerator(Entire, ABC):
    @abstractmethod
    def get_routemap(self) -> RouteMap:
        raise NotImplementedError()

    @abstractmethod
    def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        raise NotImplementedError()

    @abstractmethod
    def get_community_lists(self, device: Any) -> list[CommunityList]:
        raise NotImplementedError()

    def generate_cumulus_rpl(self, device: Any) -> Sequence[Sequence[[str]]]:
        policies = self.get_routemap().apply(device)
        communities = {c.name: c for c in self._get_used_community_lists(
            communities=self.get_community_lists(device),
            policies=policies,
        )}
        yield from self._cumulus_communities(device, communities, policies)
        yield from self._cumulus_prefix_lists(device, policies)
        yield from self._cumulus_policy_config(device, communities, policies)

    def _cumulus_prefix_list(
            self,
            name: str,
            ip_type: Literal["ipv6", "ip"],
            match: PrefixMatchValue,
            plist: IpPrefixList,
    ) -> Iterable[Sequence[str]]:
        for i, prefix in enumerate(plist.members):
            addr_mask = ip_interface(prefix)
            yield (
                ip_type,
                "prefix-list",
                name,
                f"index {i * 10}",
                "permit", f"{addr_mask.ip}/{addr_mask.hostmask.max_prefixlen}",
            ) + (
                ("le", str(match.less_equal)) if match.less_equal is not None else ()
            ) + (
                ("ge", str(match.greater_equal)) if match.greater_equal is not None else ()
            )

    def _cumulus_prefix_lists(self, device: Any, policies: list[RoutingPolicy]) -> Iterable[Sequence[str]]:
        plists = {p.name: p for p in get_used_prefix_lists(
            prefix_lists=self.get_prefix_lists(device),
            policies=policies,
        )}
        precessed_names = set()
        for policy in policies:
            for statement in policy.statements:
                cond: SingleCondition[PrefixMatchValue]
                for cond in statement.match.find_all(MatchField.ip_prefix):
                    for name in cond.value.names:
                        mangled_name = mangle_ranged_prefix_list_name(
                            name=name,
                            greater_equal=cond.value.greater_equal,
                            less_equal=cond.value.less_equal,
                        )
                        if mangled_name in precessed_names:
                            continue
                        yield from self._cumulus_prefix_list(mangled_name, "ip", cond.value, plists[name])
                        precessed_names.add(mangled_name)
                for cond in statement.match.find_all(MatchField.ipv6_prefix):
                    for name in cond.value.names:
                        mangled_name = mangle_ranged_prefix_list_name(
                            name=name,
                            greater_equal=cond.value.greater_equal,
                            less_equal=cond.value.less_equal,
                        )
                        if mangled_name in precessed_names:
                            continue
                        yield from self._cumulus_prefix_list(mangled_name, "ipv6", cond.value, plists[name])
                        precessed_names.add(mangled_name)
            yield "!"

    def _get_used_community_lists(self, communities: list[CommunityList], policies: list[RoutingPolicy]) -> list[
        CommunityList]:
        communities_dict = {c.name: c for c in communities}
        used_communities: set[str] = set()
        for policy in policies:
            for statement in policy.statements:
                condition: SingleCondition[Sequence[str]]
                for match_field in (
                        MatchField.community, MatchField.large_community,
                        MatchField.extcommunity_rt, MatchField.extcommunity_soo
                ):
                    for condition in statement.match.find_all(match_field):
                        if condition.operator == ConditionOperator.HAS_ANY and len(condition.value) > 1:
                            united_name = mangle_united_community_list_name(condition.value)
                            united_communities = [
                                communities_dict[name] for name in condition.value
                            ]
                            if not all(united_communities[0].type == c.type for c in united_communities):
                                raise ValueError(
                                    f"Cannot apply HAS_ANY to communities of different types, "
                                    f"found for policy: `{policy.name}`, statement: {statement.name}"
                                )
                            if not all(united_communities[0].use_regex == c.use_regex for c in united_communities):
                                raise ValueError(
                                    f"Cannot apply HAS_ANY to communities with different use_regex flag, "
                                    f"found for policy: `{policy.name}`, statement: {statement.name}"
                                )
                            if any(c.logic is CommunityLogic.AND and len(c.members) > 1 for c in united_communities):
                                raise ValueError(
                                    f"Cannot use community list with AND logic for HAS_ANY rule, "
                                    f"found for policy: `{policy.name}`, statement: {statement.name}"
                                )
                            members = set()
                            for clist in united_communities:
                                members.update(clist.members)
                            communities_dict[united_name] = CommunityList(
                                name=united_name,
                                use_regex=united_communities[0].use_regex,
                                type=united_communities[0].type,
                                logic=CommunityLogic.OR,
                                members=list(members),
                            )
                            used_communities.add(united_name)
                        else:
                            used_communities.update(condition.value)
                for then_field in (
                        ThenField.community, ThenField.large_community,
                        ThenField.extcommunity_rt, ThenField.extcommunity_soo
                ):
                    for action in statement.then.find_all(then_field):
                        if action.value.replaced is not None:
                            used_communities.update(action.value.replaced)
                        used_communities.update(action.value.added)
                        used_communities.update(action.value.removed)
        return [
            communities_dict[name] for name in used_communities
        ]

    def _cumulus_communities(
            self,
            device: Any,
            communities: dict[str, CommunityList],
            policies: list[RoutingPolicy],
    ) -> Iterable[Sequence[str]]:
        """ BGP community-lists section configuration """

        for clist in communities.values():
            if clist.type is CommunityType.BASIC:
                member_prefix = ""
                cmd = "bgp community-list"
            elif clist.type is CommunityType.RT:
                member_prefix = "rt"
                cmd = "bgp extcommunity"
            elif clist.type is CommunityType.SOO:
                member_prefix = "soo"
                cmd = "bgp extcommunity"
            elif clist.type is CommunityType.LARGE:
                member_prefix = ""
                cmd = "bgp large-community-list"
            else:
                raise NotImplementedError(f"Community type {clist.type} is not supported on Cumulus")

            if clist.logic == CommunityLogic.AND and len(clist.members) > 1:
                raise NotImplementedError(
                    "Only OR logic for CommunityFiltersMatch "
                    "with multiple communities matches is currently supported"
                )

            if clist.use_regex:
                yield (
                    cmd,
                    "expanded",
                    clist.name,
                    "permit",
                    member_prefix, ",".join(f"\"{m}\"" for m in clist.members),
                )
            else:
                yield (
                    cmd,
                    "standard",
                    clist.name,
                    "permit",
                    " ".join(f"\"{member_prefix} {m}\"" for m in clist.members),
                )
        yield "!"

    def _get_match_community_names(self, condition: SingleCondition[Sequence[str]]) -> Sequence[str]:
        if condition.operator is ConditionOperator.HAS_ANY:
            return [mangle_united_community_list_name(condition.value)]
        else:
            return condition.value

    def _cumulus_policy_match(
            self,
            device: Any,
            condition: SingleCondition[Any],
    ) -> Iterator[Sequence[str]]:
        if condition.field == MatchField.community:
            for comm_name in self._get_match_community_names(condition):
                yield "match community", comm_name
            return
        if condition.field == MatchField.large_community:
            for comm_name in self._get_match_community_names(condition):
                yield "match large-community-list", comm_name
            return
        if condition.field == MatchField.extcommunity_rt:
            for comm_name in self._get_match_community_names(condition):
                yield "match extcommunity", comm_name
            return
        if condition.field == MatchField.extcommunity_soo:
            for comm_name in self._get_match_community_names(condition):
                yield "match extcommunity", comm_name
            return
        if condition.field == MatchField.ip_prefix:
            for name in condition.value.names:
                mangled_name = mangle_ranged_prefix_list_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "match", "ip address prefix-list", mangled_name
            return
        if condition.field == MatchField.ipv6_prefix:
            for name in condition.value.names:
                mangled_name = mangle_ranged_prefix_list_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "match", "ipv6 address prefix-list", mangled_name
            return
        if condition.operator is not ConditionOperator.EQ:
            raise NotImplementedError(
                f"`{condition.field}` with operator {condition.operator} is not supported for Cumulus",
            )
        if condition.field not in FRR_MATCH_COMMAND_MAP:
            raise NotImplementedError(f"Match using `{condition.field}` is not supported for Cumulus")
        cmd = FRR_MATCH_COMMAND_MAP[condition.field]
        yield "match", cmd.format(option_value=condition.value)

    def _cumulus_then_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            if not action.value.replaced:
                yield "set", "community", "none"
            first = True
            for community_name in action.value.replaced:
                if first:
                    yield "set", "community", community_name
                    first = False
                else:
                    yield "set", "community", community_name, "additive"
        for community_name in action.value.added:
            yield "set", "community", community_name, "additive"
        for community_name in action.value.removed:
            yield "set comm-list", community_name, "delete"

    def _cumulus_then_large_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Replacing Large community is not supported for Cumulus")
        for community_name in action.value.added:
            yield "set", "large-community", community_name, "additive"
        for community_name in action.value.removed:
            raise NotImplementedError("Large-community remove is not supported for Cumulus")

    def _cumulus_then_rt_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Replacing RT extcommunity is not supported for Cumulus")
        for community_name in action.value.added:
            yield "set", "extcommunity rt", community_name, "additive"
        for community_name in action.value.removed:
            raise NotImplementedError("RT extcommunity remove is not supported for Cumulus")

    def _cumulus_then_soo_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Replacing SOO extcommunity is not supported for Cumulus")
        for community_name in action.value.added:
            yield "set", "extcommunity soo", community_name, "additive"
        for community_name in action.value.removed:
            raise NotImplementedError("SOO extcommunity remove is not supported for Cumulus")

    def _cumulus_policy_then(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[Any],
    ) -> Iterator[Sequence[str]]:
        if action.field == ThenField.community:
            yield from self._cumulus_then_community(
                communities,
                device,
                cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.large_community:
            yield from self._cumulus_then_large_community(
                communities,
                device,
                cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.extcommunity_rt:
            yield from self._cumulus_then_rt_community(
                communities,
                device,
                cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.extcommunity_soo:
            yield from self._cumulus_then_soo_community(
                communities,
                device,
                cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.metric:
            if action.type is ActionType.ADD:
                yield "set", f"metric +{action.value}"
            elif action.type is ActionType.REMOVE:
                yield "set", f"metric -{action.value}"
            elif action.type is ActionType.SET:
                yield "set", f"metric {action.value}"
            else:
                raise NotImplementedError(f"Action type {action.type} for metric is not supported for Cumulus")
            return
        if action.field == ThenField.as_path:
            as_path_action_value = cast(AsPathActionValue, action.value)
            if as_path_action_value.prepend:
                for path_item in as_path_action_value.prepend:
                    yield "set as-path prepend", path_item
            if as_path_action_value.expand:  # same as prepend?
                for path_item in as_path_action_value.expand:
                    yield "set as-path prepend", path_item
            if as_path_action_value.delete:
                for path_item in as_path_action_value.delete:
                    yield "set as-path exclude", path_item
            if as_path_action_value.set is not None:
                raise NotImplementedError("asp_path.set is not supported for Cumulus")
            if as_path_action_value.expand_last_as:
                raise NotImplementedError("asp_path.expand_last_as is not supported for Cumulus")
            return
        if action.field == ThenField.next_hop:
            next_hop_action_value = cast(NextHopActionValue, action.value)
            if next_hop_action_value.target == "self":
                yield "set", "metric 1"
            elif next_hop_action_value.target == "discard":
                pass
            elif next_hop_action_value.target == "peer":
                pass
            elif next_hop_action_value.target == "ipv4_addr":
                yield "set", f"ip next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "ipv6_addr":
                yield "set", f"ipv6 next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "mapped_ipv4":
                yield "set", "ipv6 next-hop ::FFFF:{next_hop_action_value.addr}"
            else:
                raise NotImplementedError(
                    f"Next_hop target {next_hop_action_value.target} is not supported for Cumulus")
            return

        if action.type is not ActionType.SET:
            raise NotImplementedError(f"Action type {action.type} for `{action.field}` is not supported for Cumulus")
        if action.field not in FRR_THEN_COMMAND_MAP:
            raise NotImplementedError(f"Then action using `{action.field}` is not supported for Cumulus")
        cmd = FRR_THEN_COMMAND_MAP[action.field]
        yield "set", cmd.format(option_value=action.value)

    def _cumulus_policy_statement(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            policy: RoutingPolicy,
            statement: RoutingPolicyStatement,
    ) -> Iterable[Sequence[str]]:
        if statement.number is None:
            raise RuntimeError(f"Statement number should not be empty on Cumulus (found for policy: {policy.name})")
        yield "route-map", policy.name, FRR_RESULT_MAP[statement.result], statement.number

        for condition in statement.match:
            for row in self._cumulus_policy_match(device, condition):
                yield FRR_INDENT, *row
        for action in statement.then:
            for row in self._cumulus_policy_then(communities, device, action):
                yield FRR_INDENT, *row
        if statement.result is ResultType.NEXT:
            yield FRR_INDENT, "on-match next"
        yield "!"

    def _cumulus_policy_config(
            self,
            device: Any,
            communities: dict[str, CommunityList],
            policies: list[RoutingPolicy],
    ) -> Iterable[Sequence[str]]:
        """ Route maps configuration """

        for policy in policies:
            applied_stmts: dict[Optional[int], str] = {}
            for statement in policy.statements:
                if statement.number in applied_stmts:
                    raise RuntimeError(
                        f"Multiple statements have same number {statement.number} for policy `{policy.name}`: "
                        f"`{statement.name}` and `{applied_stmts[statement.number]}`")
                yield from self._cumulus_policy_statement(communities, device, policy, statement)
                applied_stmts[statement.number] = statement.name
