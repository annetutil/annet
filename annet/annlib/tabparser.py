import dataclasses
import itertools
import re
from collections import OrderedDict as odict
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Tuple, Union

from .types import Op

if TYPE_CHECKING:
    from .patching import PatchTree


# =====
class ParserError(Exception):
    pass


# =====
class _CommentOrEmpty:
    pass


class BlockBegin:
    pass


class BlockEnd:
    pass


RowWithContext = Tuple[str, Optional[Dict[str, Any]]]


def block_wrapper(value: Any) -> Iterable[Any]:
    yield from iter((BlockBegin, value, BlockEnd))


@dataclasses.dataclass
class FormatterContext:
    parent: Optional["FormatterContext"] = None

    prev: Optional[RowWithContext] = None
    current: Optional[RowWithContext] = None
    next: Optional[RowWithContext] = None

    @property
    def level(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.level + 1

    @property
    def row_prev(self) -> Optional[str]:
        return self.prev and self.prev[0]

    @property
    def row(self) -> Optional[str]:
        return self.current and self.current[0]

    @property
    def row_next(self) -> Optional[str]:
        return self.next and self.next[0]


# =====
class CommonFormatter:
    def __init__(self, indent="  "):
        self._indent = indent
        self._block_begin = ""
        self._block_end = ""
        self._statement_end = ""

    def split(self, text):
        return list(filter(None, text.split("\n")))

    def join(self, config):
        return "\n".join(
            _filtered_block_marks(
                self._indent_blocks(self._blocks(config, is_patch=False))
            )
        )

    def diff_generator(self, diff):
        yield from self._diff_lines(diff)

    def diff(self, diff):
        return list(self.diff_generator(diff))

    def patch(self, patch):
        return "\n".join(
            _filtered_block_marks(
                self._indent_blocks(self._blocks(patch, is_patch=True))
            )
        )

    def cmd_paths(self, patch):
        ret = odict()
        path = []
        for row, context in self.blocks_and_context(patch, is_patch=True):
            if row is BlockBegin:
                path.append(path[-1])
            elif row is BlockEnd:
                path.pop()
            else:
                if path:
                    path.pop()
                path.append(row)
                ret[tuple(path)] = context
        return ret

    def patch_plain(self, patch):
        return list(self.cmd_paths(patch).keys())

    def _diff_lines(self, diff, _level=0, _block_sign=None):
        sign_map = {
            Op.REMOVED: "-",
            Op.ADDED: "+",
            Op.MOVED: ">",
            Op.AFFECTED: " ",
        }
        for (flag, row, children, _) in diff:
            sign = sign_map[flag]
            if not children:
                yield "%s %s%s" % (sign, self._indent * _level, row + self._statement_end)
            else:
                yield "%s %s%s" % (sign, self._indent * _level, row + self._block_begin)
                yield from self._diff_lines(children, _level + 1, sign)
        if _level > 0 and self._block_end and _block_sign is not None:
            yield "%s %s%s" % (_block_sign, self._indent * (_level - 1), self._block_end)

    def _indented_blocks(self, tree):
        return self._indent_blocks(self._blocks(tree, False))

    def _indent_blocks(self, blocks):
        _level = 0
        for row in blocks:
            if row is BlockBegin:
                _level += 1
            elif row is BlockEnd:
                _level -= 1
            else:
                row = self._indent * _level + row
            yield row

    def blocks_and_context(
        self,
        tree: "PatchTree",
        is_patch: bool,
        context: Optional[FormatterContext] = None
    ):
        if context is None:
            context = FormatterContext()

        if is_patch:
            items = [(item.row, item.child, item.context) for item in tree.itms]
        else:
            items = [(row, child, {}) for row, child in tree.items()]

        n = len(items)
        for i in range(n):
            prev_row, prev_sub_config, prev_row_context = items[i - 1] if i > 0 else (None, None, None)
            row, sub_config, row_context = items[i]
            next_row, next_sub_config, next_row_context = items[i + 1] if i + 1 < n else (None, None, None)

            context.current = (row, row_context)
            context.prev = (prev_row, prev_row_context) if prev_row else None
            context.next = (next_row, next_row_context) if next_row else None

            yield row, row_context

            if sub_config or (is_patch and sub_config is not None):
                yield BlockBegin, None
                yield from self.blocks_and_context(
                    sub_config, is_patch, context=FormatterContext(parent=context)
                )
                yield BlockEnd, None

    def _blocks(self, tree, is_patch):
        for row, _context in self.blocks_and_context(tree, is_patch):
            yield row


class BlockExitFormatter(CommonFormatter):
    def __init__(self, block_exit, no_block_exit=(), indent="  "):
        super().__init__(indent)
        self._block_exit = block_exit
        self._no_block_exit = tuple(no_block_exit)

    def split_remove_spaces(self, text):
        # эта регулярка заменяет 2 и более пробела на один, но оставляет пробелы в начале линии
        text = re.sub(r"(?<=\S)\ {2,}(?=\S)", " ", text)
        res = super().split(text)
        return res

    def block_exit(self, context: Optional[FormatterContext]) -> Iterable[Any]:
        current = context and context.row
        if current and not current.startswith(self._no_block_exit):
            yield from block_wrapper(self._block_exit)

    def blocks_and_context(self, tree, is_patch, context: Optional[FormatterContext] = None):
        if context is None:
            context = FormatterContext()

        level = context.level
        block_level = level

        last_row_context = {}
        for row, row_context in super().blocks_and_context(tree, is_patch, context=context):
            yield row, row_context
            if row_context is not None:
                last_row_context = row_context

            if row is BlockBegin:
                block_level += 1
            elif row is BlockEnd:
                block_level -= 1

            if row is BlockEnd and block_level == level and is_patch:
                for exit_statement in filter(None, self.block_exit(context)):
                    yield exit_statement, last_row_context


class HuaweiFormatter(BlockExitFormatter):
    def __init__(self, indent="  "):
        super().__init__(
            block_exit="quit",
            no_block_exit=[
                "rsa peer-public-key",
                "dsa peer-public-key",
                "public-key-code begin",
            ],
            indent=indent,
        )

    def split(self, text):
        # на старых прошивка наблюдается баг с двумя пробелами в этом месте в конфиге
        # например на VRP V100R006C00SPC500 + V100R006SPH003
        policy_end_blocks = ("end-list", "endif", "end-filter")
        tree = self.split_remove_spaces(text)
        tree[:] = filter(lambda x: not str(x).strip().startswith(policy_end_blocks), tree)
        return tree

    def block_exit(self, context: Optional[FormatterContext]):
        row = context and context.row or ""
        row_next = context and context.row_next
        parent_row = context and context.parent and context.parent.row or ""

        if row.startswith("xpl route-filter"):
            yield from block_wrapper("end-filter")
            return

        if row.startswith("xpl"):
            yield from block_wrapper("end-list")
            return

        if parent_row.startswith("xpl route-filter"):
            if (row.startswith(("if", "elseif")) and row.endswith("then")) and not row_next:
                yield "endif"
            elif row == "else":
                yield "endif"
            return

        yield from super().block_exit(context)


class OptixtransFormatter(CommonFormatter):
    pass


class CiscoFormatter(BlockExitFormatter):
    def __init__(self, indent="  "):
        super().__init__("exit", indent)

    def split(self, text):
        return self.split_remove_spaces(text)


class AsrFormatter(BlockExitFormatter):
    def __init__(self, indent="  "):
        super().__init__("exit", indent)

    def split(self, text):
        policy_end_blocks = ("end-set", "endif", "end-policy")
        tree = self.split_remove_spaces(text)
        tree[:] = filter(lambda x: not x.endswith(policy_end_blocks), tree)
        return tree

    def block_exit(self, context: Optional[FormatterContext]) -> str:
        current = context and context.row or ""

        if current.startswith(("prefix-set", "as-path-set", "community-set")):
            yield from block_wrapper("end-set")
        elif current.startswith("if") and current.endswith("then"):
            yield from block_wrapper("endif")
        elif current.startswith("route-policy"):
            yield from block_wrapper("end-policy")
        else:
            yield from super().block_exit(context)


class JuniperFormatter(CommonFormatter):
    patch_set_prefix = "set "

    def __init__(self, indent="    "):
        super().__init__(indent)
        self._block_begin = " {"
        self._block_end = "}"
        self._statement_end = ";"
        self._endofline_comment = "; ##"

    def split(self, text):
        sub_regexs = (
            (re.compile(self._block_begin + r"\s*" + self._block_end + r"$"), ""),  # collapse empty blocks
            (re.compile(self._block_begin + "(\t# .+)?$"), ""),
            (re.compile(self._statement_end + r"$"), ""),
            (re.compile(r"\s*" + self._block_end + "(\t# .+)?$"), ""),
            (re.compile(self._endofline_comment + r".*$"), ""),
        )
        split = []
        for line in text.split("\n"):
            for (regex, repl_line) in sub_regexs:
                line = regex.sub(repl_line, line)
            split.append(line)
        return list(filter(None, split))

    def join(self, config):
        return "\n".join(_filtered_block_marks(self._formatted_blocks(self._indented_blocks(config))))

    def patch(self, patch):
        return "\n".join(" ".join(x) for x in self.cmd_paths(patch))

    def patch_plain(self, patch):
        return list(self.cmd_paths(patch).keys())

    def _formatted_blocks(self, blocks):
        level = 0
        line = None
        for new_line in blocks:
            if new_line is BlockBegin:
                level += 1
                if isinstance(line, str):
                    yield line + self._block_begin
            elif new_line is BlockEnd:
                level -= 1
                if isinstance(line, str):
                    yield line + self._statement_end
                yield self._indent * level + self._block_end
            elif isinstance(line, str):
                yield line + self._statement_end
            line = new_line
        if isinstance(line, str):
            yield line + self._statement_end

    def cmd_paths(self, patch, _prev=""):
        commands = odict()
        for item in patch.itms:
            key, childs, context = item.row, item.child, item.context
            if childs:
                for k, v in self.cmd_paths(childs, _prev + " " + key).items():
                    commands[k] = v
            else:
                if key.startswith("delete"):
                    cmd = "delete" + _prev + " " + key.replace("delete", "", 1).strip()
                elif key.startswith("activate"):
                    cmd = "activate" + _prev + " " + key.replace("activate", "", 1).strip()
                elif key.startswith("deactivate"):
                    cmd = "deactivate" + _prev + " " + key.replace("deactivate", "", 1).strip()
                else:
                    cmd = (self.patch_set_prefix + _prev.strip()).strip() + " " + key
                # Expanding [ a b c ] junipers list of arguments
                matches = re.search(r"^(.*)\s+\[(.+)\]$", cmd)
                if matches:
                    for c in matches.group(2).split(" "):
                        if c.strip():
                            cmd = " ".join([matches.group(1), c])
                            commands[(cmd,)] = context
                else:
                    commands[(cmd,)] = context

        return commands


class RibbonFormatter(JuniperFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._endofline_comment = "; # SECRET-DATA"


class JuniperList:
    """
    Форматирует inline-листы в конфиге juniper
    """

    def __init__(self, *args, spaces=True, **kwargs):
        self._items = list(*args, **kwargs)
        self.spaces = spaces

    def __str__(self):
        if self.spaces:
            return "[ %s ]" % " ".join(str(_) for _ in self._items)
        else:
            return "[%s]" % " ".join(str(_) for _ in self._items)


class NokiaFormatter(JuniperFormatter):
    patch_set_prefix = "/configure "

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._statement_end = ""
        self._endofline_comment = " ##"

    def split(self, text):
        ret = super().split(text)
        # NOCDEVDUTY-248 сдергиваем верхний configure-блок
        # NOCDEVDUTY-282 после configure {} блока могут идти еще блоки которые нам не нужны
        start, finish = None, None
        for i, line in enumerate(ret):
            if line.startswith("#"):
                continue
            # начало configure-блока
            if line == "configure":
                start = i + 1
            # любой после configure последующий блок на глобальном уровне
            elif len(line) == len(line.lstrip()):
                if start is not None and finish is None:
                    finish = i
        # Если configure-блока не было - то весь конфиг считаем configre'ом
        start = start if start is not None else 0
        finish = finish if finish is not None else len(ret)
        return ret[start:finish]

    def cmd_paths(self, patch, _prev=""):
        commands = odict()
        for item in patch.itms:
            key, childs, context = item.row, item.child, item.context
            if childs:
                for k, v in self.cmd_paths(childs, _prev + " " + key).items():
                    commands[k] = v
            else:
                if key.startswith("delete"):
                    cmd = "/configure delete" + _prev + " " + key.replace("delete", "", 1).strip()
                else:
                    cmd = self.patch_set_prefix + _prev.strip() + " " + key
                # Expanding [ a b c ] junipers list of arguments
                matches = re.search(r"^(.*)\s+\[(.+)\]$", cmd)
                if matches:
                    for c in matches.group(2).split(" "):
                        if c.strip():
                            cmd = " ".join([matches.group(1), c])
                            commands[(cmd,)] = context
                else:
                    commands[(cmd,)] = context
        return commands


class RosFormatter(CommonFormatter):
    patch_set_prefix = "set "

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._block_begin = "/"

    def join(self, config):
        return "\n".join(_filtered_block_marks(self._formatted_blocks(self._indented_blocks(config))))

    def patch(self, patch):
        return "\n".join(" ".join(x) for x in self.cmd_paths(patch))

    def patch_plain(self, patch):
        return list(self.cmd_paths(patch).keys())

    def blocks_and_context(
        self,
        tree: "PatchTree",
        is_patch: bool,
        context: Optional[FormatterContext] = None
    ):
        rows = []

        if is_patch:
            items = ((item.row, item.child, item.context) for item in tree.itms)
        else:
            items = ((row, child, {}) for row, child in tree.items())

        for row, sub_config, row_context in items:
            if sub_config or (is_patch and sub_config is not None):
                rows.append((row, sub_config, row_context))
            else:
                rows.append((row, None, row_context))

        prev_prow = None
        prev_prow_context = {}
        for sub_config, row_group in itertools.groupby(rows, lambda x: x[1]):
            if sub_config is None:
                if prev_prow:
                    yield prev_prow, prev_prow_context
                    yield BlockBegin, None
                for row, _, row_context in row_group:
                    yield row, row_context
                if prev_prow:
                    yield BlockEnd, None
            else:
                for row, _, row_context in row_group:
                    if context and context.parent and context.parent.row:
                        prev_prow, prev_prow_context = context.parent.current
                        prow = f"{context.parent.row} {row}"
                    else:
                        prow = row
                    yield prow, row_context

                    yield BlockBegin, None
                    yield from self.blocks_and_context(
                        sub_config,
                        is_patch,
                        context=FormatterContext(parent=context, current=(prow, row_context))
                    )
                    yield BlockEnd, None

    def _formatted_blocks(self, blocks):
        line = None
        for new_line in blocks:
            if new_line is BlockBegin:
                if isinstance(line, str):
                    yield self._block_begin + line.strip()
            elif isinstance(line, str):
                yield line
            line = new_line

    def _splitter_file(self, lines):
        filedesrc_re = re.compile(r"^\s+(?P<num>\d+)\s+name=\"(?P<name>[^\"]+)\"\s+type=\"(?P<type>[^\"]+)\""
                                  r"\s+(size=(?P<size>.*))?creation-time=(?P<time>.*?)(contents=(?P<content>.*)?)?$")
        file_content_indent = re.compile(r"^\s{5}")
        out = []
        files = {}
        curfile = None
        for line in lines:
            match = filedesrc_re.search(line)
            if match:
                if match.group("type").strip() == ".txt file":
                    curfile = match.group("name")
                    files[curfile] = {"name": curfile, "contents": []}
                    if match.group("content"):
                        files[curfile]["contents"].append(match.group("content").strip())
            elif curfile and file_content_indent.match(line):
                files[curfile]["contents"].append(file_content_indent.sub("", line))
        for file in files.values():
            out.append(f"print file={file['name']}")
            if len(file["contents"]) > 0:
                text = "\n".join(file["contents"])
                out.append(f"set {file['name']} contents=\"{text}\"")
        return out

    def _splitter_user_ssh_keys(self, lines):
        keydescr_re = re.compile(r"user=(?P<user>\w+).*key-owner=(?P<owner>.*)$")
        out = []
        for line in lines:
            match = keydescr_re.search(line)
            if match:
                out.append(f"import public-key-file={match.group('owner')}.ssh_key.txt user={match.group('user')}")

        return out

    def split(self, text):
        split = []
        level = 0
        postj = {}
        curgroup = None
        for line in text.split("\n"):
            if line.startswith("/"):
                if curgroup:
                    for row in getattr(self, curgroup)(postj[curgroup]):
                        if level > 0:
                            row = row.strip()
                        split.append(self._indent * level + row)

                level = 0
                for group in line.split():
                    split.append(self._indent * level + group.replace("/", ""))
                    level += 1

                gpath = line.replace("/", "_splitter_").replace(" ", "_").replace("-", "_")
                if hasattr(self, gpath):
                    postj[gpath] = []
                    curgroup = gpath
                else:
                    curgroup = None
            else:
                row = line
                if curgroup:
                    postj[curgroup].append(row)
                else:
                    if level > 0:
                        row = line.strip()
                    split.append(self._indent * level + row)
        if curgroup:
            for row in getattr(self, curgroup)(postj[curgroup]):
                if level > 0:
                    row = row.strip()
                split.append(self._indent * level + row)
        return list(filter(None, split))

    def cmd_paths(self, patch, _prev=""):
        rm_regexs = (
            (re.compile(r"^add "), ""),
            (re.compile(r"^print file="), "name="),
        )
        patch_items = []
        for item in patch.itms:
            key, childs, context = item.row, item.child, item.context
            if childs:
                patch_items.append((key, childs, context))
            else:
                patch_items.append((key, None, context))

        commands = odict()
        prev_cmd = None
        prev_context = None
        for childs, items in itertools.groupby(patch_items, lambda x: x[1]):
            if childs is None:
                if prev_cmd:
                    commands[(prev_cmd,)] = prev_context
                for key, _, context in items:
                    if key.startswith("remove"):
                        find_cmd = key.replace("remove", "", 1).strip()
                        for (regex, repl_line) in rm_regexs:
                            find_cmd = regex.sub(repl_line, find_cmd)
                        cmd = "remove [ find " + find_cmd + " ]"
                    else:
                        cmd = key
                    commands[(cmd,)] = context
            else:
                for key, _, context in items:
                    if _prev:
                        prev_cmd = _prev
                        prev_context = context
                        block_cmd = f"{_prev} {key}"
                    else:
                        block_cmd = f"/{key}"
                    commands[(block_cmd,)] = context
                    for k, v in self.cmd_paths(childs, block_cmd).items():
                        commands[k] = v
        return commands


def make_formatter(vendor, **kwargs):
    formatters = {
        "juniper": JuniperFormatter,
        "cisco": CiscoFormatter,
        "nexus": CiscoFormatter,
        "huawei": HuaweiFormatter,
        "optixtrans": OptixtransFormatter,
        "arista": CiscoFormatter,
        "nokia": NokiaFormatter,
        "routeros": RosFormatter,
        "aruba": CiscoFormatter,
        "pc": CommonFormatter,
        "ribbon": RibbonFormatter,
        "b4com": CiscoFormatter,
    }
    return formatters[vendor](**kwargs)


# ====
def parse_to_tree(text, splitter, comments=("!", "#")):
    tree = odict()
    for stack in _stacked(splitter(text), tuple(comments)):
        local_tree = tree
        for key in stack:
            if key not in local_tree:
                local_tree[key] = odict()
            local_tree = local_tree[key]
    return tree


# =====
def _stacked(lines, comments):
    stack = []
    for (level, line) in _stripped_indents(lines, comments):
        level += 1
        if level > len(stack):
            stack.append(line)
        elif level == len(stack):
            stack[-1] = line
        else:
            stack = stack[:level - 1] + [line]
        yield tuple(stack)


def _stripped_indents(lines, comments):
    indents = []
    curr_level = 0
    g_level = None

    for (number, (level, line)) in enumerate(_parsed_indents(lines, comments), start=1):
        if isinstance(line, str):
            if g_level is None:
                g_level = level
            level = level - (g_level or 0)
            if level < 0:
                raise ParserError("Invalid top indention: line %d: %s" % (number, line))

            if level > curr_level:
                indents.append(level - curr_level)
                curr_level += level - curr_level
            elif level < curr_level:
                while curr_level > level and len(indents):
                    curr_level -= indents.pop()
                if curr_level != level:
                    raise ParserError("Invalid top indention: line %d: %s" % (number, line))

            yield (len(indents), line)

        elif line is BlockEnd:
            indents = []
            curr_level = 0
            g_level = None


def _parsed_indents(lines, comments):
    for line in _filtered_lines(lines, comments):
        if isinstance(line, str):
            yield (_parse_indent(line), line.strip())
        else:
            yield (0, line)


def _filtered_lines(lines, comments):
    for line in lines:
        stripped = line.strip()
        # TODO Это для хуавей, так что хелпер нужно унести в Formatter
        if "#" in comments and line.startswith("#"):
            yield BlockEnd
        elif len(stripped) == 0 or stripped.startswith(comments):
            yield _CommentOrEmpty
        else:
            yield line


def _filtered_block_marks(blocks):
    return filter(lambda b: isinstance(b, str), blocks)


def _parse_indent(line):
    level = 0
    for ch in line:
        if ch in ("\t", " "):
            level += 1
        else:
            break
    return level
