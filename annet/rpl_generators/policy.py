from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any, cast, Literal

from annet.generators import PartialGenerator
from annet.rpl import (
    CommunityActionValue,
    ResultType, RoutingPolicyStatement, RoutingPolicy, ConditionOperator, SingleCondition, SingleAction, ActionType,
    MatchField,
)
from annet.rpl.statement_builder import AsPathActionValue, NextHopActionValue, ThenField
from annet.rpl_generators.entities import (
    arista_well_known_community,
    CommunityList, RDFilter, PrefixListNameGenerator, CommunityLogic, mangle_united_community_list_name,
)
from annet.rpl_generators.prefix_lists import new_prefix_list_name_generator

HUAWEI_MATCH_COMMAND_MAP: dict[str, str] = {
    MatchField.as_path_filter: "as-path-filter {option_value}",
    MatchField.metric: "cost {option_value}",
    MatchField.protocol: "protocol {option_value}",
    MatchField.interface: "interface {option_value}",
}

HUAWEI_THEN_COMMAND_MAP: dict[str, str] = {
    ThenField.local_pref: "local-preference {option_value}",
    ThenField.metric_type: "cost-type {option_value}",
    ThenField.mpls_label: "mpls-label",
    ThenField.origin: "origin {option_value}",
    ThenField.tag: "tag {option_value}",
    # unsupported: resolution
    # unsupported: rpki_valid_state
}
HUAWEI_RESULT_MAP = {
    ResultType.ALLOW: "permit",
    ResultType.DENY: "deny",
    ResultType.NEXT: "permit"
}
ARISTA_RESULT_MAP = {
    ResultType.ALLOW: "permit",
    ResultType.DENY: "deny",
    ResultType.NEXT: "permit"
}
ARISTA_MATCH_COMMAND_MAP: dict[str, str] = {
    MatchField.interface: "interface {option_value}",
    MatchField.metric: "metric {option_value}",
    MatchField.as_path_filter: "as-path {option_value}",
    MatchField.protocol: "source-protocol {option_value}",
    # unsupported: rd
}
ARISTA_THEN_COMMAND_MAP: dict[str, str] = {
    ThenField.local_pref: "local-preference {option_value}",
    ThenField.origin: "origin {option_value}",
    ThenField.tag: "tag {option_value}",
    ThenField.metric_type: "metric-type {option_value}",
    # unsupported: mpls_label
    # unsupported: resolution
    # unsupported: rpki_valid_state
}


class RoutingPolicyGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_policies(self, device: Any) -> list[RoutingPolicy]:
        raise NotImplementedError()

    @abstractmethod
    def get_community_lists(self, device: Any) -> list[CommunityList]:
        raise NotImplementedError()

    @abstractmethod
    def get_rd_filters(self, device: Any) -> list[RDFilter]:
        raise NotImplementedError()

    # huawei
    def acl_huawei(self, _):
        return r"""
        route-policy *
            ~ %global=1
        """

    def _huawei_match(
            self,
            device: Any,
            condition: SingleCondition[Any],
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            prefix_name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        if condition.field == MatchField.community:
            if condition.operator is ConditionOperator.HAS:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS for communities is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS_ANY:
                raise NotImplementedError("Community operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                yield "if-match community-filter", comm_name
            return
        if condition.field == MatchField.large_community:
            if condition.operator is ConditionOperator.HAS_ANY:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS_ANY values for large_community is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS:
                raise NotImplementedError("large_community operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                yield "if-match large-community-filter", comm_name
            return
        if condition.field == MatchField.extcommunity_rt:
            if condition.operator is ConditionOperator.HAS:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS values for extcommunity_rt is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS_ANY:
                raise NotImplementedError("Extcommunity_rt operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                if communities[comm_name].logic is CommunityLogic.AND:
                    yield "if-match extcommunity-filter", comm_name, "matches-all"
                else:
                    yield "if-match extcommunity-filter", comm_name
            return
        if condition.field == MatchField.extcommunity_soo:
            if condition.operator is ConditionOperator.HAS_ANY:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS_ANY for extcommunities_soo is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS:
                raise NotImplementedError("Extcommunity_soo operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                yield "if-match extcommunity-list soo", comm_name
            return
        if condition.field == MatchField.rd:
            if len(condition.value) > 1:
                raise NotImplementedError("Multiple RD filters is not supported for huawei")
            rd_filter = rd_filters[condition.value[0]]
            yield "if-match rd-filter", str(rd_filter.number)
            return
        if condition.field == MatchField.ip_prefix:
            for name in condition.value.names:
                mangled_name = prefix_name_generator.get_prefix_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "if-match", "ip-prefix", mangled_name
            return
        if condition.field == MatchField.ipv6_prefix:
            for name in condition.value.names:
                mangled_name = prefix_name_generator.get_prefix_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "if-match", "ipv6 address prefix-list", mangled_name
            return
        if condition.field == MatchField.as_path_length:
            if condition.operator is ConditionOperator.EQ:
                yield "if-match", "as-path length", condition.value
            elif condition.operator is ConditionOperator.LE:
                yield "if-match", "as-path length less-equal", condition.value
            elif condition.operator is ConditionOperator.GE:
                yield "if-match", "as-path length greater-equal", condition.value
            elif condition.operator is ConditionOperator.BETWEEN_INCLUDED:
                yield "if-match", "as-path length greater-equal", condition.value[0], "less-equal", condition.value[1]
            else:
                raise NotImplementedError(
                    f"as_path_length operator {condition.operator} not supported for huawei",
                )
            return
        if condition.operator is not ConditionOperator.EQ:
            raise NotImplementedError(
                f"`{condition.field}` with operator {condition.operator} is not supported for huawei",
            )
        if condition.field not in HUAWEI_MATCH_COMMAND_MAP:
            raise NotImplementedError(f"Match using `{condition.field}` is not supported for huawei")
        cmd = HUAWEI_MATCH_COMMAND_MAP[condition.field]
        yield "if-match", cmd.format(option_value=condition.value)

    def _huawei_then_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set community together with add/remove on huawei",
                )
            members = [m for name in action.value.replaced for m in communities[name].members]
            if members:
                yield "apply", "community", *members
            else:
                yield "apply", "community", "none"
        if action.value.added:
            members = [m for name in action.value.added for m in communities[name].members]
            yield "apply", "community", *members, "additive"
        for community_name in action.value.removed:
            yield "apply comm-filter", community_name, "delete"

    def _huawei_then_large_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set large-community together with add/remove on huawei",
                )
            members = [m for name in action.value.replaced for m in communities[name].members]
            if members:
                yield "apply", "large-community", *members, "overwrite"
            else:
                yield "apply", "large-community", "none"
        if action.value.added:
            members = [m for name in action.value.added for m in communities[name].members]
            yield "apply", "large-community", *members, "additive"
        if action.value.removed:
            members = [m for name in action.value.removed for m in communities[name].members]
            yield "apply large-community", *members, "delete"

    def _huawei_then_extcommunity_rt(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_rt replace is not supported for huawei")
        if action.value.added:
            members = [f"rt {m}" for name in action.value.added for m in communities[name].members]
            yield "apply", "extcommunity", *members, "additive"
        for community_name in action.value.removed:
            yield "apply extcommunity-filter rt", community_name, "delete"

    def _huawei_then_extcommunity_soo(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_soo replace is not supported for huawei")
        if action.value.added:
            members = [f"rt {m}" for name in action.value.added for m in communities[name].members]
            yield "apply", "extcommunity", *members, "additive"
        if action.value.removed:
            raise NotImplementedError("Extcommunity_soo remove is not supported for huawei")

    def _huawei_then_as_path(
            self,
            device: Any,
            action: SingleAction[AsPathActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.set is not None:
            if action.value.prepend:
                raise NotImplementedError(
                    "Cannot set as_path together with prepend on huawei",
                )
            if action.value.set:
                yield "apply", "as-path", *action.value.set, "overwrite"
            else:
                yield "apply", "as-path", "none overwrite"
        if action.value.prepend:
            yield "apply as-path", *action.value.prepend, "additive"
        if action.value.expand:
            raise RuntimeError("as_path.expand is not supported for huawei")
        if action.value.delete:
            for path_item in action.value.delete:
                yield "apply as-path", path_item, "delete"
        if action.value.expand_last_as:
            raise RuntimeError("as_path.expand_last_as is not supported for huawei")

    def _huawei_then(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[Any],
    ) -> Iterator[Sequence[str]]:
        if action.field == ThenField.community:
            yield from self._huawei_then_community(communities, device,
                                                   cast(SingleAction[CommunityActionValue], action))
            return
        if action.field == ThenField.large_community:
            yield from self._huawei_then_large_community(communities, device,
                                                         cast(SingleAction[CommunityActionValue], action))
            return
        if action.field == ThenField.extcommunity_rt:
            yield from self._huawei_then_extcommunity_rt(communities, device,
                                                         cast(SingleAction[CommunityActionValue], action))
            return
        if action.field == ThenField.extcommunity_soo:
            yield from self._huawei_then_extcommunity_soo(communities, device,
                                                          cast(SingleAction[CommunityActionValue], action))
            return
        if action.field == ThenField.metric:
            if action.type is ActionType.ADD:
                yield "apply", f"cost + {action.value}"
            elif action.type is ActionType.SET:
                yield "apply", f"cost {action.value}"
            else:
                raise NotImplementedError(f"Action type {action.type} for metric is not supported for huawei")
            return
        if action.field == ThenField.as_path:
            yield from self._huawei_then_as_path(device, cast(SingleAction[AsPathActionValue], action))
            return
        if action.field == ThenField.next_hop:
            next_hop_action_value = cast(NextHopActionValue, action.value)
            if next_hop_action_value.target == "self":
                yield "apply", "cost 1"
            elif next_hop_action_value.target == "discard":
                pass
            elif next_hop_action_value.target == "peer":
                pass
            elif next_hop_action_value.target == "ipv4_addr":
                yield "apply", f"ip-address next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "ipv6_addr":
                yield "apply", f"ipv6 next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "mapped_ipv4":
                yield "apply", f"ipv6 next-hop ::FFFF:{next_hop_action_value.addr}"
            else:
                raise RuntimeError(f"Next_hop target {next_hop_action_value.target} is not supported for huawei")

        if action.type is not ActionType.SET:
            raise NotImplementedError(f"Action type {action.type} for `{action.field}` is not supported for huawei")
        if action.field not in HUAWEI_THEN_COMMAND_MAP:
            raise NotImplementedError(f"Then action using `{action.field}` is not supported for huawei")
        cmd = HUAWEI_THEN_COMMAND_MAP[action.field]
        yield "apply", cmd.format(option_value=action.value)

    def _huawei_statement(
            self,
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            device: Any,
            policy: RoutingPolicy,
            statement: RoutingPolicyStatement,
            prefix_name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        if statement.number is None:
            raise RuntimeError(f"Statement number should not be empty on Huawei (found for policy: {policy.name})")
        with self.block(
                "route-policy", policy.name,
                HUAWEI_RESULT_MAP[statement.result],
                "node", statement.number
        ):
            for condition in statement.match:
                yield from self._huawei_match(device, condition, communities, rd_filters, prefix_name_generator)
            for action in statement.then:
                yield from self._huawei_then(communities, device, action)
            if statement.result is ResultType.NEXT:
                yield "goto next-node"

    def run_huawei(self, device):
        policies = self.get_policies(device)
        communities = {c.name: c for c in self.get_community_lists(device)}
        rd_filters = {f.name: f for f in self.get_rd_filters(device)}
        prefix_name_generator = new_prefix_list_name_generator(policies)

        for policy in self.get_policies(device):
            for statement in policy.statements:
                yield from self._huawei_statement(communities, rd_filters, device, policy, statement, prefix_name_generator)

    # arista
    def acl_arista(self, device):
        return r"""
        route-map
            ~ %global=1
        """

    def _arista_match_community(
            self,
            device: Any,
            community_type: Literal["community", "extcommunity", "large-community"],
            community_names: Sequence[str],
    ) -> Iterator[Sequence[str]]:
        yield "match", community_type, *community_names

    def _arista_match(
            self,
            device: Any,
            condition: SingleCondition[Any],
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            prefix_name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        if condition.field == MatchField.community:
            if condition.operator is ConditionOperator.HAS_ANY:
                yield from self._arista_match_community(
                    device, "community", [mangle_united_community_list_name(condition.value)],
                )
            elif condition.operator is ConditionOperator.HAS:
                yield from self._arista_match_community(
                    device, "community", condition.value,
                )
            else:
                raise NotImplementedError(f"Community match operator {condition.field} is not supported on arista")
            return
        if condition.field == MatchField.large_community:
            if condition.operator is ConditionOperator.HAS_ANY:
                yield from self._arista_match_community(
                    device, "large-community", [mangle_united_community_list_name(condition.value)],
                )
            elif condition.operator is ConditionOperator.HAS:
                yield from self._arista_match_community(
                    device, "large-community", condition.value,
                )
            else:
                raise NotImplementedError(
                    f"Large-community match operator {condition.field} is not supported on arista")
            return
        if condition.field == MatchField.extcommunity_rt:
            if condition.operator is ConditionOperator.HAS_ANY:
                yield from self._arista_match_community(
                    device, "extcommunity", [mangle_united_community_list_name(condition.value)],
                )
            elif condition.operator is ConditionOperator.HAS:
                yield from self._arista_match_community(
                    device, "extcommunity", condition.value,
                )
            else:
                raise NotImplementedError(f"Community match operator {condition.field} is not supported on arista")
            return
        if condition.field == MatchField.extcommunity_soo:
            if condition.operator is ConditionOperator.HAS_ANY:
                yield from self._arista_match_community(
                    device, "extcommunity", [mangle_united_community_list_name(condition.value)],
                )
            elif condition.operator is ConditionOperator.HAS:
                yield from self._arista_match_community(
                    device, "extcommunity", condition.value,
                )
            else:
                raise NotImplementedError(f"Extcommunity match operator {condition.field} is not supported on arista")
            return
        if condition.field == MatchField.ip_prefix:
            for name in condition.value.names:
                mangled_name = prefix_name_generator.get_prefix_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "match", "ip address prefix-list", mangled_name
            return
        if condition.field == MatchField.ipv6_prefix:
            for name in condition.value.names:
                mangled_name = prefix_name_generator.get_prefix_name(
                    name=name,
                    greater_equal=condition.value.greater_equal,
                    less_equal=condition.value.less_equal,
                )
                yield "match", "ipv6 address prefix-list", mangled_name
            return
        if condition.field == MatchField.as_path_length:
            if condition.operator is ConditionOperator.EQ:
                yield "match", "as-path length =", condition.value
            elif condition.operator is ConditionOperator.LE:
                yield "match", "as-path length <=", condition.value
            elif condition.operator is ConditionOperator.GE:
                yield "match", "as-path length >=", condition.value
            elif condition.operator is ConditionOperator.BETWEEN_INCLUDED:
                yield "match", "as-path length >=", condition.value[0]
                yield "match", "as-path length <=", condition.value[1]
            else:
                raise NotImplementedError(
                    f"as_path_length operator {condition.operator} not supported for arista",
                )
            return
        if condition.operator is not ConditionOperator.EQ:
            raise NotImplementedError(
                f"`{condition.field}` with operator {condition.operator} is not supported for arista",
            )
        if condition.field not in ARISTA_MATCH_COMMAND_MAP:
            raise NotImplementedError(f"Match using `{condition.field}` is not supported for arista")
        cmd = ARISTA_MATCH_COMMAND_MAP[condition.field]
        yield "match", cmd.format(option_value=condition.value)

    def _arista_then_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set community together with add/remove on arista",
                )

            if action.value.replaced:
                yield "set", "community community-list", *action.value.replaced
            else:
                yield "set", "community", "none"
        for community_name in action.value.added:
            yield "set", "community community-list", community_name, "additive"
        for community_name in action.value.removed:
            community = communities[community_name]
            for comm_value in community.members:
                yield "set community", arista_well_known_community(comm_value), "delete"

    def _arista_then_large_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set large-community together with add/remove on arista",
                )

            if not action.value.replaced:
                yield "set", "large-community", "none"
            first = True
            for community_name in action.value.replaced:
                if first:
                    yield "set", "large-community large-community-list", community_name
                    first = False
                else:
                    yield "set", "large-community large-community-list", community_name, "additive"
        for community_name in action.value.added:
            yield "set", "large-community large-community-list", community_name, "additive"
        for community_name in action.value.removed:
            yield "set large-community large-community-list", community_name, "delete"

    def _arista_then_extcommunity_rt(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_rt replace is not supported for arista")
        for community_name in action.value.added:
            community = communities[community_name]
            for comm_value in community.members:
                yield "set", "extcommunity rt", comm_value, "additive"
        for community_name in action.value.removed:
            community = communities[community_name]
            for comm_value in community.members:
                yield "set extcommunity rt", comm_value, "delete"

    def _arista_then_extcommunity_soo(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_soo replace is not supported for arista")
        for community_name in action.value.added:
            community = communities[community_name]
            for comm_value in community.members:
                yield "set", "extcommunity soo", comm_value, "additive"
        for community_name in action.value.removed:
            community = communities[community_name]
            for comm_value in community.members:
                yield "set", "extcommunity soo", comm_value, "delete"

    def _arista_then_as_path(
            self,
            device: Any,
            action: SingleAction[AsPathActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.set is not None:
            if action.value.prepend:
                raise NotImplementedError(
                    "Cannot set as_path together with prepend on arista",
                )
            if not action.value.set:
                yield "set", "as-path match all replacement", "none"
            else:
                yield "set", "as-path match all replacement", *action.value.set

        if action.value.expand_last_as:
            last_as_suffix: Sequence[str] = "last-as", action.value.expand_last_as
        else:
            last_as_suffix = ()

        if action.value.prepend:
            for path_item in action.value.prepend:
                yield "set", "as-path prepend", path_item, *last_as_suffix
        else:
            yield "set", "as-path prepend", *last_as_suffix
        if action.value.expand:
            raise RuntimeError("as_path.expand is not supported for arista")
        if action.value.delete:
            raise RuntimeError("as_path.delete is not supported for arista")

    def _arista_then(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[Any],
    ) -> Iterator[Sequence[str]]:
        if action.field == ThenField.community:
            yield from self._arista_then_community(
                communities, device, cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.large_community:
            yield from self._arista_then_large_community(
                communities, device, cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.extcommunity_rt:
            yield from self._arista_then_extcommunity_rt(
                communities, device, cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.extcommunity_soo:
            yield from self._arista_then_extcommunity_soo(
                communities, device, cast(SingleAction[CommunityActionValue], action),
            )
            return
        if action.field == ThenField.metric:
            if action.type is ActionType.ADD:
                yield "set", f"metric + {action.value}"
            elif action.type is ActionType.REMOVE:
                yield "set", f"metric - {action.value}"
            elif action.type is ActionType.SET:
                yield "set", f"metric {action.value}"
            else:
                raise NotImplementedError(f"Action type {action.type} for metric is not supported for arista")
            return
        if action.field == ThenField.as_path:
            yield from self._arista_then_as_path(device, cast(SingleAction[AsPathActionValue], action))
            return
        if action.field == ThenField.next_hop:
            next_hop_action_value = cast(NextHopActionValue, action.value)
            if next_hop_action_value.target == "self":
                yield "set", "cost 1"  # TODO?
            elif next_hop_action_value.target == "discard":
                pass
            elif next_hop_action_value.target == "peer":
                pass
            elif next_hop_action_value.target == "ipv4_addr":
                yield "set", f"ip next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "ipv6_addr":
                yield "set", f"ipv6 next-hop {next_hop_action_value.addr}"
            elif next_hop_action_value.target == "mapped_ipv4":
                yield "set", f"ipv6 next-hop ::FFFF:{next_hop_action_value.addr}"
            else:
                raise RuntimeError(f"Next_hop target {next_hop_action_value.target} is not supported for arista")
            return
        if action.type is not ActionType.SET:
            raise NotImplementedError(f"Action type {action.type} for `{action.field}` is not supported for arista")
        if action.field not in ARISTA_THEN_COMMAND_MAP:
            raise NotImplementedError(f"Then action using `{action.field}` is not supported for arista")
        cmd = ARISTA_THEN_COMMAND_MAP[action.field]
        yield "set", cmd.format(option_value=action.value)

    def _arista_statement(
            self,
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            device: Any,
            policy: RoutingPolicy,
            statement: RoutingPolicyStatement,
            prefix_name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        with self.block(
                "route-map",
                policy.name,
                ARISTA_RESULT_MAP[statement.result],
                statement.number,
        ):
            for condition in statement.match:
                yield from self._arista_match(device, condition, communities, rd_filters, prefix_name_generator)
            for action in statement.then:
                yield from self._arista_then(communities, device, action)
            if statement.result is ResultType.NEXT:
                yield "continue"

    def run_arista(self, device):
        policies = self.get_policies(device)
        prefix_name_generator = new_prefix_list_name_generator(policies)
        communities = {c.name: c for c in self.get_community_lists(device)}
        rd_filters = {f.name: f for f in self.get_rd_filters(device)}

        for policy in policies:
            for statement in policy.statements:
                yield from self._arista_statement(
                    communities, rd_filters, device, policy, statement, prefix_name_generator,
                )
