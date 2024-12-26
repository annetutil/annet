from abc import abstractmethod, ABC
from collections.abc import Sequence
from typing import Any

from annet.generators import PartialGenerator
from annet.rpl import RouteMap, MatchField, RoutingPolicy
from .entities import RDFilter


class RDFilterFilterGenerator(PartialGenerator, ABC):
    TAGS = ["policy", "rpl", "routing"]

    @abstractmethod
    def get_policies(self, device: Any) -> list[RoutingPolicy]:
        raise NotImplementedError()

    @abstractmethod
    def get_rd_filters(self, device: Any) -> Sequence[RDFilter]:
        raise NotImplementedError()

    def get_used_rd_filters(self, device: Any) -> Sequence[RDFilter]:
        filters = {c.name: c for c in self.get_rd_filters(device)}
        policies = self.get_policies(device)
        used_filters = set()
        for policy in policies:
            for statement in policy.statements:
                for condition in statement.match.find_all(MatchField.rd):
                    used_filters.update(condition.value)
        return [filters[name] for name in sorted(used_filters)]

    def acl_huawei(self, _):
        return r"""
        ip rd-filter
        """

    def run_huawei(self, device: Any):
        for rd_filter in self.get_used_rd_filters(device):
            for i, route_distinguisher in enumerate(rd_filter.members):
                rd_id = (i + 1) * 10 + 5
                yield "ip rd-filter", rd_filter.number, f"index {rd_id}", "permit", route_distinguisher
