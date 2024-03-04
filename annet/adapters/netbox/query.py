from dataclasses import dataclass
from typing import List

from annet.storage import Query


@dataclass
class NetboxQuery(Query):
    query: List[str]

    @classmethod
    def new(cls, query, hosts_range) -> "NetboxQuery":
        if hosts_range is not None:
            raise ValueError("host_range is not supported")
        return cls(query=query)

    @property
    def globs(self):
        # We process every query host as a glob
        return self.query
