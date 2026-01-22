import logging
import os
import pathlib
import string
import typing

import pytest


logger = logging.getLogger()


def iterate_files(files_or_dirs: typing.List[str]) -> typing.Iterable[pathlib.Path]:
    for file_or_dir in files_or_dirs:
        if os.path.isfile(file_or_dir):
            yield pathlib.Path(file_or_dir)
        elif os.path.isdir(file_or_dir):
            for dirpath, dirnames, filenames in os.walk(file_or_dir):
                for filename in filenames:
                    yield pathlib.Path(os.path.join(dirpath, filename))


def check_indent(file: pathlib.Path, indent_symbol: str, number: int) -> None:
    lineno = 0
    errors = []

    with open(file) as fh:
        while line := fh.readline():
            lineno += 1
            indent_count = 0

            for pos, char in enumerate(line):
                if char not in string.whitespace:
                    break
                if char == "\n":
                    break
                if char != indent_symbol:
                    errors.append("%s: line %d: pos %s: unexpected indentation symbol" % (file, lineno, pos))
                indent_count += 1
            if not errors and indent_count:
                if indent_count % number:
                    errors.append(
                        "%s: line %d: invalid indentation number is not multiple of %d" % (file, lineno, number)
                    )

    if errors:
        raise Exception("\n".join(errors))


def pytest_generate_tests(metafunc):
    if "file" in metafunc.fixturenames:
        metafunc.parametrize(
            "file",
            (pytest.param(item, id=str(item)) for item in iterate_files(["annet/rulebook/texts"])),
        )


def test_indent(file):
    check_indent(file, " ", 4)
