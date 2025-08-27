from collections.abc import Iterator
from typing import Any, Sequence
from unittest.mock import Mock

from annet.vendors.tabparser import parse_to_tree
from annet.rpl import RouteMap, RoutingPolicy
from annet.rpl_generators import (
    IpPrefixList, CumulusPolicyGenerator, RoutingPolicyGenerator, RDFilter, CommunityList, AsPathFilterGenerator,
    AsPathFilter,  RDFilterFilterGenerator, PrefixListFilterGenerator, CommunityListGenerator
)

from annet.vendors import registry_connector
from .. import MockDevice


def scrub(text: str) -> str:
    splitted = text.split("\n")
    return "\n".join(filter(None, splitted))


def huawei():
    return MockDevice(
        "Huawei CE6870-48S6CQ-EI",
        "VRP V200R001C00SPC700 + V200R001SPH002",
        "vrp85",
    )


def arista():
    return MockDevice(
        "Arista DCS-7368",
        "EOS 4.29.9.1M",
        "arista",
    )


def cumulus():
    return MockDevice(
        "Mellanox SN3700-VS2RO",
        "Cumulus Linux 5.4.0",
        "pc",
    )

def iosxr():
    return MockDevice(
        "Cisco 8712-MOD-M",
        "Cisco IOS XR Release 7.4.2",
        "iosxr",
    )

def juniper():
    return MockDevice(
        "Juniper MX304",
        "JUNOS 22.4R3-S4.5",
        "juniper",
    )


def cumulus_generator(
    routemaps: RouteMap,
    as_path_filters: list[AsPathFilter] | None = None,
    community_lists: list[CommunityList] | None = None,
    prefix_lists: list[IpPrefixList] | None = None,
):
    class TestCumulusPolicyGenerator(CumulusPolicyGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return prefix_lists or []

        def get_community_lists(self, _: Any) -> list:
            return community_lists or []

        def get_as_path_filters(self, _: Any) -> list:
            return as_path_filters or []

        def __call__(self, device: Any) -> Iterator[Sequence[str]]:
            return self.generate_cumulus_rpl(device)

    return TestCumulusPolicyGenerator()


def blackbox_generators(
    routemaps: RouteMap,
    as_path_filters: list[AsPathFilter] | None = None,
    community_lists: list[CommunityList] | None = None,
    prefix_lists: list[IpPrefixList] | None = None,
    rd_filters: list[RDFilter] | None = None,
):
    class BlackboxRdFilterGenerator(RDFilterFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_rd_filters(self, device: Any) -> list[RDFilter]:
            return rd_filters or []

    class BlackboxPrefixListFilterGenerator(PrefixListFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_prefix_lists(self, device: Any) -> Sequence[IpPrefixList]:
            return prefix_lists or []

    class BlackboxAsPathGenerator(AsPathFilterGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_as_path_filters(self, device: Any) -> Sequence[AsPathFilter]:
            return as_path_filters or []

    class BlackboxCommunityListGenerator(CommunityListGenerator):
        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_community_lists(self, device: Any) -> list[CommunityList]:
            return community_lists or []

    class BlackBoxPolicyGenerator(RoutingPolicyGenerator):
        def get_prefix_lists(self, device: Any) -> list[IpPrefixList]:
            return prefix_lists or []

        def get_policies(self, device: Any) -> list[RoutingPolicy]:
            return routemaps.apply(device)

        def get_community_lists(self, device: Any) -> list[CommunityList]:
            return community_lists or []

        def get_rd_filters(self, device: Any) -> list[RDFilter]:
            return rd_filters or []

    storage = Mock()
    return [
        BlackboxPrefixListFilterGenerator(storage),
        BlackboxRdFilterGenerator(storage),
        BlackboxAsPathGenerator(storage),
        BlackboxCommunityListGenerator(storage),
        BlackBoxPolicyGenerator(storage),
    ]


def generate(
    dev: MockDevice,
    routemaps: RouteMap,
    as_path_filters: list[AsPathFilter] | None = None,
    community_lists: list[CommunityList] | None = None,
    prefix_lists: list[IpPrefixList] | None = None,
    rd_filters: list[RDFilter] | None = None,
):
    result: list[str] = []
    if dev.hw.soft.startswith("Cumulus"):
        generator = cumulus_generator(
            routemaps=routemaps,
            as_path_filters=as_path_filters,
            community_lists=community_lists,
            prefix_lists=prefix_lists,
        )
        genoutput = generator.generate_cumulus_rpl(dev)
        result = [" ".join(x) for x in genoutput]
        return scrub("\n".join(result))

    generators = blackbox_generators(
        routemaps=routemaps,
        as_path_filters=as_path_filters,
        community_lists=community_lists,
        prefix_lists=prefix_lists,
        rd_filters=rd_filters,
    )
    for generator in generators:
        if generator.supports_device(dev):
            result.append(generator(dev))
    fmtr = registry_connector.get().match(dev.hw).make_formatter()
    tree = parse_to_tree("\n".join(result), fmtr.split)
    text = fmtr.join(tree)
    return scrub(text)