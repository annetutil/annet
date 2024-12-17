from abc import ABC, abstractmethod
from collections.abc import Sequence, Iterable
from ipaddress import ip_interface
from typing import Any, Literal

from annet.generators import PartialGenerator
from annet.rpl import RouteMap, PrefixMatchValue, MatchField, SingleCondition, RoutingPolicy
from .entities import IpPrefixList, mangle_ranged_prefix_list_name


def get_used_prefix_lists(prefix_lists: Sequence[IpPrefixList], policies: list[RoutingPolicy]) -> list[IpPrefixList]:
    plist_map = {c.name: c for c in prefix_lists}
    used_names = set()
    for policy in policies:
        for statement in policy.statements:
            for condition in statement.match.find_all(MatchField.ipv6_prefix):
                used_names.update(condition.value.names)
            for condition in statement.match.find_all(MatchField.ip_prefix):
                used_names.update(condition.value.names)
    return [plist_map[name] for name in sorted(used_names)]


class PrefixListFilterGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_policies(self, device: Any) -> list[RoutingPolicy]:
        raise NotImplementedError()

    @abstractmethod
    def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        raise NotImplementedError()

    def get_used_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        return get_used_prefix_lists(
            prefix_lists=self.get_prefix_lists(device),
            policies=self.get_policies(device),
        )

    # huawei
    def acl_huawei(self, _):
        return r"""
        ip ip-prefix
        ip ipv6-prefix
        """

    def _huawei_prefix_list(
            self,
            name: str,
            prefix_type: Literal["ipv6-prefix", "ip-prefix"],
            match: PrefixMatchValue,
            plist: IpPrefixList,
    ) -> Iterable[Sequence[str]]:
        for i, prefix in enumerate(plist.members):
            addr_mask = ip_interface(prefix)
            yield (
                "ip",
                prefix_type,
                name,
                f"index {i * 10 + 5}",
                "permit",
                str(addr_mask.ip).upper(),
                str(addr_mask.network.prefixlen),
            ) + (
                ("greater-equal", str(match.greater_equal)) if match.greater_equal is not None else ()
            ) + (
                ("less-equal", str(match.less_equal)) if match.less_equal is not None else ()
            )

    def run_huawei(self, device: Any):
        plists = {p.name: p for p in self.get_used_prefix_lists(device)}
        policies = self.get_policies(device)
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
                        yield from self._huawei_prefix_list(mangled_name, "ip-prefix", cond.value, plists[name])
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
                        yield from self._huawei_prefix_list(mangled_name, "ipv6-prefix", cond.value, plists[name])
                        precessed_names.add(mangled_name)

    # arista
    def acl_arista(self, _):
        return r"""
        ip prefix-list
        ipv6 prefix-list
        """

    def _arista_prefix_list(
            self,
            name: str,
            prefix_type: Literal["ipv6", "ip"],
            match: PrefixMatchValue,
            plist: IpPrefixList,
    ) -> Iterable[Sequence[str]]:
        for i, prefix in enumerate(plist.members):
            addr_mask = ip_interface(prefix)
            yield (
                prefix_type,
                "prefix-list",
                name,
                f"seq {i * 10 + 5}",
                "permit",
                str(addr_mask.ip).upper(),
                str(addr_mask.network.prefixlen),
            ) + (
                ("ge", str(match.greater_equal)) if match.greater_equal is not None else ()
            ) + (
                ("le", str(match.less_equal)) if match.less_equal is not None else ()
            )

    def run_arista(self, device: Any):
        plists = {p.name: p for p in self.get_used_prefix_lists(device)}
        policies = self.get_policies(device)
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
                        yield from self._arista_prefix_list(mangled_name, "ip", cond.value, plists[name])
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
                        yield from self._arista_prefix_list(mangled_name, "ipv6", cond.value, plists[name])
                        precessed_names.add(mangled_name)
