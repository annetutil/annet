from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence, Iterable
from typing import Any, cast, Literal

from annet.generators import PartialGenerator
from annet.rpl import (
    CommunityActionValue,
    ResultType, RoutingPolicyStatement, RoutingPolicy, ConditionOperator, SingleCondition, SingleAction, ActionType,
    MatchField, PrefixMatchValue,
)
from annet.rpl.statement_builder import AsPathActionValue, NextHopActionValue, ThenField
from annet.rpl_generators.entities import (
    arista_well_known_community,
    CommunityList, RDFilter, PrefixListNameGenerator, CommunityLogic, mangle_united_community_list_name,
    IpPrefixList, group_community_members, CommunityType,
)

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
IOSXR_MATCH_COMMAND_MAP: dict[str, str] = {
    MatchField.as_path_filter: "as-path in {option_value}",
    MatchField.protocol: "protocol is {option_value}",
    # unsupported: interface
    # unsupported: metric
    # unsupported: large-community
}
IOSXR_THEN_COMMAND_MAP: dict[str, str] = {
    ThenField.local_pref: "local-preference {option_value}",
    ThenField.origin: "origin {option_value}",
    ThenField.tag: "tag {option_value}",
    ThenField.metric_type: "metric-type {option_value}",
    # unsupported: mpls_label  # label?
    # unsupported: resolution
    # unsupported: rpki_valid_state
    # unsupported: large_community
}
IOSXR_RESULT_MAP = {
    ResultType.ALLOW: "done",
    ResultType.DENY: "drop",
    ResultType.NEXT: "pass"
}


class RoutingPolicyGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
        raise NotImplementedError()

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
            name_generator: PrefixListNameGenerator,
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
                plist = name_generator.get_prefix(name, condition.value)
                yield "if-match", "ip-prefix", plist.name
            return
        if condition.field == MatchField.ipv6_prefix:
            for name in condition.value.names:
                plist = name_generator.get_prefix(name, condition.value)
                yield "if-match", "ipv6 address prefix-list", plist.name
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

    def _huawei_render_ext_community_members(
            self, comm_type: CommunityType, members: list[str]
    ) -> Sequence[Sequence[str]]:
        if comm_type is CommunityType.SOO:
            return "soo", *members
        if comm_type is CommunityType.RT:
            return [f"rt {member}" for member in members]
        elif comm_type is CommunityType.LARGE:
            raise ValueError("Large community is not subtype of extcommunity")
        elif comm_type is CommunityType.BASIC:
            raise ValueError("Basic community is not subtype of extcommunity")
        else:
            raise NotImplementedError(f"Community type {comm_type} is not supported on huawei")

    def _huawei_then_extcommunity(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ):
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set extcommunity together with add/delete on huawei",
                )
            if not action.value.replaced:
                raise NotImplementedError(
                    "Cannot reset extcommunity on huawei",
                )

            members = group_community_members(communities, action.value.replaced)
            for community_type, replaced_members in members.items():
                if community_type is CommunityType.SOO:
                    raise NotImplementedError(
                        "Cannot set extcommunity soo on huawei",
                    )
                rendered_memebers = self._huawei_render_ext_community_members(community_type, replaced_members)
                yield "apply", "extcommunity", *rendered_memebers
        if action.value.added:
            members = group_community_members(communities, action.value.added)
            for community_type, added_members in members.items():
                rendered_memebers = self._huawei_render_ext_community_members(community_type, added_members)
                yield "apply", "extcommunity", *rendered_memebers, "additive"
        if action.value.removed:
            raise NotImplementedError("Cannot remove extcommunity on huawei")

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
        if action.field == ThenField.extcommunity:
            yield from self._huawei_then_extcommunity(communities, device,
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
        prefix_lists = self.get_prefix_lists(device)
        policies = self.get_policies(device)
        communities = {c.name: c for c in self.get_community_lists(device)}
        rd_filters = {f.name: f for f in self.get_rd_filters(device)}
        prefix_name_generator = PrefixListNameGenerator(prefix_lists, policies)

        for policy in self.get_policies(device):
            for statement in policy.statements:
                yield from self._huawei_statement(communities, rd_filters, device, policy, statement,
                                                  prefix_name_generator)

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
            name_generator: PrefixListNameGenerator,
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
                plist = name_generator.get_prefix(name, condition.value)
                yield "match", "ip address prefix-list", plist.name
            return
        if condition.field == MatchField.ipv6_prefix:
            for name in condition.value.names:
                plist = name_generator.get_prefix(name, condition.value)
                yield "match", "ipv6 address prefix-list", plist.name
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
        if action.value.added:
            yield "set", "community community-list", *action.value.added, "additive"
        if action.value.removed:
            members = [
                arista_well_known_community(member)
                for community_name in action.value.removed
                for member in communities[community_name].members
            ]
            yield "set community", *members, "delete"

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
        if action.value.added:
            yield "set", "large-community large-community-list", *action.value.added, "additive"
        if action.value.removed:
            yield "set large-community large-community-list", *action.value.removed, "delete"

    def _arista_then_extcommunity_rt(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_rt replace is not supported for arista")
        if action.value.added:
            members = [
                f"rt {member}"
                for community_name in action.value.removed
                for member in communities[community_name].members
            ]
            yield "set", "extcommunity", *members, "additive"
        if action.value.removed:
            members = [
                f"rt {member}"
                for community_name in action.value.removed
                for member in communities[community_name].members
            ]
            yield "set extcommunity", *members, "delete"

    def _arista_then_extcommunity_soo(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.replaced is not None:
            raise NotImplementedError("Extcommunity_soo replace is not supported for arista")
        if action.value.added:
            members = [
                f"soo {member}"
                for community_name in action.value.removed
                for member in communities[community_name].members
            ]
            yield "set", "extcommunity", *members, "additive"
        if action.value.removed:
            members = [
                f"soo {member}"
                for community_name in action.value.removed
                for member in communities[community_name].members
            ]
            yield "set", "extcommunity", *members, "delete"

    def _arista_extcommunity_type_str(self, comm_type: CommunityType) -> str:
        if comm_type is CommunityType.SOO:
            return "soo"
        elif comm_type is CommunityType.RT:
            return "rt"
        elif comm_type is CommunityType.LARGE:
            raise ValueError("Large community is not subtype of extcommunity")
        elif comm_type is CommunityType.BASIC:
            raise ValueError("Basic community is not subtype of extcommunity")
        else:
            raise NotImplementedError(f"Community type {comm_type} is not supported on arista")

    def _arista_render_ext_community_members(
            self, all_communities: dict[str, CommunityList], communities: list[str],
    ) -> Iterator[str]:
        for community_name in communities:
            community = all_communities[community_name]
            comm_type = self._arista_extcommunity_type_str(community.type)
            for member in community.members:
                yield f"{comm_type} {member}"

    def _arista_then_extcommunity(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ):
        if action.value.replaced is not None:
            if action.value.added or action.value.removed:
                raise NotImplementedError(
                    "Cannot set extcommunity together with add/delete on arista",
                )
            if not action.value.replaced:
                yield "set", "extcommunity", "none"
                return
            members = list(self._arista_render_ext_community_members(communities, action.value.replaced))
            yield "set extcommunity", *members
            return
        if action.value.added:
            members = list(self._arista_render_ext_community_members(communities, action.value.added))
            yield "set extcommunity", *members, "additive"
        if action.value.removed:
            members = list(self._arista_render_ext_community_members(communities, action.value.removed))
            yield "set extcommunity", *members, "delete"

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
        if action.field == ThenField.extcommunity:
            yield from self._arista_then_extcommunity(communities, device, action)
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
        if statement.number is None:
            raise RuntimeError(f"Statement number should not be empty on Arista (found for policy: {policy.name})")
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
        prefix_lists = self.get_prefix_lists(device)
        policies = self.get_policies(device)
        prefix_name_generator = PrefixListNameGenerator(prefix_lists, policies)
        communities = {c.name: c for c in self.get_community_lists(device)}
        rd_filters = {f.name: f for f in self.get_rd_filters(device)}

        for policy in policies:
            for statement in policy.statements:
                yield from self._arista_statement(
                    communities, rd_filters, device, policy, statement, prefix_name_generator,
                )

    # Cisco IOS XR
    def acl_iosxr(self, device):
        return r"""
        route-policy *
            ~ %global=1
        """

    def _iosxr_match_community(
            self,
            community_type: Literal["community", "extcommunity rt", "extcommunity soo"],
            community: CommunityList,
    ) -> Iterator[Sequence[str]]:
        if community.logic is CommunityLogic.AND:
            yield community_type, "matches-every", community.name
        elif community.logic is CommunityLogic.OR:
            yield community_type, "matches-any", community.name
        else:
            raise ValueError(f"Unknown community logic {community.logic}")

    def _iosxr_match_communities(
            self,
            operator: ConditionOperator,
            community_type: Literal["community", "extcommunity rt", "extcommunity soo"],
            community_names: list[str],
            communities: dict[str, CommunityList],
    ) -> Iterator[Sequence[str]]:
        if operator == ConditionOperator.HAS_ANY:
            yield self._iosxr_or_matches(
                self._iosxr_match_community(community_type, communities[name])
                for name in community_names
            ),
        elif operator == ConditionOperator.HAS:
            for name in community_names:
                yield from self._iosxr_match_community(community_type, communities[name])
        else:
            raise NotImplementedError(f"Operator {operator} is not supported for {community_type} on Cisco IOS XR")

    def _iosxr_match_rd(
            self,
            condition: SingleCondition[Sequence[str]],
            rd_filters: dict[str, RDFilter],
    ) -> Iterator[Sequence[str]]:
        if condition.operator == ConditionOperator.HAS_ANY:
            if len(condition.value) == 1:
                yield "rd", "in", condition.value[0]
                return
            conds = " or ".join(f"rd in {name}" for name in condition.value)
            yield f"({conds})",
            return
        elif condition.operator == ConditionOperator.HAS:
            for name in condition.value:
                yield "rd", "in", name
        else:
            raise NotImplementedError(f"Operator {condition.operator} is not supported for {condition.field} on Cisco IOS XR")

    def _iosxr_match_prefix_lists(
            self,
            condition: SingleCondition[PrefixMatchValue],
            name_generator: PrefixListNameGenerator
    ) -> Iterator[Sequence[str]]:
        matches = []
        for name in condition.value.names:
            plist = name_generator.get_prefix(name, condition.value)
            matches.append(("destination in", plist.name))
        if len(matches) == 1:
            yield matches[0]
        else:
            yield self._iosxr_or_matches([matches]),

    def _iosxr_match_local_pref(self, condition: SingleCondition) -> Iterator[Sequence[str]]:
        if condition.operator is ConditionOperator.EQ:
            yield "local-preference", "eq", str(condition.value)
        elif condition.operator is ConditionOperator.LE:
            yield "local-preference", "le", str(condition.value)
        elif condition.operator is ConditionOperator.GE:
            yield "local-preference", "ge", str(condition.value)
        elif condition.operator is ConditionOperator.BETWEEN_INCLUDED:
            yield "local-preference", "ge", str(condition.value[0])
            yield "local-preference", "le", str(condition.value[1])
        else:
            raise NotImplementedError(
                f"Operator {condition.operator} is not supported for {condition.field} on Cisco IOS XR",
            )

    def _iosxr_match_as_path_length(self, condition: SingleCondition) -> Iterator[Sequence[str]]:
        if condition.operator is ConditionOperator.EQ:
            yield "as-path length", "eq", str(condition.value)
        elif condition.operator is ConditionOperator.LE:
            yield "as-path length", "le", str(condition.value)
        elif condition.operator is ConditionOperator.GE:
            yield "as-path length", "ge", str(condition.value)
        elif condition.operator is ConditionOperator.BETWEEN_INCLUDED:
            yield "as-path length", "ge", str(condition.value[0])
            yield "as-path length", "le", str(condition.value[1])
        else:
            raise NotImplementedError(
                f"Operator {condition.operator} is not supported for {condition.field} on Cisco IOS XR",
            )

    def _iosxr_and_matches(self, conditions: Iterable[Iterable[Sequence[str]]]) -> str:
        return " and ".join(" ".join(c) for seq in conditions for c in seq)

    def _iosxr_or_matches(self, conditions: Iterable[Iterable[Sequence[str]]]) -> str:
        return "(" + " or ".join(" ".join(c) for seq in conditions for c in seq) + ")"

    def _iosxr_match(
            self,
            device: Any,
            condition: SingleCondition[Any],
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        if condition.field == MatchField.community:
            yield from self._iosxr_match_communities(condition.operator, "community", condition.value, communities)
            return
        elif condition.field == MatchField.extcommunity_rt:
            yield from self._iosxr_match_communities(condition.operator, "extcommunity rt", condition.value, communities)
            return
        elif condition.field == MatchField.extcommunity_soo:
            yield from self._iosxr_match_communities(condition.operator, "extcommunity soo", condition.value, communities)
            return
        elif condition.field == MatchField.local_pref:
            yield from self._iosxr_match_local_pref(condition)
            return
        elif condition.field == MatchField.as_path_length:
            yield from self._iosxr_match_as_path_length(condition)
            return
        elif condition.field == MatchField.rd:
            yield from self._iosxr_match_rd(condition, rd_filters)
            return
        elif condition.field == MatchField.ip_prefix:
            yield from self._iosxr_match_prefix_lists(condition, name_generator)
            return
        elif condition.field == MatchField.ipv6_prefix:
            yield from self._iosxr_match_prefix_lists(condition, name_generator)
            return

        if condition.operator is not ConditionOperator.EQ:
            raise NotImplementedError(
                f"`{condition.field}` with operator {condition.operator} is not supported for Cisco IOS XR",
            )
        if condition.field not in IOSXR_MATCH_COMMAND_MAP:
            raise NotImplementedError(f"Match using `{condition.field}` is not supported for Cisco IOS XR")
        yield IOSXR_MATCH_COMMAND_MAP[condition.field].format(option_value=condition.value),

    def _iosxr_then_as_path(
            self,
            device: Any,
            action: SingleAction[AsPathActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.set is not None:
            raise RuntimeError("as_path.set is not supported for Cisco IOS XR")
        if action.value.prepend:
            for asn in action.value.prepend:
                yield "prepend as-path", asn
        if action.value.expand:
            raise RuntimeError("as_path.expand is not supported for Cisco IOS XR")
        if action.value.delete:
            raise RuntimeError("as_path.delete is not supported for Cisco IOS XR")
        if action.value.expand_last_as:
            raise RuntimeError("as_path.expand_last_as is not supported for Cisco IOS XR")

    def _iosxr_then_next_hop(
            self,
            device: Any,
            action: SingleAction[NextHopActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.value.target == "self":
            yield "set", "next-hop", "self"
        elif action.value.target == "discard":
            yield "set", "next-hop", "discard"
        elif action.value.target == "peer":
            pass
        elif action.value.target == "ipv4_addr":
            yield "set", "next-hop", action.value.addr
        elif action.value.target == "ipv6_addr":
            yield "set", "next-hop", action.value.addr.lower()
        elif action.value.target == "mapped_ipv4":
            yield "set", "next-hop", f"::ffff:{action.value.addr}"
        else:
            raise RuntimeError(f"Next_hop target {action.value.target} is not supported for Cisco IOS XR")

    def _iosxr_then_metric(
            self,
            device: Any,
            action: SingleAction[NextHopActionValue],
    ) -> Iterator[Sequence[str]]:
        if action.type is ActionType.ADD:
            yield "set", f"med +{action.value}"
        elif action.type is ActionType.REMOVE:
            yield "set", f"med -{action.value}"
        elif action.type is ActionType.SET:
            yield "set", f"med {action.value}"
        else:
            raise NotImplementedError(f"Action type {action.type} for metric is not supported for Cisco IOS XR")

    def _iosxr_then_community(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        added = []
        if action.value.replaced is not None:
            yield "delete", "community", "all"
            added.extend(action.value.replaced)
        added.extend(action.value.added)
        for name in added:
            yield "set", "community", name, "additive"
        for community_name in action.value.removed:
            yield "delete", "community", "in", community_name

    def _iosxr_community_type_str(self, comm_type: CommunityType) -> str:
        if comm_type is CommunityType.RT:
            return "rt"
        elif comm_type is CommunityType.LARGE:
            raise ValueError("Large community is not subtype of extcommunity")
        elif comm_type is CommunityType.BASIC:
            raise ValueError("Basic community is not subtype of extcommunity")
        else:
            raise NotImplementedError(f"Community type {comm_type} is not supported on Cisco IOS XR")

    def _iosxr_then_extcommunity(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[CommunityActionValue],
    ) -> Iterator[Sequence[str]]:
        added = []
        if action.value.replaced is not None:
            yield "delete", "extcommunity", "rt", "all"
            added.extend(action.value.replaced)

        added.extend(action.value.added)
        for member_name in added:
            typename = self._iosxr_community_type_str(communities[member_name].type)
            yield "set", "extcommunity", typename, member_name, "additive"
        for member_name in action.value.removed:
            typename = self._iosxr_community_type_str(communities[member_name].type)
            yield "delete", "extcommunity", typename, "in", member_name

    def _iosxr_then(
            self,
            communities: dict[str, CommunityList],
            device: Any,
            action: SingleAction[Any],
    ) -> Iterator[Sequence[str]]:
        if action.field == ThenField.community:
            yield from self._iosxr_then_community(communities, device, action)
            return
        if action.field == ThenField.extcommunity:
            yield from self._iosxr_then_extcommunity(communities, device, action)
            return
        if action.field == ThenField.metric:
            yield from self._iosxr_then_metric(device, action)
            return
        if action.field == ThenField.as_path:
            yield from self._iosxr_then_as_path(device, cast(SingleAction[AsPathActionValue], action))
            return
        if action.field == ThenField.next_hop:
            yield from self._iosxr_then_next_hop(device, cast(SingleAction[NextHopActionValue], action))
            return
        if action.type is not ActionType.SET:
            raise NotImplementedError(f"Action type {action.type} for `{action.field}` is not supported for Cisco IOS XR")
        if action.field not in IOSXR_THEN_COMMAND_MAP:
            raise NotImplementedError(f"Then action using `{action.field}` is not supported for Cisco IOS XR")
        cmd = IOSXR_THEN_COMMAND_MAP[action.field]
        yield "set", cmd.format(option_value=action.value)

    def _iosxr_statement(
            self,
            communities: dict[str, CommunityList],
            rd_filters: dict[str, RDFilter],
            device: Any,
            policy: RoutingPolicy,
            statement: RoutingPolicyStatement,
            prefix_name_generator: PrefixListNameGenerator,
    ) -> Iterator[Sequence[str]]:
        if statement.match:
            condition_expr = self._iosxr_and_matches(
                self._iosxr_match(device, condition, communities, rd_filters, prefix_name_generator)
                for condition in statement.match
            )
            with self.block(
                    "if", condition_expr, "then",
            ):
                for action in statement.then:
                    yield from self._iosxr_then(communities, device, action)
                yield IOSXR_RESULT_MAP[statement.result],
        else:
            for action in statement.then:
                yield from self._iosxr_then(communities, device, action)
            yield IOSXR_RESULT_MAP[statement.result],

    def run_iosxr(self, device):
        prefix_lists = self.get_prefix_lists(device)
        policies = self.get_policies(device)
        prefix_name_generator = PrefixListNameGenerator(prefix_lists, policies)
        communities = {c.name: c for c in self.get_community_lists(device)}
        rd_filters = {f.name: f for f in self.get_rd_filters(device)}

        for policy in policies:
            with self.block(
                    "route-policy", policy.name,
            ):
                for statement in policy.statements:
                    yield from self._iosxr_statement(
                        communities, rd_filters, device, policy, statement, prefix_name_generator,
                    )
