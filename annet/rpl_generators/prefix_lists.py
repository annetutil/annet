from abc import ABC, abstractmethod
from collections.abc import Sequence, Iterable
from ipaddress import ip_interface
from typing import Any, Literal

from annet.generators import PartialGenerator
from annet.rpl import RouteMap, PrefixMatchValue, MatchField
from .entities import IpPrefixList


class PrefixListFilterGenerator(PartialGenerator, ABC):
    @abstractmethod
    def get_routemap(self) -> RouteMap:
        raise NotImplementedError()

    @abstractmethod
    def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        raise NotImplementedError()

    def get_used_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        plists = {c.name: c for c in self.get_prefix_lists(device)}
        policies = self.get_routemap().apply(device)
        used_names = set()
        for policy in policies:
            for statement in policy.statements:
                for condition in statement.match.find_all(MatchField.ipv6_prefix):
                    used_names.update(condition.value.names)
                for condition in statement.match.find_all(MatchField.ip_prefix):
                    used_names.update(condition.value.names)
        return [plists[name] for name in used_names]

    def acl_huawei(self, _):
        return r"""
        ip ip-prefix
        ip ipv6-prefix
        """

    def _huawei_prefix_list(
            self,
            policy_name: str,
            prefix_type: Literal["ipv6-prefix", "ip-prefix"],
            match: PrefixMatchValue,
            plists: dict[str, IpPrefixList],
    ) -> Iterable[Sequence[str]]:
        for name in match.names:
            plist = plists[name]
            for i, prefix in enumerate(plist.members):
                addr_mask = ip_interface(prefix)
                yield (
                    "ip",
                    prefix_type,
                    f"{name}_{policy_name}",
                    f"index {i * 10}",
                    "permit",
                    str(addr_mask.ip).upper(),
                    str(addr_mask.hostmask.max_prefixlen),
                ) + (
                    ("less-equal", str(match.less_equal)) if match.less_equal is not None else ()
                ) + (
                    ("greater-equal", str(match.greater_equal)) if match.greater_equal is not None else ()
                )

    def run_huawei(self, device: Any):
        plists = {p.name: p for p in self.get_prefix_lists(device)}
        policies = self.get_routemap().apply(device)
        for policy in policies:
            for statement in policy.statements:
                for cond in statement.match.find_all("ip_prefix"):
                    yield from self._huawei_prefix_list(policy.name, "ip-prefix", cond.value, plists)
                for cond in statement.match.find_all("ipv6_prefix"):
                    yield from self._huawei_prefix_list(policy.name, "ipv6-prefix", cond.value, plists)
