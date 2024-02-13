#!/usr/bin/env python3
# данная утилита используется для проверки
# индентации в файлах rulebook'ов

import argparse
import logging
import os
import pathlib
import string
import sys
import typing


logger = logging.getLogger()


def iterate_files(files_or_dirs: typing.List[str]) -> typing.Iterable[pathlib.Path]:
    for file_or_dir in files_or_dirs:
        if os.path.isfile(file_or_dir):
            yield pathlib.Path(file_or_dir)
        elif os.path.isdir(file_or_dir):
            for dirpath, dirnames, filenames in os.walk(file_or_dir):
                for filename in filenames:
                    yield pathlib.Path(os.path.join(dirpath, filename))


def check_indent(file: pathlib.Path, indent_symbol: str, number: int) -> True:
    lineno = 0
    ok = True
    logger.debug("Opening a file: %s", file)
    with open(file) as fh:
        while True:
            lineno += 1
            line = fh.readline()
            if not line:
                break
            indent_count = 0
            logger.debug("%s: Checking a line %d: '%s'", file, lineno, line.strip())
            for pos, char in enumerate(line):
                if char not in string.whitespace:
                    break
                if char == "\n":
                    break
                if char != indent_symbol:
                    logger.error("%s: line %d: pos %s: unexpected indentation symbol", file, lineno, pos)
                    ok = False
                indent_count += 1
            if ok and indent_count:
                if indent_count % number:
                    logger.error("%s: line %d: invalid indentation number is not multiple of %d", file, lineno, number)
                    ok = False
            logger.debug("%s: Result for a line %d: '%s'", file, lineno, "ok" if ok else "fail")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--indent", help="Режим индетации: space/tab, default: space", default="space")
    parser.add_argument("-n", "--number-of-indent", help="Сколько символов используется для индетации, default: space=4, tab=1")
    parser.add_argument("-d", "--debug", action="store_true", help="Режим отладки")
    parser.add_argument("files", nargs="+", help="Файлы или директория с файлами которые надо обработать")
    args = parser.parse_args()

    hdl = logging.StreamHandler()
    hdl.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(hdl)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    indent_symbol = None
    number_of_indent = None
    if args.indent == "space":
        indent_symbol = " "
        number_of_indent = 4
    elif args.indent == "tab":
        indent_symbol = "\t"
        number_of_indent = 1
    else:
        logger.error("Invalid --indent argument value")
        parser.print_help()
        sys.exit(-1)

    if args.number_of_indent:
        if not string.digits(args.number_of_indent):
            logger.error("Invalid --number-of-indent argument value")
            sys.exit(-1)
        number_of_indent = int(args.number_of_indent)

    retcode = 0
    for file in iterate_files(args.files):
        if not check_indent(file, indent_symbol, number_of_indent):
            retcode = 1

    sys.exit(retcode)


if __name__ == "__main__":
    main()
