from dataclasses import dataclass
from typing import List, Union, Iterable, Optional

from annet.storage import Query


@dataclass
class NetboxQuery(Query):
    query: List[str]

    @classmethod
    def new(
            cls, query: Union[str, Iterable[str]],
            hosts_range: Optional[slice] = None,
    ) -> "NetboxQuery":
        if hosts_range is not None:
            raise ValueError("host_range is not supported")
        return cls(query=list(query))

    @property
    def globs(self):
        # We process every query host as a glob
        return self.query

    def is_empty(self) -> bool:
        return len(self.query) == 0
