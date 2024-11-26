from typing import Any

from annet.generators import BaseGenerator
from annet.rpl import RouteMap
from annet.rpl_generators import CommunityListGenerator, RoutingPolicyGenerator
from annet.rpl_generators.entities import CommunityList
from annet.storage import Storage
from .items import COMMUNITIES
from .route_policy import routemap


class CommunityGenerator(CommunityListGenerator):
    def get_community_lists(self, device: Any) -> list[CommunityList]:
        return COMMUNITIES

    def get_routemap(self) -> RouteMap:
        return routemap


class PolicyGenerator(RoutingPolicyGenerator):
    def get_routemap(self) -> RouteMap:
        return routemap

    def get_community_lists(self, device: Any) -> list[CommunityList]:
        return COMMUNITIES


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        PolicyGenerator(store),
        CommunityGenerator(store),
    ]
