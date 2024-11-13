import copy
import operator
import textwrap
from collections import OrderedDict as odict
from typing import (  # pylint: disable=unused-import
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

from .lib import jun_activate, merge_dicts, strip_annotation, uniq
from .rbparser import platform
from .rbparser.ordering import compile_ordering_text
from .rulebook.common import call_diff_logic
from .rulebook.common import default as common_default
from .tabparser import CommonFormatter
from .types import Diff, Op


# =====
class AclError(Exception):
    pass


class AclNotExclusiveError(AclError):
    pass


class PatchRow:
    row: str

    def __init__(self, row: str):
        self.row = row

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.row == other
        if not isinstance(other, PatchRow):
            return NotImplemented
        return self.row == other.row

    def __hash__(self) -> int:
        return hash(self.row)

    def __str__(self) -> str:
        return self.row


class PatchItem:
    row: str
    child: "Union[PatchTree, None]"
    context: Dict[str, str]

    def __init__(self, row, child, context):
        self.row = row
        self.child = child
        self.context = context

    def __str__(self):
        return (
            f"PatchItem(\n"
            f'    row="{self.row}",\n'
            f"    child={textwrap.indent(str(self.child), '    ').strip()},\n"
            f"    context={self.context}\n"
            f")"
        )


class PatchTree:
    itms: List[PatchItem]

    def __init__(self, row: Optional[str] = None):
        self.itms = []
        if row:
            self.add(row, {})

    def add(self, row: str, context: Dict[str, str]) -> None:
        self.itms.append(PatchItem(row, None, context))

    def add_block(self, row: str, subtree: "Optional[PatchTree]" = None, context: Dict[str, str] = None) -> "PatchTree":
        if subtree is None:
            subtree = PatchTree()
        if context is None:
            context = {}
        self.itms.append(PatchItem(row, subtree, context))
        return subtree

    def items(self) -> "Iterator[Tuple[str, Union[PatchTree, None]]]":
        for item in self.itms:
            yield str(item.row), item.child

    def asdict(self) -> Dict:
        ret = odict()
        for row in uniq(i.row for i in self.itms):
            subtrees = []
            for i in self.itms:
                if i.row == row and i.child is not None:
                    subtrees.append(i.child.asdict())
            if subtrees:
                ret[str(row)] = merge_dicts(*subtrees)
            else:
                ret[str(row)] = None
        return ret

    def __bool__(self):
        return bool(self.itms)

    def __str__(self):
        n = ",\n"
        itms = map(lambda x: textwrap.indent(str(x), "    "), self.itms)
        return (
            f"PatchTree(\n"
            f"    itms=[\n"
            f"{textwrap.indent(n.join(itms), '    ')}\n"
            f"    ]\n"
            f")"
        )


class Orderer:
    def __init__(self, rb, vendor):
        self.rb = rb
        self.vendor = vendor

    def ref_insert(self, ref_tracker):
        for ref, _ in reversed(ref_tracker.configs()):
            self.insert(ref)
        for _, defs in reversed(ref_tracker.configs()):
            self.insert(defs)

    def insert(self, rules):
        if isinstance(rules, dict):
            fmtr = CommonFormatter()
            rules = fmtr.join(rules)
        rules = compile_ordering_text(rules, self.vendor)
        self.rb = merge_dicts(rules, self.rb)

    def rule_weight(self, row, rule, regexp_key):
        return len(set(row).intersection(set(rule["attrs"][regexp_key].pattern))) / len(row)

    def get_order(self, row, cmd_direct):
        f_order = None
        f_weight = 0
        f_rule = ""
        children = []
        ordering = self.rb
        block_exit = platform.VENDOR_EXIT[self.vendor]

        for (order, (raw_rule, rule)) in enumerate(ordering.items()):
            direct_matched = bool(rule["attrs"]["direct_regexp"].match(row))
            if not rule["attrs"]["order_reverse"] and (direct_matched or rule["attrs"]["reverse_regexp"].match(row)):
                # если не указано order_reverse - правило считается прямым
                regexp_key = ("direct_regexp" if direct_matched else "reverse_regexp")
                weight = self.rule_weight(row, rule, regexp_key)
                if f_order is None or f_weight < weight:
                    f_order = order
                    f_weight = weight
                    f_rule = (raw_rule, rule["attrs"][regexp_key])
                children.extend(ordering[raw_rule]["children"].items())

            elif rule["attrs"]["order_reverse"] and not cmd_direct and direct_matched:
                weight = self.rule_weight(row, rule, "direct_regexp")
                if f_order is None or f_weight < weight or (f_weight == weight and not cmd_direct):
                    f_order = order
                    f_weight = weight
                    f_rule = (raw_rule, rule["attrs"]["direct_regexp"])
                    cmd_direct = True
                children = []

            elif block_exit and block_exit == row:
                f_order = float("inf")
                f_rule = (raw_rule, block_exit)
                cmd_direct = True
                children = []

        return (f_order or 0), cmd_direct, odict(children), f_rule

    def order_config(self, config):
        if self.vendor not in platform.VENDOR_REVERSES:
            return config

        ordered = []
        reverse_prefix = platform.VENDOR_REVERSES[self.vendor]
        if not config:
            return odict()
        for (row, children) in config.items():
            cmd_direct = not row.startswith(reverse_prefix)
            (order, direct, rb, _) = self.get_order(row, cmd_direct)
            child_orderer = Orderer(rb, self.vendor)
            children = child_orderer.order_config(children)
            ordered.append({
                "row": row,
                "children": children,
                "direct": direct,
                "order": order,
            })

        return odict(
            (item["row"], item["children"])
            for item in sorted(ordered, key=(lambda item: (
                (item["order"] if item["direct"] else -item["order"]),
                item["direct"],
            )))
        )


# =====
def apply_acl(config, rules, fatal_acl=False, exclusive=False, with_annotations=False, _path=()):
    passed = odict()
    for (row, children) in config.items():
        if with_annotations:
            # do not pass annotations through ACL
            test_row = strip_annotation(row)
        else:
            test_row = row
        try:
            (match, children_rules) = match_row_to_acl(test_row, rules, exclusive)
        except AclNotExclusiveError as err:
            raise AclNotExclusiveError("'%s', %s" % ("/ ".join(_path + (row,)), err))
        if match:
            if not (match["is_reverse"] and all(match["attrs"]["cant_delete"])):
                passed[row] = apply_acl(
                    config=children,
                    rules=children_rules,
                    fatal_acl=fatal_acl,
                    exclusive=exclusive,
                    with_annotations=with_annotations,
                    _path=_path + (row,)
                )
        elif fatal_acl:
            raise AclError(" / ".join(_path + (row,)))
    return passed


def apply_acl_diff(diff, rules):
    passed = []
    for (op, row, children, d_match) in diff:
        (match, children_rules) = match_row_to_acl(row, rules)
        if match:
            if op == Op.REMOVED and all(match["attrs"]["cant_delete"]):
                op = Op.AFFECTED
            children = apply_acl_diff(children, children_rules)
            passed.append((op, row, children, d_match))
    return passed


def mark_unchanged(diff):
    passed = []
    for (op, row, children, d_match) in diff:
        if op == Op.AFFECTED:
            children = mark_unchanged(children)
            if all(x[0] == Op.UNCHANGED for x in children):
                op = Op.UNCHANGED
        passed.append((op, row, children, d_match))
    return passed


def strip_unchanged(diff):
    passed = []
    for (op, row, children, d_match) in diff:
        if op == Op.UNCHANGED:
            continue
        children = strip_unchanged(children)
        passed.append((op, row, children, d_match))
    return passed


def make_diff(old, new, rb, acl_rules_list) -> Diff:
    # не позволяем logic-коду модифицировать конфиг
    old = copy.deepcopy(old)
    new = copy.deepcopy(new)
    diff_pre = apply_diff_rb(old, new, rb)
    diff = call_diff_logic(diff_pre, old, new)
    for acl_rules in acl_rules_list:
        if acl_rules is not None:
            diff = apply_acl_diff(diff, acl_rules)
    diff = mark_unchanged(diff)
    return diff


def apply_diff_rb(old, new, rb):
    """ Diff pre is a odict {(key, diff_logic): {}} """
    diff_pre = odict()
    for row in list(uniq(old, new)):
        (match, children_rules) = _match_row_to_rules(row, rb["patching"])
        if match:
            diff_pre[row] = {
                "match": match,
                "subtree": apply_diff_rb(
                    old.get(row, odict()),
                    new.get(row, odict()),
                    rb={"patching": children_rules},  # Нужен только кусок, касающийся правил для патчей
                ),
            }
        else:
            old.pop(row, None)
            new.pop(row, None)
    return diff_pre


def make_pre(diff: Diff, _parent_match=None) -> Dict[str, Any]:
    pre = odict()
    for (op, row, children, match) in diff:
        if _parent_match and _parent_match["attrs"]["multiline"]:
            # Если родительское правило было мультилайном, то все внутренности станут его контентом.
            # Это значит, что к ним будет принудительно применяться common.default() и фейковое
            # правило __MULTILINE_BODY__.
            match = {
                "raw_rule": "__MULTILINE_BODY__",
                "key": row,
                "attrs": {
                    "comment": [],
                    "logic": common_default,  # Прекрасно работает с мультилайнами и обрезанным правилом
                    "multiline": True,
                    "context": _parent_match["attrs"]["context"],
                }
            }
        raw_rule = match["raw_rule"]
        key = match["key"]

        if raw_rule not in pre:
            pre[raw_rule] = {
                "attrs": match["attrs"],
                "items": odict(),
            }
        if key not in pre[raw_rule]["items"]:
            pre[raw_rule]["items"][key] = {
                Op.ADDED: [],
                Op.REMOVED: [],
                Op.MOVED: [],
                Op.AFFECTED: [],
                Op.UNCHANGED: [],
            }

        pre[raw_rule]["items"][key][op].append({
            "row": row,
            "children": make_pre(
                diff=children,
                _parent_match=match,
            ),
        })
    return pre


_comment_macros = {
    "!!HYES!!": "!!question!![Y/N]!!answer!!Y!! !!question!![y/n]!!answer!!Y!! !!question!![Yes/All/No/Cancel]!!answer!!Y!!"
}


def make_patch(pre, rb, hw, add_comments, orderer=None, _root_pre=None, do_commit=True):
    patch = []
    if not orderer:
        orderer = Orderer(rb["ordering"], hw.vendor)

    for (raw_rule, content) in pre.items():
        for (key, diff) in content["items"].items():
            # чтобы logic не мог поменять атрибуты
            rule_pre = content.copy()
            attrs = rule_pre["attrs"].copy()

            iterable = attrs["logic"](
                rule=attrs,
                key=key,
                diff=diff,
                hw=hw,
                rule_pre=rule_pre,
                root_pre=(_root_pre or pre),
            )
            for (direct, row, sub_pre) in iterable:
                if direct is not None:
                    patch_row = row
                    if add_comments:
                        comments = " ".join(attrs["comment"])
                        for (macro, m_value) in _comment_macros.items():
                            comments = comments.replace(macro, m_value)
                        if comments:
                            patch_row = "%s %s" % (row, comments)

                    # pylint: disable=unused-variable
                    (order, order_direct, ordering, order_rule) = orderer.get_order(row, direct)
                    fmt_row = patch_row
                    # fmt_row += "  # %s" % str(order_rule)  # uncomment to debug ordering

                    if not do_commit and attrs.get("force_commit", False):
                        # if do_commit is false skip patch that couldn't be applied without commit
                        continue

                    patch.append({
                        "row": fmt_row,
                        "children": (PatchTree() if not sub_pre else make_patch(
                            pre=sub_pre,
                            rb={"ordering": ordering},  # Нужен только кусок, касающийся правил для ордеринга
                            hw=hw,
                            add_comments=add_comments,
                            _root_pre=(_root_pre or pre),
                            do_commit=do_commit,
                        )),
                        "raw_rule": raw_rule,
                        "direct": direct,
                        "order": order,
                        "order_direct": order_direct,
                        "parent": attrs.get("parent", False),
                        "force_commit": attrs.get("force_commit", False),
                        "ignore_case": attrs.get("ignore_case", False),
                        "context": attrs["context"],
                    })
    tree = PatchTree()
    sorted_patch = sorted(patch, key=(lambda item: (
        (item["order"] if item["order_direct"] else -item["order"]),
        item["raw_rule"],
        item["order_direct"],
    )))
    for item in sorted_patch:
        if (not item["children"] and not item["parent"]) or not item["direct"]:
            tree.add(item["row"], item["context"])
        else:
            tree.add_block(item["row"], item["children"], item["context"])
        if item["force_commit"]:
            tree.add("commit", item["context"])
    return tree


def match_row_to_acl(row, rules, exclusive=False):
    matches = _find_acl_matches(row, rules)
    if matches:
        if exclusive:
            gen_cant_delete = {}
            for match in matches:
                names = match[0][0]["attrs"]["generator_names"]
                flags = match[0][0]["attrs"]["cant_delete"]
                for name, flag in zip(names, flags):
                    if name not in gen_cant_delete:
                        gen_cant_delete[name] = flag
                    else:
                        gen_cant_delete[name] &= flag
            can_delete = {name: flag for name, flag in gen_cant_delete.items() if not flag}
            if len(can_delete) > 1:
                generator_names = ", ".join(can_delete.keys())
                raise AclNotExclusiveError("generators: '%s'" % generator_names)
        return _select_match(matches, rules)
    return (None, None)  # (match, children_rules)


def _match_row_to_rules(row, rules):
    matches = _find_rules_matches(row, rules)
    if matches:
        return _select_match(matches, rules)
    return (None, None)


def _find_acl_matches(row, rules):
    res = []
    for regexp_key in ["direct_regexp", "reverse_regexp"]:
        for ((_, rule), is_global) in _rules_local_global(rules):
            row_to_match = _normalize_row_for_acl(row, rule)
            match = rule["attrs"][regexp_key].match(row_to_match)
            if match:
                rule["attrs"]["match"] = match.groupdict()
                # FIXME: сейчас у нас вообще не используется тип ignore, но он иногда встречается в ACL.
                # Проблема в том, что ACL мержится, и игноры все ломают. Надо придумать, что с этим сделать.
                # В данный момент ignore acl работает только в filter-acl, так как он целостный и накладывается независимо
                # В этом случае ignore правила так же матчатся и считается их специфичность на ряду с normal
                # при выборе ignore правила, заматченная строка не будет пропущена
                metric = (
                    rule["attrs"]["prio"],
                    # Calculate how specific matched regex is for the row
                    # based on how many symbols they share
                    len(set(row).intersection(set(rule["attrs"][regexp_key].pattern))) / len(row),
                )
                item = (
                    metric,
                    ((rule, (not is_global and regexp_key == "direct_regexp" and rule["type"] != "ignore")),
                     #       ^^^ is_cr_allowed ^^^    cr == children rules
                     {"is_reverse": (regexp_key == "reverse_regexp")}),
                    # ^^^ is_reverse ^^^
                )
                res.append(item)
    res.sort(key=operator.itemgetter(0), reverse=True)
    return [item[1] for item in res]


def _find_rules_matches(row, rules):
    matches = []
    for ((raw_rule, rule), is_global) in _rules_local_global(rules):
        match = rule["attrs"]["regexp"].match(row)
        if match:
            if rule["type"] == "ignore":
                return []
            matches.append(((rule, (not is_global)), {"raw_rule": raw_rule, "key": match.groups()}))
            #                       ^^^ is_cr_allowed
    return matches


def _select_match(matches, rules):
    ((f_rule, is_f_cr_allowed), f_other) = matches[0]  # f == first
    if f_rule["type"] == "ignore":
        # В данный момент эта ветка достижима только в filter-acl
        return (None, None)

    # Мерджим всех потомков которые заматчились
    local_children = odict()
    global_children = odict()
    if is_f_cr_allowed:
        for (rule, is_cr_allowed) in map(operator.itemgetter(0), matches):
            if is_cr_allowed:
                local_children = merge_dicts(local_children, rule["children"]["local"])
            # optional break on is_cr_allowed==False?

                global_children = merge_dicts(global_children, rule["children"]["global"])

    global_children = merge_dicts(global_children, rules["global"])

    children_rules = {
        "local": local_children,
        "global": global_children,
    }

    match = {"attrs": f_rule["attrs"]}
    match.update(f_other)
    return (match, children_rules)


def _rules_local_global(rules):
    for (raw_rule, rule) in rules["local"].items():
        yield ((raw_rule, rule), False)
    for (raw_rule, rule) in rules["global"].items():
        yield ((raw_rule, rule), True)


def _normalize_row_for_acl(row, rule):
    # NOCDEV-5940 У джуниперов есть служебрая разметка "inactive:"
    if rule["attrs"]["vendor"] == "juniper":
        row = jun_activate(row)
    return row
