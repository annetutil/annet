from __future__ import annotations

import abc
import argparse
import contextlib
import functools
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from functools import lru_cache
from typing import Any, ContextManager, Generic, TypeVar, cast, overload

from annet.connectors import Connector


T = TypeVar("T")
_ArgT = TypeVar("_ArgT")
_ArgX = TypeVar("_ArgX")

_ARGS_ATTR_NAME = "_alan_opts"


# =====
class FuncMeta:
    cmd_name: str
    opts: list[Arg[Any] | type[ArgGroup]]
    parent: Callable[..., Any] | None
    parser: argparse.ArgumentParser | None
    sub: argparse._SubParsersAction[Any] | None

    def __init__(self) -> None:
        self.cmd_name = ""
        self.opts = []
        self.parent = None
        self.parser = None
        self.sub = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            + ", ".join(
                (
                    f"cmd_name={self.cmd_name}",
                    f"opt={self.opts}",
                    f"parent={self.parent}",
                    f"parser={self.parser}",
                    f"sub={self.sub}",
                )
            )
            + ")"
        )


def _get_meta(func: Callable[..., Any]) -> FuncMeta:
    if not hasattr(func, _ARGS_ATTR_NAME):
        _reset_meta(func)
    return cast(FuncMeta, getattr(func, _ARGS_ATTR_NAME))


def _reset_meta(func: Callable[..., Any]) -> None:
    setattr(func, _ARGS_ATTR_NAME, FuncMeta())


class ConvertibleDefault:
    def __init__(self, value: str):
        self.value = value

    def convert(self, type_function: Callable[[str], T]) -> T:
        return type_function(self.value)


class DefaultFromEnv(ConvertibleDefault):
    def __init__(self, var_name: str, default_val: str):
        super().__init__(os.environ.get(var_name, default_val))
        self.var_name = var_name

    def convert(self, type_function: Callable[[str], T]) -> T:
        try:
            return super().convert(type_function)
        except Exception:
            function_name = getattr(type_function, "__name__", repr(type_function))
            raise ValueError(f"invalid {function_name} in the {self.var_name} environment variable: {repr(self.value)}")


class Arg(Generic[_ArgT]):
    """CLI argument.

    Acts as a descriptor: declared as a class attribute ``foo = Arg(...)`` on an
    ``ArgGroup``, attribute access on an instance yields the parsed value (like
    ``dataclasses.field``). ``_ArgT`` is that value type, inferred from ``default``/``type``.
    """

    @overload
    def __init__(  # noqa: E704
        self: Arg[_ArgX | None], *args: Any, type: Callable[[str], _ArgX], default: None = ..., **kwargs: Any
    ) -> None: ...

    @overload
    def __init__(  # noqa: E704
        self: Arg[_ArgX], *args: Any, type: Callable[[str], _ArgX], default: _ArgX, **kwargs: Any
    ) -> None: ...

    @overload
    def __init__(self: Arg[_ArgT], *args: Any, default: _ArgT, **kwargs: Any) -> None: ...  # noqa: E704
    @overload
    def __init__(self: Arg[Any], *args: Any, **kwargs: Any) -> None: ...  # noqa: E704

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Конструктор повторяет прототип parser.add_argument()"""
        if args and isinstance(args[0], type(self)):
            # copy constructor
            args = args[0].args
            new_kwargs = args[0].kwargs.copy()
            new_kwargs.update(kwargs)
            kwargs = new_kwargs

        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs

        self._prepared = False
        self.default: Any = None

        self.dest: str | None = None  # заполняется в attach()

    @overload
    def __get__(self, obj: None, owner: type[Any] | None = None) -> Arg[_ArgT]: ...  # noqa: E704
    @overload
    def __get__(self, obj: object, owner: type[Any] | None = None) -> _ArgT: ...  # noqa: E704

    def __get__(self, obj: object | None, owner: type[Any] | None = None) -> Arg[_ArgT] | _ArgT:
        # Instances store the parsed value in __dict__, which shadows this
        # non-data descriptor, so this runs only for class-level access.
        if obj is None:
            return self
        return cast(_ArgT, self.default)

    def _prepare(self) -> None:
        if self._prepared:
            return
        self._prepared = True
        default = self.kwargs.get("default", None)
        if isinstance(default, ConvertibleDefault) and "type" in self.kwargs:
            default = self.kwargs["default"] = default.convert(self.kwargs["type"])
        elif callable(default):
            default = self.kwargs["default"] = default()
        elif default is False and "action" not in self.kwargs:
            self.kwargs["action"] = "store_true"
        self.default = default

        if default is not None and not (default is False and self.kwargs.get("action") == "store_true"):
            if "help" not in self.kwargs:
                self.kwargs["help"] = ""
            self.kwargs["help"] += " (default: %r)" % default

    def attach(self, parser: argparse.ArgumentParser) -> None:
        self._prepare()
        arg = parser.add_argument(*self.args, **self.kwargs)
        self.dest = arg.dest


class ArgGroup:
    """
    Контейнер для нескольких аргументов.
    Класс служит для описания набора аргументов, а экземляр - для хранения значений.

    Пример:
    class Group1(ArgGroup):
        in = Arg("--in")
        out = Arg("--out")

    values = Group1(in="/dev/null", out="/dev/null")
    open(values.in)
    """

    def __init__(self, *args: ArgGroup, **kwargs: Any) -> None:
        """
        В kwargs - пары ключ-значение. Соотвествующие опции должны быть объявлены в классе
        """
        keys = {arg_name: arg.default for arg_name, arg in self._enum_args().items()}
        for src_obj in args:
            for opt, val in vars(src_obj).items():
                if opt in keys:
                    keys[opt] = val
        for opt, val in kwargs.items():
            if opt in keys:
                keys[opt] = val
            else:
                raise TypeError("Unknown argument %r for %s" % (opt, type(self).__qualname__))
        self.__dict__.update(keys)

    @classmethod
    @lru_cache()
    def _enum_args(cls) -> dict[str, Arg[Any]]:
        ret = {}
        for base in cls.__mro__:
            for name, value in vars(base).items():
                if not name.startswith("_") and isinstance(value, Arg):
                    ret[name] = value
        return ret

    @classmethod
    def attach(cls, parser: argparse.ArgumentParser) -> None:
        for arg in cls._enum_args().values():
            arg.attach(parser)

    @classmethod
    def construct_from(cls, ns: argparse.Namespace) -> ArgGroup:
        kwargs = {}
        for arg_name, arg in cls._enum_args().items():
            assert arg.dest is not None
            kwargs[arg_name] = getattr(ns, arg.dest)
        return cls(**kwargs)

    @classmethod
    def copy_from(cls, other: ArgGroup, **more_kwargs: Any) -> ArgGroup:
        kwargs = {}
        for arg_name in cls._enum_args():
            try:
                kwargs[arg_name] = getattr(other, arg_name)
            except AttributeError:
                pass

        kwargs.update(more_kwargs)
        return cls(**kwargs)

    def __repr__(self) -> str:
        return "%(classname)s(%(params)s)" % dict(
            classname=type(self).__qualname__,
            params=", ".join("%s=%r" % (key, getattr(self, key)) for key in sorted(self._enum_args())),
        )

    def stdin(self, **kwargs: str | None) -> dict[str, str | None]:
        ret: dict[str, str | None] = {}
        stdin_used = False
        for arg, val in kwargs.items():
            if val == "-":
                if stdin_used:
                    raise ValueError("stdin can not be used twice")
                self.validate_stdin(arg, val, **kwargs.copy())
                ret[arg] = _read_stdin_once()
                stdin_used = True
            else:
                ret[arg] = None
        return ret

    def validate_stdin(self, arg: str, val: str | None, **kwargs: str | None) -> None:
        pass


class _HelpFormatter(argparse.HelpFormatter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["width"] = self._get_term_width()
        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_term_width() -> int | None:
        try:
            return int(os.environ["COLUMNS"])
        except (KeyError, ValueError):
            try:
                return os.get_terminal_size(sys.stdout.fileno()).columns
            except OSError:
                return None


class ArgDispatcher(abc.ABC):
    @abc.abstractmethod
    def setup(self) -> ContextManager[None]:
        pass

    @abc.abstractmethod
    def exec(self) -> ContextManager[None]:
        pass

    @abc.abstractmethod
    def pre_call(self) -> ContextManager[None]:
        pass

    @contextlib.contextmanager
    def func_opts(self, arg: Arg[Any] | type[ArgGroup]) -> Iterator[None]:
        yield

    @abc.abstractmethod
    def func(self, ns: argparse.Namespace) -> ContextManager[None]:
        pass


class NullArgDispatcher(ArgDispatcher):
    @contextlib.contextmanager
    def setup(self) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def exec(self) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def pre_call(self) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def func_opts(self, arg: Arg[Any] | type[ArgGroup]) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def func(self, ns: argparse.Namespace) -> Iterator[None]:
        yield


class _DispatcherConnector(Connector[ArgDispatcher]):
    name = "Dispatcher"
    ep_name = "dispatcher"

    def _get_default(self) -> type[ArgDispatcher]:
        return NullArgDispatcher


dispatcher_connector = _DispatcherConnector()


class ArgParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "formatter_class" not in kwargs:
            kwargs["formatter_class"] = _HelpFormatter
        super().__init__(*args, **kwargs)
        self._dispatcher: ArgDispatcher = dispatcher_connector.get()

    def argv(self) -> list[str]:
        return sys.argv[1:]

    def add_commands(self, commands: Iterable[Callable[..., Any]]) -> None:
        subparsers = self.add_subparsers()
        pending = list(commands)
        failcount = 0
        while pending and failcount < len(pending):
            func, pending = pending[0], pending[1:]
            if not self.add_func(func, subparsers):
                pending.append(func)
                failcount += 1
            else:
                failcount = 0
        if failcount:
            raise RuntimeError("Failed to resolve subparsers")

    def add_func(self, func: Callable[..., Any], sub: argparse._SubParsersAction[Any]) -> bool:
        meta = _get_meta(func)
        parent = meta.parent
        if parent:
            parent_meta = _get_meta(parent)
            if not parent_meta.parser:
                return False
            if not parent_meta.sub:
                parent_meta.sub = parent_meta.parser.add_subparsers()
            assert parent_meta.sub is not None
            sub = parent_meta.sub

        sp = sub.add_parser(meta.cmd_name, help=func.__doc__)
        sp.set_defaults(func=func)
        meta.parser = sp

        for arg in self.func_opts(func):
            arg.attach(sp)
        return True

    def set_dispatcher(self, dispatcher: ArgDispatcher) -> None:
        self._dispatcher = dispatcher

    def dispatch(
        self, pre_call: Callable[[argparse.Namespace], Any] | None = None, add_help_command: bool = False
    ) -> Any:
        with self._dispatcher.setup():
            with self._dispatcher.exec():
                argv = self.argv()
                if add_help_command and argv and argv[0] == "help":
                    argv.pop(0)
                    argv.append("--help")

                # show usage in cache when no options specified
                if not argv:
                    argv = [""]

                ns = self.parse_args(argv)
                assert ns.func
                if pre_call:
                    with self._dispatcher.pre_call():
                        pre_call(ns)

                values = []
                for arg in self.func_opts(ns.func):
                    with self._dispatcher.func_opts(arg):
                        if isinstance(arg, Arg):
                            assert arg.dest is not None
                            values.append(getattr(ns, arg.dest))
                        else:
                            # arg is a ArgGroup-derived type
                            values.append(arg.construct_from(ns))

                with self._dispatcher.func(ns):
                    return ns.func(*values)

    @staticmethod
    def find_subcommands(variables: dict[str, Any]) -> Iterator[Callable[..., Any]]:
        for var in variables.values():
            if callable(var) and hasattr(var, _ARGS_ATTR_NAME):
                yield var

    @classmethod
    def func_opts(cls, func: Callable[..., Any]) -> Iterator[Arg[Any] | type[ArgGroup]]:
        yield from _get_meta(func).opts


def subcommand(
    *arg_list: Arg[Any] | type[ArgGroup], parent: Callable[..., Any] | None = None, is_group: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    декоратор, задающий cli-аргументы подпрограммы

    Пример:
    @subcommand(Arg(), ArgGroup)
    def cmd1(arg1, arg2):
        pass

    Связь аргументов происходит только по порядковому номеру, каждый аргумент subcommand становится аргументом функции.
    Функция вызывается только с позиционными аргументами, всегда с одним и тем же количеством аргументов.

    Для создания более одного уровня команд используется аргумент parent

    Пример: 'ann some thing' - вызовет some_thing()

    @subcommand()
    def some():
        pass


    @subcommand(parent=some)
    def some_thing():
        pass
    """

    def _amend_func(func: Callable[..., Any]) -> Callable[..., Any]:
        meta = _get_meta(func)
        if is_group:

            @functools.wraps(func)
            def group_func() -> None:
                assert meta.parser is not None
                meta.parser.print_help()

            func = group_func

        cmd_name = func.__name__
        if parent:
            parentprefix = parent.__name__ + "_"
            if cmd_name.startswith(parentprefix):
                cmd_name = cmd_name[len(parentprefix) :]
            meta.parent = parent

        meta.cmd_name = cmd_name.replace("_", "-").lower()
        meta.opts.extend(arg_list)
        return func

    return _amend_func


@functools.lru_cache()
def _read_stdin_once() -> str:
    return sys.stdin.read()
