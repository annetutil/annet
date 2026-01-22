import logging
import re
from typing import Any, Callable, List, NoReturn, Optional, Type, Union


def add_validator_magic(validator):  # type: ignore
    def make(*args, ig=None, **kwargs):  # type: ignore
        if ig is None:
            partial = lambda arg: validator(arg, *args, **kwargs)  # noqa: E731
        else:
            partial = lambda arg: validator(arg, *args, **kwargs)[ig]  # noqa: E731
        return partial

    validator.mk = make
    return validator


def check_re_match(
    arg: Any,
    name: str,
    pattern: str,
    strip: bool = False,
    limit: Optional[int] = None,
) -> Any:
    arg = not_none_string(arg, name, strip)
    if limit is not None:
        arg = arg[:limit]
    if re.match(pattern, arg) is None:
        raise_validator(arg, name)
    return arg


def check_in_list(
    arg: Any,
    name: str,
    variants: List,
) -> Any:
    if arg not in variants:
        raise_validator(arg, name)
    return arg


# =====
class ValidatorError(ValueError):
    pass


# =====
def raise_validator(
    arg: Any,
    name: str,
    err_extra: str = "",
) -> NoReturn:
    err_extra = ": %s" % (err_extra) if err_extra else ""
    arg_str = ("%r" if isinstance(arg, (str, bytes)) else "'%s'") % (arg)
    raise ValidatorError(
        ("The argument " + arg_str + " is not a valid %s%s") % (name, err_extra)
    )


def not_none(
    arg: Any,
    name: str,
) -> Any:  # FIXME -> NotNone

    if arg is None:
        raise ValidatorError("Empty argument is not a valid %s" % (name))
    return arg


def not_none_string(
    arg: Any,
    name: str,
    strip: bool = False,
) -> str:
    arg = str(not_none(arg, name))
    return arg.strip() if strip else arg


@add_validator_magic
def valid_logging_level(
    arg: Any,
    up: bool = True,
    strip: bool = False,
) -> int:
    name = "logging level"
    try:
        arg = int(arg)
        if arg not in logging._levelToName:  # pylint: disable=protected-access
            raise_validator(arg, name)
        return arg
    except ValueError:
        arg = not_none_string(arg, name, strip)
        try:
            return logging._nameToLevel[
                arg.upper() if up else arg
            ]  # pylint: disable=protected-access
        except KeyError:
            raise_validator(arg, name)


@add_validator_magic
def valid_string_list(
    arg: Any,
    delim: str = r"[,\t ]+",
    subval: Optional[Callable[[Any], Any]] = None,
    strip: bool = False,
) -> List[str]:
    if not isinstance(arg, (list, tuple)):
        arg = not_none_string(arg, "string list", strip)
        arg = list(filter(None, re.split(delim, arg)))
        if subval is not None:
            arg = list(map(subval, arg))
    return arg


@add_validator_magic
def valid_bool(
    arg: Any,
    strip: bool = False,
) -> bool:
    true_args = ["1", "true", "yes"]
    false_args = ["0", "false", "no"]
    name = "bool (%r or %r)" % (true_args, false_args)
    arg = not_none_string(arg, name, strip).lower()
    arg = check_in_list(arg, name, true_args + false_args)
    return arg in true_args


@add_validator_magic
def valid_bool_list(
    arg: Any,
    delim: str = r"[,\t ]+",
    subval: Optional[Callable[[Any], Any]] = None,
    strip: bool = False,
) -> List[bool]:
    arg = valid_string_list(arg, delim, subval, strip)
    arg = [valid_bool(x, strip) for x in arg]
    return arg


@add_validator_magic
def valid_number(
    arg: Any,
    min: Union[int, float, None] = None,  # pylint: disable=redefined-builtin
    max: Union[int, float, None] = None,  # pylint: disable=redefined-builtin
    type: Union[Type[int], Type[float]] = int,  # pylint: disable=redefined-builtin
    strip: bool = False,
) -> Union[int, float]:
    arg = not_none_string(arg, type.__name__, strip)
    try:
        arg = type(arg)
    except Exception:
        raise_validator(arg, type.__name__)

    if min is not None and arg < min:
        raise ValidatorError(
            "The argument '%s' must be greater or equial than %s" % (arg, min)
        )
    if max is not None and arg > max:
        raise ValidatorError(
            "The argument '%s' must be lesser or equal then %s" % (arg, max)
        )
    return arg


@add_validator_magic
def valid_object_path(
    arg: Any,
    strip: bool = False,
) -> str:
    pattern = r"^([a-zA-Z_][a-zA-Z0-9_]*\.)*[a-zA-Z_][a-zA-Z0-9_]*$"
    return check_re_match(arg, "Python object path", pattern, strip)
