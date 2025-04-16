import functools
import re
from collections import OrderedDict as odict

from valkit.common import valid_bool, valid_string_list

from annet.vendors import registry_connector
from . import syntax


# =====
@functools.lru_cache()
def compile_ordering_text(text, vendor):
    return _compile_ordering(
        tree=syntax.parse_text(text, params_scheme={
            "order_reverse": {
                "validator": valid_bool,
                "default":   False,
            },
            "global": {
                "validator": valid_bool,
                "default": False,
            },
            "scope": {
                "validator": valid_string_list,
                "default": None,
            }
        }),
        reverse_prefix=registry_connector.get()[vendor].reverse,
    )


def decompile_ordering_rulebook(rb) -> str:
    def _decompile_ordering_text(rb, level):
        indent = "  "
        for attrs in rb.values():
            yield indent * level + attrs["attrs"]["raw_rule"]
            yield from _decompile_ordering_text(attrs["children"], level + 1)
    return "\n".join(_decompile_ordering_text(rb, 0))


# =====
def _compile_ordering(tree, reverse_prefix):
    ordering = odict()
    for (rule_id, attrs) in tree.items():
        if attrs["type"] == "normal":
            ordering[rule_id] = {
                "attrs": {
                    "direct_regexp": syntax.compile_row_regexp(attrs["row"]),
                    "reverse_regexp": (
                        syntax.compile_row_regexp(reverse_prefix + " " + attrs["row"])
                        if not attrs["row"].startswith(reverse_prefix + " ") else
                        syntax.compile_row_regexp(re.sub(r"^%s\s+" % (reverse_prefix), "", attrs["row"]))
                    ),
                    "order_reverse": attrs["params"]["order_reverse"],
                    "global": attrs["params"]["global"],
                    "scope": attrs["params"]["scope"],
                    "raw_rule": attrs["raw_rule"],
                    "context": attrs["context"],
                },
                "children": _compile_ordering(attrs["children"], reverse_prefix),
            }
    return ordering
