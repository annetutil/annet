from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from annet.generators import PartialGenerator
from annet.rpl import RouteMap, SingleCondition, MatchField, ThenField, RoutingPolicy
from .entities import CommunityList, CommunityLogic, CommunityType


def get_used_community_lists(
        communities: list[CommunityList], policies: list[RoutingPolicy],
) -> list[CommunityList]:
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
        communities_dict[name] for name in sorted(used_communities)
    ]


class CommunityListGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_routemap(self) -> RouteMap:
        raise NotImplementedError()

    @abstractmethod
    def get_community_lists(self, device: Any) -> list[CommunityList]:
        raise NotImplementedError()

    def get_used_community_lists(self, device: Any) -> list[CommunityList]:
        return get_used_community_lists(
            communities=self.get_community_lists(device),
            policies=self.get_routemap().apply(device),
        )

    def acl_huawei(self, _):
        return r"""
        ip community-filter
        ip extcommunity-filter
        ip extcommunity-list
        ip large-community-filter
        """

    def ref_huawei(self, _):
        return """
        route-policy
            if-match community-filter <name>
            if-match extcommunity-filter <name>
            if-match extcommunity-list soo <name>
            if-match large-community-filter <name>
            apply comm-filter <name>
        """

    def _huawei_community_filter(self, index: int, community_list: CommunityList, members: str) -> Sequence[str]:
        if community_list.type is CommunityType.BASIC:
            return "ip community-filter basic", community_list.name, f"index {index}", "permit", members
        elif community_list.type is CommunityType.RT:
            return "ip extcommunity-filter basic", community_list.name, f"index {index}", "permit", members
        elif community_list.type is CommunityType.SOO:
            return "ip extcommunity-list soo", community_list.name, f"index {index}", "permit", members
        elif community_list.type is CommunityType.LARGE:
            return "ip large-community-filter", community_list.name, f"index {index}", "permit", members
        else:
            raise NotImplementedError(f"CommunityList type {community_list.type} not implemented for huawei")

    def run_huawei(self, device: Any):
        for community_list in self.get_used_community_lists(device):
            if community_list.type is CommunityType.RT:
                # RT communities used with prefix rt
                members: Sequence[str] = [f"rt {m}" for m in community_list.members]
            else:
                members = community_list.members

            if community_list.logic == CommunityLogic.AND:
                # to get AND logic the communities should be in one sting
                yield self._huawei_community_filter(10, community_list, " ".join(members))
            elif community_list.logic == CommunityLogic.OR:
                for i, member in enumerate(members):
                    member_id = (i + 1) * 10
                    yield self._huawei_community_filter(member_id, community_list, member)
            else:
                raise NotImplementedError
