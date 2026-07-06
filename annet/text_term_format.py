from collections.abc import Iterable, Mapping
from itertools import groupby
from operator import itemgetter
from typing import Any

from pygments import lex
from pygments.formatter import Formatter
from pygments.lexer import RegexLexer
from pygments.lexers import DiffLexer, YamlLexer  # pylint: disable=no-name-in-module
from pygments.token import Token, _TokenType

from .output import TextArgs


# =====
Warning = Token.Warning  # pylint: disable=redefined-builtin
Error = Token.Error

YAML_TERMINAL_COLORS = {
    Token.Literal.String: "green",
    Token.Literal.Scalar.Plain: "darkblue",
    Token.Punctuation.Indicator: "darkblue",
}

DIFF_TERMINAL_COLORS = {
    Token.Generic.Inserted: "green",
    Token.Generic.Deleted: "red",
    Token.Generic.Heading: "cyan_blue",
}

SWITCH_OUTPUT_TERMINAL_COLORS = {
    Warning: "yellow",
    Error: "red",
}


class SwitchOutputLexer(RegexLexer):
    name = "SwitchOutputLexer"
    aliases = ["switch_output_lexer"]
    tokens = {
        "root": [
            (r"[wW]arning.*\n", Warning),
            (r"Info.*\n", Warning),
            (r"[eE]rror.*\n", Error),
            (r".*\n", Token.Text),
        ]
    }


class CursesFormatter(Formatter[str]):
    def __init__(self, **options: Any) -> None:
        self.colorscheme: Mapping[_TokenType, str] = options.pop("scheme")
        Formatter.__init__(self, **options)

    def format_tokens(self, tokensource: Iterable[tuple[_TokenType, str]]) -> dict[int, list[TextArgs]]:
        res: dict[int, list[TextArgs]] = {}
        tokens = list(tokensource)
        tmp_res: dict[int, list[tuple[str | None, str]]] = {}
        line_no = 0
        for ttype, values in groupby(tokens, itemgetter(0)):
            color = self.colorscheme.get(ttype)
            for value in values:
                if line_no not in tmp_res:
                    tmp_res[line_no] = []
                if value[1].endswith("\n"):
                    if len(value[1]) > 1:
                        tmp_res[line_no].append((color, value[1].rstrip()))
                    line_no += 1
                else:
                    tmp_res[line_no].append((color, value[1]))

        for line_no, color_values in tmp_res.items():
            res[line_no] = []
            for color, grouped in groupby(color_values, itemgetter(0)):
                str_values = "".join(v[1] for v in grouped)
                res[line_no].append(TextArgs(str_values, color))
        return res


def format_yaml(txt: str) -> dict[int, list[TextArgs]]:
    return CursesFormatter(scheme=YAML_TERMINAL_COLORS).format_tokens(lex(txt, YamlLexer()))


def format_diff(txt: str) -> dict[int, list[TextArgs]]:
    return CursesFormatter(scheme=DIFF_TERMINAL_COLORS).format_tokens(lex(txt, DiffLexer()))


LEXERS = {
    "diff": (DiffLexer, DIFF_TERMINAL_COLORS),
    "yaml": (YamlLexer, YAML_TERMINAL_COLORS),
    "switch_out": (SwitchOutputLexer, SWITCH_OUTPUT_TERMINAL_COLORS),
}


def curses_format(txt: str, lexer: str) -> dict[int, list[TextArgs]]:
    return CursesFormatter(scheme=LEXERS[lexer][1]).format_tokens(lex(txt, LEXERS[lexer][0]()))
