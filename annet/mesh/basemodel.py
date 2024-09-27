from abc import ABC
from copy import copy
from enum import Enum
from typing import TypeVar, Any, Annotated, get_origin, get_type_hints, get_args, Callable


class Special(Enum):
    NOT_SET = "<NOT SET>"


T = TypeVar('T')


class Merger(ABC):
    def __call__(self, name: str, x: T | Special, y: T | Special) -> T:
        if x is Special.NOT_SET:
            return y
        if y is Special.NOT_SET:
            return x
        return self._merge(name, x, y)

    def _merge(self, name: str, x: T, y: T) -> T:
        raise NotImplementedError


class UseFirst(Merger):
    def _merge(self, name: str, x: T, y: T) -> T:
        return x


class UseLast(Merger):
    def _merge(self, name: str, x: T, y: T) -> T:
        return y


class Forbid(Merger):
    def _merge(self, name: str, x: T, y: T) -> T:
        raise ValueError(f"Override is forbidden for field {name}")


class Concat(Merger):
    def _merge(self, name: str, x: T, y: T) -> T:
        return x + y


class Merge(Merger):
    def _merge(self, name: str, x: T, y: T) -> T:
        return merge(x, y)


class DictMerge(Merger):
    def __init__(self, value_merger: Merger = Forbid):
        self.value_merger = value_merger

    def _merge(self, name: str, x: T, y: T) -> T:
        result = copy(x)
        for key, value in y.items():
            if key in result:
                result[key] = self.value_merger(key, result[key], value)
            else:
                result[key] = value
        return result


class ApplyFunc(Merger):
    def __init__(self, func: Callable):
        self.func = func

    def __call__(self, name: str, x: T | Special, y: T | Special) -> T:
        if x is Special.NOT_SET:
            return y
        return self.func(x, y)


def _get_merger(hint: Any):
    if get_origin(hint) is not Annotated:
        return UseLast()
    for arg in get_args(hint):

        if isinstance(arg, Merger):
            return arg
    return UseLast()


class BaseMeshModel:
    def __init__(self, **kwargs):
        if extra_keys := (kwargs.keys() - self._field_mergers.keys()):
            raise ValueError(f"Extra arguments: {extra_keys}")
        self.__dict__.update(kwargs)

    def unset_attrs(self):
        return type(self)._field_mergers.keys() - vars(self).keys()

    def __repr__(self):
        return f"{self.__class__.__name__}(" + ", ".join(
            f"{key}={value}" for key, value in vars(self).items()
        ) + ")"

    def __init_subclass__(cls, **kwargs):
        cls._field_mergers = {
            field: _get_merger(hint)
            for field, hint in get_type_hints(cls, include_extras=True).items()
        }


def _merge(a: T, b: T) -> T:
    result = copy(a)
    for attr_name, merger in a._field_mergers.items():
        new_value = merger(
            attr_name,
            getattr(a, attr_name, Special.NOT_SET),
            getattr(b, attr_name, Special.NOT_SET),
        )
        if new_value is not Special.NOT_SET:
            setattr(result, attr_name, new_value)
    return result


def merge(first: T, *others: T) -> T:
    for second in others:
        first = _merge(first, second)
    return first
