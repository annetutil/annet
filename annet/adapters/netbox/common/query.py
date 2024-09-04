from dataclasses import dataclass
from typing import Any, List, Union, Iterable, Optional

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
        query = cls(query=list(query))
        query = hostname_dot_hack(query)
        return query

    @property
    def globs(self):
        # We process every query host as a glob
        return self.query

    def is_empty(self) -> bool:
        return len(self.query) == 0


def hostname_dot_hack(netbox_query: NetboxQuery) -> NetboxQuery:
    # there is no proper way to lookup host by its hostname
    # ie find "host" with fqdn "host.example.com"
    # besides using name__ic (ie startswith)
    # since there is no direct analogue for this field in netbox
    # so we need to add a dot to hostnames (top-level fqdn part)
    # so we would not receive devices with a common name prefix
    def add_dot(raw_query: Any) -> Any:
        if isinstance(raw_query, str) and "." not in raw_query:
            raw_query = raw_query + "."
        return raw_query

    raw_query = netbox_query.query
    if isinstance(raw_query, list):
        for i, name in enumerate(raw_query):
            raw_query[i] = add_dot(name)

    return NetboxQuery(raw_query)
