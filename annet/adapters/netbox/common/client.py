from dataclasses import dataclass
from functools import wraps
from typing import Generic, Optional, List, TypeVar, Callable

from dataclass_rest.http.requests import RequestsClient
from requests import Session

Model = TypeVar("Model")


@dataclass
class PagingResponse(Generic[Model]):
    next: Optional[str]
    previous: Optional[str]
    count: int
    results: List[Model]


Func = TypeVar("Func", bound=Callable)


def _collect(func: Func) -> Func:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        kwargs.setdefault("offset", 0)
        limit = kwargs.setdefault("limit", 100)
        results = []
        method = func.__get__(self, self.__class__)
        has_next = True
        while has_next:
            page = method(*args, **kwargs)
            kwargs["offset"] += limit
            results.extend(page.results)
            has_next = bool(page.next)
        return PagingResponse(
            None, None,
            count=len(results),
            results=results,
        )

    return wrapper


def collect(func: Func, field: str = "") -> Func:
    if not field:
        return _collect(func)

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        value = kwargs.get(field)
        if not value:
            return _collect(func)(*args, **kwargs)

        method = func.__get__(self, self.__class__)
        results = []
        for offset in range(0, len(value), 100):
            kwargs[field] = value[offset:offset + 100]
            page = method(*args, **kwargs)
            results.extend(page.results)
        return PagingResponse(
            None, None,
            count=len(results),
            results=results,
        )

    return wrapper


class BaseNetboxClient(RequestsClient):
    def __init__(self, url: str, token: str):
        url = url.rstrip("/") + "/api/"
        session = Session()
        if token:
            session.headers["Authorization"] = f"Token {token}"
        super().__init__(url, session)
