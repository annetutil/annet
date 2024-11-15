from collections.abc import Iterator, Sequence

from annet.generators import PartialGenerator, BaseGenerator
from annet.rpl import ResultType, RoutingPolicyStatement, RoutingPolicy, ConditionOperator
from annet.storage import Storage
from .routes import routemap

HUAWEI_MATCH_COMMAND_MAP = {
    "as_path_filter": "as-path-filter {option_value}",
    "metric": "cost {option_value}",
    "protocol": "protocol {option_value}",
    "interface": "interface {option_value}",
}

HUAWEI_THEN_COMMAND_MAP = {
    "metric": "cost {option_value}",
    "metric_add": "cost + {option_value}",
    "metric_type": "cost-type {option_value}",
    "next_hop_self": "cost {option_value}",  # XXX next_hop_self == metric ?WTF?
    "local_pref": "local-preference {option_value}",
    "next_hop": "ip-address next-hop {option_value}",
    "next_hop_v6": "ipv6 next-hop {option_value}",
    "next_hop_v4mapped": "ipv6 next-hop ::FFFF:{option_value}",
    "tag": "tag {option_value}",
    "origin": "origin {option_value}",
    "mpls_label": "mpls-label",
}
HUAWEI_RESULT_MAP = {
    ResultType.ALLOW: "permit",
    ResultType.DENY: "deny",
}


class RoutingPolicyGenerator(PartialGenerator):
    TAGS = ["policy", "rpl", "routing"]

    def acl_huawei(self, _):
        return r"""
        ip as-path-filter
        route-policy *
            ~ %global=1
        """

    def _huawei_statement(
            self, device, policy: RoutingPolicy, statement: RoutingPolicyStatement,
    ) -> Iterator[Sequence[str]]:
        with self.block(
                "route-policy", policy.name,
                HUAWEI_RESULT_MAP[statement.result],
                "node", statement.number
        ):
            for condition in statement.match:
                if condition.field == "community":
                    if condition.operator is ConditionOperator.HAS:
                        if len(condition.value) > 1:
                            raise NotImplementedError("Multiple HAS for communities is not supported for huawei")
                    elif condition.operator is not ConditionOperator.HAS_ANY:
                        raise NotImplementedError("Community operator %r not supported for huawei" % condition.operator)
                    for comm_name in condition.value:
                        yield "if-match community-filter", comm_name
                    continue
                if condition.field == "extcommunity":
                    if condition.operator is ConditionOperator.HAS:
                        if len(condition.value) > 1:
                            raise NotImplementedError("Multiple HAS for extcommunities is not supported for huawei")
                    elif condition.operator is not ConditionOperator.HAS_ANY:
                        raise NotImplementedError("Extcommunity operator %r not supported for huawei" % condition.operator)
                    for comm_name in condition.value:
                        yield "if-match extcommunity-filter", comm_name
                    continue
                if condition.operator is not ConditionOperator.EQ:
                    raise NotImplementedError(f"{condition.field} operator {condition.operator} is not supported for huawei")
                cmd = HUAWEI_MATCH_COMMAND_MAP[condition.field]
                yield "if-match", cmd.format(option_value=condition.value)
            for action in statement.then:
                cmd = HUAWEI_THEN_COMMAND_MAP[action.field]
                yield "then", cmd.format(option_value=action.value)

    def run_huawei(self, device):
        for policy in routemap.apply(device):
            for statement in policy.statements:
                yield from self._huawei_statement(device, policy, statement)


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        RoutingPolicyGenerator(store),
    ]
