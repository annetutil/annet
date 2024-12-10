from typing import Any

from annet.generators import BaseGenerator, Entire
from annet.rpl import RouteMap
from annet.rpl_generators import (
    CommunityListGenerator, RoutingPolicyGenerator, AsPathFilterGenerator, CommunityList, AsPathFilter,
    RDFilterFilterGenerator, RDFilter, PrefixListFilterGenerator, IpPrefixList, CumulusPolicyGenerator
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


FRR_HEADER = """\
!!! This file is auto-generated
!
frr defaults datacenter
log syslog informational
log timestamp precision 6
service integrated-vtysh-config"""


class FrrGenerator(Entire, CumulusPolicyGenerator):
    def get_routemap(self) -> RouteMap:
        return routemap

    def get_community_lists(self, device: Any) -> list[CommunityList]:
        return COMMUNITIES

    def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
        return PREFIX_LISTS

    def get_as_path_filters(self, device: Any) -> list[AsPathFilter]:
        raise AS_PATH_FILTERS

    def path(self, device):
        if device.hw.PC.Mellanox or device.hw.PC.NVIDIA:
            return "/etc/frr/frr.conf"

    def run(self, device):
        yield FRR_HEADER
        yield from self.generate_cumulus_rpl(device)
        yield "line vty"


def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        AsPathGenerator(store),
        PolicyGenerator(store),
        CommunityGenerator(store),
        RDGenerator(store),
        PrefixListGenerator(store),
        FrrGenerator(store),
    ]
