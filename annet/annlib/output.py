import abc
import dataclasses
import enum
import io
import json
import os
import sys
import types
from collections import OrderedDict as odict
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any, List, Pattern, cast

import colorama
import pygments
import pygments.formatters
import pygments.lexers.data
import yaml


LABEL_NEW_PREFIX = "new: "


# =====
class OutputWriter:
    def __init__(self, data: Any) -> None:
        self.data = data

    def write(self, file: IO[str]) -> None:
        if isinstance(self.data, types.GeneratorType):
            for n in self.data:
                file.write(n)
            return
        file.write(self.data)

        if self.data and self.data[-1:] != "\n":
            file.write("\n")


class YamlWriter(OutputWriter):
    def write(self, file: IO[str]) -> None:
        print_as_yaml(self.data, file)


class JsonWriter(OutputWriter):
    def write(self, file: IO[str]) -> None:
        print_as_json(self.data, fh=file)


def dir_or_file_output(dest: str | None, items_count: int, create_dir: bool = True, suggest_dir: bool = False) -> bool:
    if dest is None:
        dest = ""

    dir_mode = dest.endswith(os.sep) or suggest_dir or dest not in ("-", "") and items_count > 1

    if os.path.exists(dest):
        is_dir = os.path.isdir(dest)
        if dir_mode and not is_dir:
            raise EnvironmentError(f"Output set to dir {dest}, but file with the same name is on the way")
        dir_mode = dir_mode or is_dir
    elif create_dir and dest not in ("-", ""):
        pdir = dest if dir_mode else os.path.dirname(dest)
        if pdir:
            os.makedirs(pdir, exist_ok=True)

    return dir_mode


def print_label(label: str, back_color: str = colorama.Back.GREEN, file: IO[str] | None = None) -> None:
    if file is None:
        file = sys.stdout
    tty = bool(os.isatty(file.fileno()))
    print(
        "%s%s# %s %s %s%s%s"
        % (
            colorama.Style.BRIGHT * tty,
            back_color * tty,
            "-" * 20,
            label,
            "-" * 20,
            colorama.Back.RESET * tty,
            colorama.Style.RESET_ALL * tty,
        ),
        file=file,
    )


def print_err_label(label: str) -> None:
    print_label(label, colorama.Back.RED)


def print_as_yaml(data: Any, fh: IO[str] = sys.stdout) -> None:
    class UnsortableTuple(tuple[Any, ...]):
        def __lt__(self, _: object) -> bool:
            raise TypeError

    class Dumper(yaml.Dumper):
        def ignore_aliases(self, data: Any) -> bool:
            return True

        def represent_ordered_dict(self, data: Any) -> Any:
            return self.represent_dict([UnsortableTuple(item) for item in data.items()])

    Dumper.add_representer(odict, Dumper.represent_ordered_dict)

    def yaml_dump(data: Any, **kwargs: Any) -> str:
        return cast(str, yaml.dump(data, allow_unicode=True, indent=4, Dumper=Dumper, **kwargs))

    if fh.isatty():
        pygments.highlight(
            code=yaml_dump(data, width=os.get_terminal_size().columns),
            lexer=pygments.lexers.data.YamlLexer(),
            formatter=pygments.formatters.TerminalFormatter(bg="dark"),
            outfile=fh,
        )
    else:
        fh.write(yaml_dump(data))


class Dumpable(abc.ABC):
    def dump(self) -> Any:
        pass


class JsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        # https://github.com/PyCQA/pylint/issues/3537
        if isinstance(o, Pattern):  # pylint: disable=isinstance-second-argument-not-valid-type
            return "(regex obj)/" + o.pattern + "/ (not a string)"
        elif isinstance(o, Dumpable):
            return o.dump()
        elif dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        elif isinstance(o, enum.Enum):
            return o.value

        raise TypeError("can't serialize %r to json" % o)

    def encode(self, o: Any) -> str:
        try:
            return super().encode(o)
        except TypeError:
            raise TypeError("can't serialize %r to json" % o)


def print_as_json(data: Any, sort_keys: bool = True, fh: IO[str] = sys.stdout, highlight: bool = True) -> None:
    """
    В выводе dict ключи отсортированы по имени, кроме ключей в OrderedDict,
    которые сохраняют свой оригинальный порядок
    """

    class ODictKey(str):
        """
        Строка с дополнительным параметром :index, по которому сортируется
        """

        ind: int

        @staticmethod
        def __new__(cls, str_value: str, index: int = 0) -> "ODictKey":
            self = str.__new__(cls, str_value)
            self.ind = index
            return self

        def __lt__(self, other: Any) -> bool:
            assert type(self) is type(other)
            return (self.ind, self) < (other.ind, other)  # pylint: disable=no-member

    class UnsortableOdict(odict[str, Any]):
        """
        Разновидность OrderedDict, ключи которого сохраняют порядок
        при попытке строковой сортировки (содержат доп. индекс)
        """

        def __init__(self, orig: odict[str, Any]) -> None:
            super().__init__((ODictKey(key, index), value) for (index, (key, value)) in enumerate(orig.items()))

        @staticmethod
        def convert_odicts(data: Any) -> Any:
            self = UnsortableOdict.convert_odicts
            if isinstance(data, dict):
                data = type(data)((key, self(value)) for (key, value) in data.items())
            elif isinstance(data, (tuple, list)):
                data = type(data)(self(value) for value in data)
            if isinstance(data, odict):
                data = UnsortableOdict(data)
            return data

    if sort_keys:
        dump_data = UnsortableOdict.convert_odicts(data)
    else:
        dump_data = data

    dump_kwargs: dict[str, Any] = dict(cls=JsonEncoder, ensure_ascii=False)

    if fh.isatty() and highlight:
        pygments.highlight(
            code=json.dumps(dump_data, indent=4, **dump_kwargs) + "\n",
            lexer=pygments.lexers.data.JsonLexer(),
            formatter=pygments.formatters.TerminalFormatter(bg="dark"),
            outfile=fh,
        )
    else:
        json.dump(dump_data, fh, **dump_kwargs)
        fh.write("\n")


class TextArgs:
    __slots__ = ("text", "color", "offset")

    def __init__(self, text: str, color: str | None = None, offset: int | None = None) -> None:
        self.text = text
        self.color = color
        self.offset = offset  # смещение от начала линии

    def __repr__(self) -> str:
        return "%s(%r, %s, %s)" % (self.__class__.__name__, self.text, self.color, self.offset)


# =====
@contextmanager
def capture_output(new_stdout: io.IOBase | None = None, new_stderr: io.IOBase | None = None) -> Iterator[None]:
    streams = (
        (sys.stdout, new_stdout),
        (sys.stderr, new_stderr),
    )
    backup = []
    for std_stream, new_stream in streams:
        if new_stream is not None:
            new_stream.seek(0)
            new_stream.truncate(0)
            std_fd = std_stream.fileno()
            std_stream.flush()
            backup.append((std_fd, os.fdopen(os.dup(std_fd), "w"), new_stream))
            os.dup2(new_stream.fileno(), std_fd)
    try:
        yield
    finally:
        for std_fd, backup_stream, stream in backup:
            backup_stream.flush()
            os.dup2(backup_stream.fileno(), std_fd)
            backup_stream.close()
            stream.seek(0)


def format_file_diff(diff_lines: List[str]) -> List[str]:
    colors = (
        ("+++", colorama.Fore.CYAN),
        ("---", colorama.Fore.CYAN),
        ("@@", colorama.Fore.CYAN),
        ("+", colorama.Fore.GREEN),
        ("-", colorama.Fore.RED),
    )
    ret = []
    for line in diff_lines:
        for check, color in colors:
            if line.startswith(check):
                ret.append(color + line + colorama.Fore.RESET)
                break
        else:
            ret.append(line)
    return ret
