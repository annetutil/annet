from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from annet.generators import PartialGenerator
from annet.rpl import RouteMap, MatchField
from .entities import AsPathFilter


class AsPathFilterGenerator(PartialGenerator, ABC):
    @abstractmethod
    def get_routemap(self) -> RouteMap:
        raise NotImplementedError

    @abstractmethod
    def get_as_path_filters(self, device: Any) -> Sequence[AsPathFilter]:
        raise NotImplementedError

    def get_used_as_path_filters(self, device: Any) -> Sequence[AsPathFilter]:
        filters = {c.name: c for c in self.get_as_path_filters(device)}
        policies = self.get_routemap().apply(device)
        used_filters = set()
        for policy in policies:
            for statement in policy.statements:
                for condition in statement.match.find_all(MatchField.as_path_filter):
                    used_filters.add(condition.value)
        return [filters[name] for name in used_filters]

    def acl_huawei(self, _):
        return r"""
        ip as-path-filter
        """

    def run_huawei(self, device: Any):
        for as_path_filter in self.get_used_as_path_filters(device):
            values = "_".join((x for x in as_path_filter.filters if x != ".*"))
            yield "ip as-path-filter", as_path_filter.name, "index 10 permit", f"_{values}_"
