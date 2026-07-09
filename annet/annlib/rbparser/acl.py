import functools
from collections import OrderedDict as odict
from typing import Any, Callable, List, Optional, TypeVar, cast

from valkit import add_validator_magic as _add_validator_magic
from valkit.common import valid_bool, valid_number, valid_string_list

from annet.vendors import registry_connector

from . import syntax


_F = TypeVar("_F", bound=Callable[..., Any])
# valkit's decorator is untyped; treat it as signature-preserving so decorated validators stay typed.
add_validator_magic = cast("Callable[[_F], _F]", _add_validator_magic)


# =====
@functools.lru_cache()
def compile_acl_text(text: str, vendor: str, allow_ignore: bool = False) -> dict[str, odict[Any, Any]]:
    return _compile_acl(
        trees=[syntax.parse_text(text, _PARAMS_SCHEME)],
        reverse_prefix=registry_connector.get()[vendor].reverse,
        allow_ignore=allow_ignore,
        vendor=vendor,
    )


@functools.lru_cache()
def compile_ref_acl_text(text: str) -> dict[str, odict[Any, Any]]:
    return _compile_acl(
        trees=[syntax.parse_text(text, _PARAMS_SCHEME)],
        reverse_prefix="",
        allow_ignore=False,
    )


@add_validator_magic
def valid_bool_list(
    arg: Any,
    delim: str = r"[,\t ]+",
    subval: Optional[Callable[[Any], Any]] = None,
    strip: bool = False,
) -> List[bool]:
    arg = valid_string_list(arg, delim, subval, strip)
    result: List[bool] = [valid_bool(x, strip) for x in arg]
    return result


# =====
_PARAMS_SCHEME = {
    "global": {
        "validator": valid_bool,
        "default": False,
        "uniter": (lambda a, b: a or b),
    },
    "cant_delete": {
        "validator": valid_bool_list,
        "default": (lambda raw_rule: [raw_rule.startswith("interface")]),  # FIXME: ужас какой
        "uniter": (lambda a, b: a + b),
    },
    "prio": {
        "validator": (lambda s: valid_number(s, min=0, type=int)),
        "default": 0,
        "uniter": max,
    },
    "generator_names": {"validator": valid_string_list, "default": [], "uniter": (lambda a, b: a + b)},
}


# =====
def _compile_acl(
    trees: list[odict[Any, Any]],
    reverse_prefix: str,
    allow_ignore: bool = False,
    vendor: str = "",
) -> dict[str, odict[Any, Any]]:
    rules: dict[str, odict[Any, Any]] = {"local": odict(), "global": odict()}
    for rule_id, attrs in _merge_toplevel(trees).items():
        if attrs["type"] == "ignore" and not allow_ignore:
            raise NotImplementedError("ACL does not support ignore-rules")
        rule = {
            "type": attrs["type"],
            "attrs": {
                "direct_regexp": syntax.compile_row_regexp(attrs["row"]),
                "reverse_regexp": syntax.compile_row_regexp(_make_reverse(attrs["row"], reverse_prefix)),
                "cant_delete": attrs["params"]["cant_delete"],
                "prio": attrs["params"]["prio"],
                "generator_names": attrs["params"]["generator_names"],
                "vendor": vendor,
                "context": attrs["context"],
            },
            "children": None,
        }
        if not attrs["params"]["global"] and not attrs["type"] == "ignore":
            rule["children"] = _compile_acl(attrs["children"], reverse_prefix, allow_ignore, vendor)
        rules["global" if attrs["params"]["global"] else "local"][rule_id] = rule
    return rules


def _merge_toplevel(trees: list[odict[Any, Any]]) -> odict[Any, Any]:
    merged: odict[Any, Any] = odict()
    for tree in trees:
        for attrs in tree.values():
            rule_id = ("!" if attrs["type"] == "ignore" else "") + attrs["row"]
            if rule_id not in merged:
                merged[rule_id] = attrs
                merged[rule_id]["children"] = [attrs["children"]] if attrs["children"] else []
                continue

            for key, value in attrs["params"].items():
                if key in merged[rule_id]["params"]:
                    uniter = _PARAMS_SCHEME[key]["uniter"]
                    merged[rule_id]["params"][key] = uniter(merged[rule_id]["params"][key], value)
                else:
                    merged[rule_id]["params"][key] = value

            if attrs["children"]:
                merged[rule_id]["children"].append(attrs["children"])
    return merged


@functools.lru_cache()
def _make_reverse(row: str, reverse_prefix: str) -> str:
    if row.startswith(reverse_prefix + " "):
        return row[len(reverse_prefix + " ") :]
    else:
        return "%s %s" % (reverse_prefix, row)
