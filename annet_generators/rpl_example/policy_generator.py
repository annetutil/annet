from collections.abc import Iterator, Sequence
from typing import Any, cast

from annet.generators import PartialGenerator, BaseGenerator
from annet.rpl import (
    CommunityActionValue,
    ResultType, RoutingPolicyStatement, RoutingPolicy, ConditionOperator, SingleCondition, SingleAction, ActionType,
)
from annet.rpl.statement_builder import AsPathActionValue, NextHopActionValue
from annet.storage import Storage
from .items import AS_PATH_FILTERS, COMMUNITIES
from .route_policy import routemap

HUAWEI_MATCH_COMMAND_MAP = {
    "as_path_filter": "as-path-filter {option_value}",
    "metric": "cost {option_value}",
    "protocol": "protocol {option_value}",
    "interface": "interface {option_value}",
}

HUAWEI_THEN_COMMAND_MAP = {
    "metric": "cost {option_value}",
    "local_pref": "local-preference {option_value}",
    "metric_type": "cost-type {option_value}",
    "mpls_label": "mpls-label",
    "origin": "origin {option_value}",
    "tag": "tag {option_value}",
}
HUAWEI_RESULT_MAP = {
    ResultType.ALLOW: "permit",
    ResultType.DENY: "deny",
    ResultType.NEXT: ""
}


class RoutingPolicyGenerator(PartialGenerator):
    TAGS = ["policy", "rpl", "routing"]

    def acl_huawei(self, _):
        return r"""
        ip as-path-filter
        route-policy *
            ~ %global=1
        """

    def _huawei_match(self, device, condition: SingleCondition[Any]) -> Iterator[Sequence[str]]:
        if condition.field == "community":
            if condition.operator is ConditionOperator.HAS:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS for communities is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS_ANY:
                raise NotImplementedError("Community operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                yield "if-match community-filter", comm_name
            return
        if condition.field == "extcommunity":
            if condition.operator is ConditionOperator.HAS:
                if len(condition.value) > 1:
                    raise NotImplementedError("Multiple HAS for extcommunities is not supported for huawei")
            elif condition.operator is not ConditionOperator.HAS_ANY:
                raise NotImplementedError("Extcommunity operator %r not supported for huawei" % condition.operator)
            for comm_name in condition.value:
                yield "if-match extcommunity-filter", comm_name
            return
        if condition.field == "ip_prefix":
            for name in condition.value.names:
                yield "if-match", "ip-prefix-filter", name
            return
        if condition.field == "ipv6_prefix":
            for name in condition.value.names:
                yield "if-match", "ipv6 address prefix-list", name
            return

        if condition.operator is not ConditionOperator.EQ:
            raise NotImplementedError(
                f"`{condition.field}` with operator {condition.operator} is not supported for huawei",
            )
        if condition.field not in HUAWEI_MATCH_COMMAND_MAP:
            raise NotImplementedError(f"Match using `{condition.field}` is not supported for huawei")
        cmd = HUAWEI_MATCH_COMMAND_MAP[condition.field]
        yield "if-match", cmd.format(option_value=condition.value)

    def _huawei_then(self, device, action: SingleAction[Any]) -> Iterator[Sequence[str]]:
        if action.field == "community":
            # TODO group by extcommunity
            comm_action_value = cast(CommunityActionValue, action.value)
            if comm_action_value.replaced is not None:
                if not comm_action_value.replaced:
                    yield "apply", "community", "none"
                first = True
                for community_name in comm_action_value.replaced:
                    community = COMMUNITIES[community_name]
                    for comm_value in community.values:
                        if first:
                            yield "apply", "community", comm_value
                            first = False
                        else:
                            yield "apply", "community", comm_value, "additive"
            for community_name in comm_action_value.added:
                community = COMMUNITIES[community_name]
                for comm_value in community.values:
                    yield "apply", "community", comm_value, "additive"
            for community_name in comm_action_value.removed:
                yield "apply comm-filter", community_name, "delete"
            return
        if action.field == "metric":
            if action.type is ActionType.ADD:
                yield "apply", f"cost + {action.value}"
            elif action.type is ActionType.SET:
                yield "apply", f"cost {action.value}"
            else:
                raise NotImplementedError(f"Action type {action.type} for metric is not supported for huawei")
            return
        if action.field == "as_path":
            as_path_action_value = cast(AsPathActionValue, action.value)
            if as_path_action_value.set is not None:
                yield "apply as-path", as_path_action_value.set, "overwrite"
            if as_path_action_value.prepend:
                yield "apply as-path", as_path_action_value.prepend, "additive"
            if as_path_action_value.expand:  # same as prepend?
                yield "apply as-path", as_path_action_value.expand, "additive"
            if as_path_action_value.delete:
                yield "apply as-path", as_path_action_value.delete, "delete"
            if as_path_action_value.expand_last_as:
                raise RuntimeError("asp_path.expand_last_as is not supported for huawei")
            return
        if action.field == "next_hop":
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
            self, device, policy: RoutingPolicy, statement: RoutingPolicyStatement,
    ) -> Iterator[Sequence[str]]:
        if "as_path_filter" in statement.match:
            as_path_condition = statement.match["as_path_filter"]
            as_filter_value = AS_PATH_FILTERS[as_path_condition.value]
            yield "ip as-path-filter", \
                as_path_condition.value, \
                "index 10 permit", \
                "_{}_".format("_".join(("%s" % x for x in as_filter_value if x != ".*")))

        with self.block(
                "route-policy", policy.name,
                HUAWEI_RESULT_MAP[statement.result],
                "node", statement.number
        ):
            for condition in statement.match:
                yield from self._huawei_match(device, condition)
            for action in statement.then:
                yield from self._huawei_then(device, action)
            if statement.result is ResultType.NEXT:
                yield "goto next-node"

    def run_huawei(self, device):
        for policy in routemap.apply(device):
            for statement in policy.statements:
                yield from self._huawei_statement(device, policy, statement)


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        RoutingPolicyGenerator(store),
    ]
