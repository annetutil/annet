from __future__ import annotations

import contextlib
import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from functools import wraps
from types import TracebackType
from typing import Any, TypeAlias, TypeVar, cast, overload

from annet.connectors import CachedConnector


MinDurationT: TypeAlias = "str | int | None"

# Bound TypeVar used by the decorator helpers so they preserve the signature of
# the function (or class) they wrap.
F = TypeVar("F", bound=Callable[..., Any])


class _Nop:
    def __getattr__(self, item: str) -> _Nop:
        return _Nop()

    def __enter__(self) -> _Nop:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> _Nop:
        return _Nop()

    def __bool__(self) -> bool:
        return False


class Tracing(ABC):
    enabled = False

    @abstractmethod
    def function(self, arg: Callable[..., Any] | None = None, /, **kwargs: Any) -> Callable[..., Any]:
        pass

    @abstractmethod
    def contextmanager(self, arg: Callable[..., Any] | None = None, /, **kwargs: Any) -> Callable[..., Any]:
        pass

    @abstractmethod
    def get_current_span(self, context_value: Any = None) -> Any:
        pass

    @abstractmethod
    def set_device_attributes(self, span: Any, device: Any) -> None:
        pass

    @abstractmethod
    def set_dimensions_attributes(self, span: Any, gen: Any, device: Any) -> None:
        pass

    @abstractmethod
    def start_as_current_span(self, *args: Any, **kwargs: Any) -> AbstractContextManager[Any]:
        pass

    @abstractmethod
    def start_as_linked_span(self, *args: Any, **kwargs: Any) -> AbstractContextManager[Any]:
        pass

    @abstractmethod
    def attach_context(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def inject_context(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def extract_context(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def get_context(self, *args: Any, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    def force_flush(self) -> None:
        pass


class DummyTracing(Tracing):
    def function(self, arg: Callable[..., Any] | None = None, /, **kwargs: Any) -> Callable[..., Any]:
        def decorator(func: F) -> F:
            return func

        return decorator if arg is None else decorator(arg)

    def contextmanager(self, arg: Callable[..., Any] | None = None, /, **kwargs: Any) -> Callable[..., Any]:
        def decorator(cls_or_func: F) -> F:
            return cls_or_func

        return decorator if arg is None else decorator(arg)

    def get_current_span(self, context_value: Any = None) -> Any:
        return None

    def set_device_attributes(self, span: Any, device: Any) -> None:
        return None

    def set_dimensions_attributes(self, span: Any, gen: Any, device: Any) -> None:
        return None

    def start_as_current_span(self, *args: Any, **kwargs: Any) -> AbstractContextManager[Any]:
        return _Nop()

    def start_as_linked_span(self, *args: Any, **kwargs: Any) -> AbstractContextManager[Any]:
        return _Nop()

    def attach_context(self, *args: Any, **kwargs: Any) -> Any:
        return

    def inject_context(self, *args: Any, **kwargs: Any) -> Any:
        return

    def extract_context(self, *args: Any, **kwargs: Any) -> Any:
        return

    def get_context(self, *args: Any, **kwargs: Any) -> Any:
        return

    def force_flush(self) -> None:
        return


class _TracingConnector(CachedConnector[Tracing]):
    name = "Tracing"
    ep_name = "tracing"

    def _get_default(self) -> type[Tracing]:
        return DummyTracing


tracing_connector = _TracingConnector()


@overload
def function(arg: F, /) -> F: ...  # noqa: E704


@overload
def function(arg: None = ..., /, **outer_kwargs: Any) -> Callable[[F], F]: ...  # noqa: E704


def function(arg: Callable[..., Any] | None = None, /, **outer_kwargs: Any) -> Callable[..., Any]:
    def decorator(func: F) -> F:
        cache: Callable[..., Any] | None = None

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal cache
            if cache is None:
                cache = tracing_connector.get().function(func, **outer_kwargs)
            return cache(*args, **kwargs)

        return cast(F, wrapper)

    return decorator if arg is None else decorator(arg)


@overload
def contextmanager(arg: F, /) -> F: ...  # noqa: E704


@overload
def contextmanager(arg: None = ..., /, **outer_kwargs: Any) -> Callable[[F], F]: ...  # noqa: E704


def contextmanager(arg: Any = None, /, **outer_kwargs: Any) -> Any:
    def decorator(cls_or_func: Any) -> Any:
        cache: Any = None

        if inspect.isfunction(cls_or_func):

            @contextlib.contextmanager
            @wraps(cls_or_func)
            def wrapper(*args: Any, **kwargs: Any) -> Iterator[Any]:
                nonlocal cache
                if cache is None:
                    cache = tracing_connector.get().contextmanager(cls_or_func, **outer_kwargs)
                with cache(*args, **kwargs) as val:
                    yield val

            return wrapper
        else:
            original_enter = cls_or_func.__enter__
            original_exit = cls_or_func.__exit__

            @wraps(original_enter)
            def one_shot_enter(*args: Any, **kwargs: Any) -> Any:
                """Wrap after first call, tracing_connector was set up"""
                nonlocal cache
                if cache is None:
                    cls_or_func.__enter__ = original_enter
                    cls_or_func.__exit__ = original_exit
                    cache = tracing_connector.get().contextmanager(cls_or_func, **outer_kwargs)
                return cache.__enter__(*args, **kwargs)  # pylint: disable=unnecessary-dunder-call

            @wraps(original_exit)
            def one_shot_exit(*args: Any, **kwargs: Any) -> Any:
                nonlocal cache
                assert cache is not None  # set by one_shot_enter before exit
                return cache.__exit__(*args, **kwargs)

            setattr(cls_or_func, "__enter__", one_shot_enter)
            setattr(cls_or_func, "__exit__", one_shot_exit)

            return cls_or_func

    return decorator if arg is None else decorator(arg)


@overload
def class_methods(arg: type, /) -> type: ...  # noqa: E704


@overload
def class_methods(arg: None = ..., /, **outer_kwargs: Any) -> Callable[[type], type]: ...  # noqa: E704


def class_methods(arg: Any = None, /, **outer_kwargs: Any) -> Any:
    def decorator(cls: Any) -> Any:
        has_enter, has_exit = False, False

        for name, attr in inspect.getmembers(
            cls, lambda x: inspect.isroutine(x) and not inspect.ismethoddescriptor(x) and not inspect.isbuiltin(x)
        ):
            if getattr(attr, "_disable_class_methods", False):
                continue
            if name == "__enter__":
                has_enter = True
            elif name == "__exit__":
                has_exit = True
            else:
                method = function(**outer_kwargs)(attr)
                if isinstance(inspect.getattr_static(cls, name), staticmethod):
                    method = staticmethod(method)
                setattr(cls, name, method)

        if all((has_enter, has_exit)):
            cls = contextmanager(**outer_kwargs)(cls)

        return cls

    return decorator if arg is None else decorator(arg)


def disable_class_methods(func: F) -> F:
    setattr(func, "_disable_class_methods", True)
    return func
