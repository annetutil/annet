from abc import abstractmethod, ABC
from collections.abc import Sequence
from ipaddress import ip_interface
from typing import Any, Literal, Iterable

from annet.rpl import RouteMap, RoutingPolicy, PrefixMatchValue, SingleCondition, MatchField
from .community import get_used_community_lists
from .entities import IpPrefixList, mangle_ranged_prefix_list_name, CommunityList, CommunityLogic, CommunityType
from .prefix_lists import get_used_prefix_lists


class CumulusPolicyGenerator(ABC):
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
        yield from self._cumulus_communities(device, policies)
        yield from self._cumulus_prefix_lists(device, policies)
        yield from self._cumulus_policy_config(device, policies)

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

    def _cumulus_communities(self, device: Any, policies: list[RoutingPolicy]) -> Iterable[Sequence[str]]:
        """ BGP community-lists section configuration """
        communities = get_used_community_lists(
            communities=self.get_community_lists(device),
            policies=policies,
        )

        for clist in communities:
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
                yield cmd, "expanded", clist.name, "permit", member_prefix, ",".join(f"\"{m}\"" for m in clist.members)
            else:
                yield cmd, "standard", clist.name, "permit", " ".join(f"\"{member_prefix} {m}\"" for m in clist.members)
        yield "!"

    def _cumulus_policy_config(self, device: Any, policies: list[RoutingPolicy]) -> Iterable[Sequence[str]]:
        """ Route maps configuration """
