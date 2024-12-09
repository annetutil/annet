from typing import Any

from annet.generators import BaseGenerator
from annet.rpl import RouteMap
from annet.rpl_generators import (
    CommunityListGenerator, RoutingPolicyGenerator, AsPathFilterGenerator, CommunityList, AsPathFilter,
    RDFilterFilterGenerator, RDFilter, PrefixListFilterGenerator, IpPrefixList
)
from annet.storage import Storage
from .items import COMMUNITIES, AS_PATH_FILTERS, RD_FILTERS, PREFIX_LISTS
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

    def get_rd_filters(self, device: Any) -> list[RDFilter]:
        return RD_FILTERS


class AsPathGenerator(AsPathFilterGenerator):
    def get_routemap(self) -> RouteMap:
        return routemap

    def get_as_path_filters(self, device: Any) -> list[AsPathFilter]:
        return AS_PATH_FILTERS


class RDGenerator(RDFilterFilterGenerator):
    def get_routemap(self) -> RouteMap:
        return routemap

    def get_rd_filters(self, device: Any) -> list[RDFilter]:
        return RD_FILTERS


class PrefixListGenerator(PrefixListFilterGenerator):
    def get_routemap(self) -> RouteMap:
        return routemap

    def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
        return PREFIX_LISTS


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        AsPathGenerator(store),
        PolicyGenerator(store),
        CommunityGenerator(store),
        RDGenerator(store),
        PrefixListGenerator(store),
    ]
