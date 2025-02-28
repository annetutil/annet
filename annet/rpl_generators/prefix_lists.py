from abc import ABC, abstractmethod
from collections.abc import Sequence, Iterable
from ipaddress import ip_interface
from typing import Any, Literal

from annet.generators import PartialGenerator
from annet.rpl import PrefixMatchValue, MatchField, SingleCondition, RoutingPolicy
from .entities import IpPrefixList, PrefixListNameGenerator


class PrefixListFilterGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_policies(self, device: Any) -> list[RoutingPolicy]:
        raise NotImplementedError()

    @abstractmethod
    def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
        raise NotImplementedError()

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
        for i, m in enumerate(plist.members):
            yield (
                "ip",
                prefix_type,
                name,
                f"index {i * 5 + 5}",
                "permit",
                str(m.prefix.network_address).upper(),
                str(m.prefix.prefixlen),
            ) + (
                ("greater-equal", str(match.greater_equal)) if match.greater_equal is not None else ()
            ) + (
                ("less-equal", str(match.less_equal)) if match.less_equal is not None else ()
            )

    def run_huawei(self, device: Any):
        prefix_lists = self.get_prefix_lists(device)
        policies = self.get_policies(device)

        name_generator = PrefixListNameGenerator(prefix_lists, policies)
        processed_names = set()
        for policy in policies:
            for statement in policy.statements:
                cond: SingleCondition[PrefixMatchValue]
                for cond in statement.match.find_all(MatchField.ip_prefix):
                    for name in cond.value.names:
                        plist = name_generator.get_prefix(name, cond.value)
                        if plist.name in processed_names:
                            continue
                        yield from self._huawei_prefix_list(plist.name, "ip-prefix", cond.value, plist)
                        processed_names.add(plist.name)
                for cond in statement.match.find_all(MatchField.ipv6_prefix):
                    for name in cond.value.names:
                        plist = name_generator.get_prefix(name, cond.value)
                        if plist.name in processed_names:
                            continue
                        yield from self._huawei_prefix_list(plist.name, "ipv6-prefix", cond.value, plist)
                        processed_names.add(plist.name)

    # arista
    def acl_arista(self, _):
        return r"""
        ip prefix-list
            seq
        ipv6 prefix-list
            seq
        """

    def _arista_prefix_list(
            self,
            name: str,
            prefix_type: Literal["ipv6", "ip"],
            match: PrefixMatchValue,
            plist: IpPrefixList,
    ) -> Iterable[Sequence[str]]:
        with self.block(prefix_type, "prefix-list", name):
            for i, m in enumerate(plist.members):
                yield (
                    f"seq {i * 10 + 10}",
                    "permit",
                    str(m.prefix),
                ) + (
                    ("ge", str(match.greater_equal)) if match.greater_equal is not None else ()
                ) + (
                    ("le", str(match.less_equal)) if match.less_equal is not None else ()
                )

    def run_arista(self, device: Any):
        prefix_lists = self.get_prefix_lists(device)
        policies = self.get_policies(device)
        name_generator = PrefixListNameGenerator(prefix_lists, policies)
        processed_names = set()
        for policy in policies:
            for statement in policy.statements:
                cond: SingleCondition[PrefixMatchValue]
                for cond in statement.match.find_all(MatchField.ip_prefix):
                    for name in cond.value.names:
                        plist = name_generator.get_prefix(name, cond.value)
                        if plist.name in processed_names:
                            continue
                        yield from self._arista_prefix_list(plist.name, "ip", cond.value, plist)
                        processed_names.add(plist.name)
                for cond in statement.match.find_all(MatchField.ipv6_prefix):
                    for name in cond.value.names:
                        plist = name_generator.get_prefix(name, cond.value)
                        if plist.name in processed_names:
                            continue
                        yield from self._arista_prefix_list(plist.name, "ipv6", cond.value, plist)
                        processed_names.add(plist.name)
