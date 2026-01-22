import logging

from annet.lib.valkit import valid_object_path
from annet.lib.valkit import valid_logging_level

from typing import List
from typing import Any

import pytest

from annet.lib.valkit import ValidatorError
from annet.lib.valkit import valid_bool
from annet.lib.valkit import valid_number
from annet.lib.valkit import valid_string_list


# =====
@pytest.mark.parametrize(
    "arg, retval",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        (1, True),
        (True, True),
        ("0", False),
        ("false", False),
        ("FALSE", False),
        ("no", False),
        (0, False),
        (False, False),
    ],
)
def test_ok__valid_bool(arg: Any, retval: bool) -> None:
    assert valid_bool(arg) == retval


@pytest.mark.parametrize(
    "arg",
    [
        "x",
        -1,
        "",
        None,
    ],
)
def test_fail__valid_bool(arg: Any) -> None:
    with pytest.raises(ValidatorError):
        valid_bool(arg)


# =====
@pytest.mark.parametrize(
    "arg, retval",
    [
        ("1", 1),
        ("-1", -1),
        (1, 1),
        (-1, -1),
        (0, 0),
        (100500, 100500),
    ],
)
def test_ok__valid_number(arg: Any, retval: int) -> None:
    assert valid_number(arg) == retval


@pytest.mark.parametrize(
    "arg",
    [
        "1x",
        "",
        None,
        100500.0,
    ],
)
def test_fail__valid_number(arg: Any) -> None:
    with pytest.raises(ValidatorError):
        valid_number(arg)


@pytest.mark.parametrize(
    "arg, retval",
    [
        (-5, -5),
        (0, 0),
        (5, 5),
        ("-5", -5),
        ("0", 0),
        ("5", 5),
    ],
)
def test_ok__valid_number__min_max(arg: Any, retval: int) -> None:
    assert valid_number(arg, -5, 5) == retval


@pytest.mark.parametrize(
    "arg",
    [
        -6,
        6,
        "-6",
        "6",
    ],
)
def test_fail__valid_number__min_max(arg: Any) -> None:  # pylint: disable=invalid-name
    with pytest.raises(ValidatorError):
        valid_number(arg, -5, 5)


# =====
@pytest.mark.parametrize(
    "arg, retval",
    [
        ("a, b, c", ["a", "b", "c"]),
        ("a b c", ["a", "b", "c"]),
        (["a", "b", "c"], ["a", "b", "c"]),
    ],
)
def test_ok__valid_string_list(arg: Any, retval: List) -> None:
    assert valid_string_list(arg) == retval


@pytest.mark.parametrize(
    "arg, retval",
    [
        ("1, 2, 3", [1, 2, 3]),
        ("1 2 3", [1, 2, 3]),
        ([1, 2, 3], [1, 2, 3]),
    ],
)
def test_ok__valid_string_list__subval(
    arg: Any, retval: List
) -> None:  # pylint: disable=invalid-name
    assert valid_string_list(arg, subval=int) == retval


def test_fail__valid_string_list__none() -> None:  # pylint: disable=invalid-name
    with pytest.raises(ValidatorError):
        valid_string_list(None)


@pytest.mark.parametrize(
    "arg",
    [
        "__test",
        "__test__",
        "Object_Name",
        "objectName123",
        "_",
        "__test.test",
        "_._._",
    ],
)
def test_ok__valid_object_path(arg: Any) -> None:
    assert valid_object_path(arg) == arg


@pytest.mark.parametrize(
    "arg",
    [
        ".object",
        "123object",
        "/object",
        "a.b.c.",
        "a.1x.b",
    ],
)
def test_fail__valid_object_path(arg: Any) -> None:
    with pytest.raises(ValidatorError):
        valid_object_path(arg)


# =====
@pytest.mark.parametrize(
    "arg, retval",
    [
        *list(
            zip(logging._levelToName, logging._levelToName)
        ),  # pylint: disable=protected-access
        *[
            (str(arg), arg) for arg in logging._levelToName
        ],  # pylint: disable=protected-access
        *list(logging._nameToLevel.items()),  # pylint: disable=protected-access
        *[
            (arg.lower(), retval) for (arg, retval) in logging._nameToLevel.items()
        ],  # pylint: disable=protected-access
    ],
)
def test_ok__valid_logging_level(arg: Any, retval: int) -> None:
    assert valid_logging_level(arg) == retval


@pytest.mark.parametrize(
    "arg",
    [
        "foo",
        "bar",
        "111",
        111,
        "info",
    ],
)
def test_fail__valid_logging_level(arg: Any) -> None:
    with pytest.raises(ValidatorError):
        valid_logging_level(arg, up=False)
