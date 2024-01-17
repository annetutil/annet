import contextlib
import inspect
from abc import ABC, abstractmethod
from functools import wraps
from typing import Optional, Type, Union

from annet.connectors import CachedConnector


MinDurationT = Optional[Union[str, int]]


class _Nop:
    def __getattr__(self, item):
        return _Nop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __call__(self, *args, **kwargs):
        return _Nop()

    def __bool__(self):
        return False


class Tracing(ABC):
    enabled = False

    @abstractmethod
    def function(self, arg=None, /, **kwargs):
        pass

    @abstractmethod
    def contextmanager(self, arg=None, /, **kwargs):
        pass

    @abstractmethod
    def get_current_span(self, context_value=None):
        pass

    @abstractmethod
    def set_device_attributes(self, span, device):
        pass

    @abstractmethod
    def start_as_current_span(self, *args, **kwargs):
        pass

    @abstractmethod
    def start_as_linked_span(self, *args, **kwargs):
        pass

    @abstractmethod
    def attach_context(self, *args, **kwargs):
        pass

    @abstractmethod
    def inject_context(self, *args, **kwargs):
        pass

    @abstractmethod
    def extract_context(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_context(self, *args, **kwargs):
        pass

    @abstractmethod
    def force_flush(self):
        pass


class DummyTracing(Tracing):
    def function(self, arg=None, /, **kwargs):
        def decorator(func):
            return func

        return decorator if arg is None else decorator(arg)

    def contextmanager(self, arg=None, /, **kwargs):
        def decorator(cls_or_func):
            return cls_or_func

        return decorator if arg is None else decorator(arg)

    def get_current_span(self, context_value=None):
        return None

    def set_device_attributes(self, span, device):
        return None

    def start_as_current_span(self, *args, **kwargs):
        return _Nop()

    def start_as_linked_span(self, *args, **kwargs):
        return _Nop()

    def attach_context(self, *args, **kwargs):
        return

    def inject_context(self, *args, **kwargs):
        return

    def extract_context(self, *args, **kwargs):
        return

    def get_context(self, *args, **kwargs):
        return

    def force_flush(self):
        return


class _TracingConnector(CachedConnector[Tracing]):
    name = "Tracing"
    ep_name = "tracing"

    def _get_default(self) -> Type[Tracing]:
        return DummyTracing


tracing_connector = _TracingConnector()


def function(arg=None, /, **outer_kwargs):
    def decorator(func):
        cache = None

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal cache
            if cache is None:
                cache = tracing_connector.get().function(func, **outer_kwargs)
            return cache(*args, **kwargs)

        return wrapper

    return decorator if arg is None else decorator(arg)


def contextmanager(arg=None, /, **outer_kwargs):
    def decorator(cls_or_func):
        if inspect.isfunction(cls_or_func):
            cache = None

            @contextlib.contextmanager
            @wraps(cls_or_func)
            def wrapper(*args, **kwargs):
                nonlocal cache
                if cache is None:
                    cache = tracing_connector.get().contextmanager(cls_or_func, **outer_kwargs)
                with cache(*args, **kwargs) as val:
                    yield val

            return wrapper
        else:
            @wraps(cls_or_func.__enter__)
            def enter(*args, **kwargs):
                tracing_connector.get().contextmanager(cls_or_func, **outer_kwargs)  # redefine __enter__ and __exit__
                return cls_or_func.__enter__(*args, **kwargs)  # pylint: disable=unnecessary-dunder-call

            setattr(cls_or_func, "__enter__", enter)
            return cls_or_func

    return decorator if arg is None else decorator(arg)
