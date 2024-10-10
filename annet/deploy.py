# pylint: disable=unused-argument


import abc
import itertools
import re
from collections import namedtuple
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, OrderedDict, Tuple, Type

from contextlog import get_logger

from annet import text_term_format
from annet.annlib.command import Command, Question, CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.rbparser.deploying import MakeMessageMatcher, Answer
from annet.cli_args import DeployOptions
from annet.connectors import Connector, get_connector_from_config
from annet.output import TextArgs
from annet.rulebook import get_rulebook, deploying
from annet.storage import Device


NCURSES_SIZE_T = 2 ** 15 - 1


_DeployResultBase = namedtuple("_DeployResultBase", ("hostnames", "results", "durations", "original_states"))


class DeployResult(_DeployResultBase):  # noqa: E302
    def add_results(self, results: Dict[str, Optional[Exception]]) -> None:
        for hostname, result in results.items():
            self.hostnames.append(hostname)
            self.results[hostname] = result
            self.durations[hostname] = 0.0
            self.original_states[hostname] = None


class _FetcherConnector(Connector["Fetcher"]):
    name = "Fetcher"
    ep_name = "deploy_fetcher"
    ep_by_group_only = "annet.connectors.fetcher"

    def _get_default(self) -> Type["Fetcher"]:
        # if entry points are broken, try to use direct import
        import annet.adapters.fetchers.stub.fetcher as stub_fetcher
        return stub_fetcher.StubFetcher


class _DriverConnector(Connector["DeployDriver"]):
    name = "DeployDriver"
    ep_name = "deploy_driver"
    ep_by_group_only = "annet.connectors.deployer"

    def _get_default(self) -> Type["DeployDriver"]:
        # if entry points are broken, try to use direct import
        import annet.adapters.deployers.stub.deployer as stub_deployer
        return stub_deployer.StubDeployDriver


fetcher_connector = _FetcherConnector()
driver_connector = _DriverConnector()


class Fetcher(abc.ABC):
    @abc.abstractmethod
    def fetch_packages(self, devices: List[Device],
                       processes: int = 1, max_slots: int = 0) -> Tuple[Dict[Device, str], Dict[Device, Any]]:
        pass

    @abc.abstractmethod
    def fetch(self, devices: List[Device],
              files_to_download: Dict[str, List[str]] = None,
              processes: int = 1, max_slots: int = 0):
        pass


def get_fetcher() -> Fetcher:
    connectors = fetcher_connector.get_all()
    fetcher, _ = get_connector_from_config("fetcher", connectors)
    return fetcher


class DeployDriver(abc.ABC):
    @abc.abstractmethod
    async def bulk_deploy(self, deploy_cmds: dict, args: DeployOptions) -> DeployResult:
        pass

    @abc.abstractmethod
    def apply_deploy_rulebook(self, hw: HardwareView, cmd_paths, do_finalize=True, do_commit=True):
        pass

    @abc.abstractmethod
    def build_configuration_cmdlist(self, hw: HardwareView, do_finalize=True, do_commit=True):
        pass

    @abc.abstractmethod
    def build_exit_cmdlist(self, hw):
        pass


def get_deployer() -> DeployDriver:
    connectors = driver_connector.get_all()
    deployer, _ = get_connector_from_config("deployer", connectors)
    return deployer


# ===
def scrub_config(text, breed):
    return text


def show_bulk_report(hostnames, results, durations, log_dir):
    pass


class AskConfirm:
    CUT_WARN_MSG = "WARNING: the text was cut because of curses limits."

    def __init__(self, text: str, text_type="diff", alternative_text: str = "",
                 alternative_text_type: str = "diff", allow_force_yes: bool = False):
        self.text = [text, text_type]
        self.alternative_text = [alternative_text, alternative_text_type]
        self.color_to_curses: Dict[Optional[str], int] = {}
        self.lines: Dict[int, List[TextArgs]] = {}
        self.rows = None
        self.cols = None
        self.top = 0
        self.left = 0
        self.pad = None
        self.screen = None
        self.found_pos = {}
        self.curses_lines = None
        self.debug_prompt = TextArgs("")
        self.page_position = TextArgs("")
        s_force = "/f" if allow_force_yes else ""
        self.prompt = [
            TextArgs("Execute these commands? [Y%s/q] (/ - search, a - patch/cmds)" % s_force, "blue", offset=0),
            self.page_position,
            self.debug_prompt]

    def _parse_text(self):
        txt = self.text[0]
        txt_split = txt.splitlines()
        # curses pad, который тут используется, имеет ограничение на количество линий
        if (len(txt_split) + 1) >= NCURSES_SIZE_T:  # +1 для того чтобы курсор можно было переместить на пустую строку
            del txt_split[NCURSES_SIZE_T - 3:]
            txt_split.insert(0, self.CUT_WARN_MSG)
            txt_split.append(self.CUT_WARN_MSG)
            txt = "\n".join(txt_split)
        self.rows = len(txt_split)
        self.cols = max(len(line) for line in txt_split)
        res = text_term_format.curses_format(txt, self.text[1])
        self.lines = res

    def _update_search_pos(self, expr):
        self.found_pos = {}
        if not expr:
            return
        try:
            expr = re.compile(expr)
        except Exception:
            return None
        lines = self.text[0].splitlines()
        for (line_no, line) in enumerate(lines):
            for match in re.finditer(expr, line):
                if line_no not in self.found_pos:
                    self.found_pos[line_no] = []
                self.found_pos[line_no].append(TextArgs(match.group(0), "highlight", match.start()))

    def _init_colors(self):
        self.color_to_curses = init_colors()

    def _init_pad(self):
        import curses

        with self._store_xy():
            self.pad = curses.newpad(self.rows + 1, self.cols)
            self.pad.keypad(True)  # accept arrow keys
            self._render_to_pad(self.lines)

    def _render_to_pad(self, lines: dict):
        """
        Рендерим данный на pad
        :param lines: словарь проиндексированный по номерам линий
        :return:
        """
        with self._store_xy():
            for line_no, line_data in sorted(lines.items()):
                line_pos_calc = 0
                for line_part in line_data:
                    if line_part.offset is not None:
                        line_pos = line_part.offset
                    else:
                        line_pos = line_pos_calc
                    if line_part.color:
                        self.pad.addstr(line_no, line_pos, line_part.text, self.color_to_curses[line_part.color])
                    else:
                        self.pad.addstr(line_no, line_pos, line_part.text)
                    line_pos_calc += len(line_part.text)

    def _add_prompt(self):
        for prompt_part in self.prompt:
            if not prompt_part:
                continue
            if prompt_part.offset is None:
                offset = 0
            else:
                offset = prompt_part.offset
            self.screen.addstr(self.curses_lines - 1, offset, prompt_part.text, self.color_to_curses[prompt_part.color])

    def _clear_prompt(self):
        with self._store_xy():
            self.screen.move(self.curses_lines - 1, 0)
            self.screen.clrtoeol()

    def show(self):
        self._add_prompt()
        self.screen.refresh()
        size = self.screen.getmaxyx()
        self.pad.refresh(self.top, self.left, 0, 0, size[0] - 2, size[1] - 2)

    @contextmanager
    def _store_xy(self):
        if self.pad is not None:
            current_y, current_x = self.pad.getyx()
            yield current_y, current_x
            max_y, max_x = self.pad.getmaxyx()
            current_y = min(max_y - 1, current_y)
            current_x = min(max_x - 1, current_x)

            self.pad.move(current_y, current_x)
        else:
            yield

    def search_next(self, prev=False):
        to = None
        current_y, current_x = self.pad.getyx()
        if prev:
            for line_index in sorted(self.found_pos, reverse=True):
                for text_args in self.found_pos[line_index]:
                    if line_index > current_y:
                        continue

                    if line_index < current_y or line_index == current_y and text_args.offset < current_x:
                        to = line_index, text_args.offset
                        break
                if to:
                    break
        else:
            for line_index in sorted([i for i in self.found_pos if i >= current_y]):
                for text_args in self.found_pos[line_index]:
                    if line_index > current_y or line_index == current_y and text_args.offset > current_x:
                        to = line_index, text_args.offset
                        break
                if to:
                    break
        if to:
            return to[0] - current_y, to[1] - current_x
        else:
            return 0, 0

    def _search_prompt(self):
        import curses

        search_prompt = [TextArgs("Search: ", "green_bold", offset=0)]
        current_prompt = self.prompt
        self.prompt = search_prompt
        with self._store_xy():
            self._clear_prompt()
            self.show()
            curses.echo()
            expr = self.screen.getstr().decode()
            curses.noecho()
            self._update_search_pos(expr)
            self._parse_text()
            self._init_pad()
            # срендерем поверх pad слой с подстветкой
            self._render_to_pad(self.found_pos)
            y_offset, x_offset = self.search_next()
        self.prompt = current_prompt
        return y_offset, x_offset

    def _do_commands(self):
        import curses

        while True:
            self._clear_prompt()
            try:
                ch = self.pad.getch()
            except KeyboardInterrupt:
                return "n"
            max_y, max_x = self.screen.getmaxyx()
            _, pad_max_x = self.pad.getmaxyx()
            max_y -= 2  # prompt
            y_offset = 0
            x_offset = 0
            margin = 0
            y_delta = 0
            x_delta = 0

            y, x = self.pad.getyx()
            if ch == ord("q"):
                return "exit"
            elif ch in [ord("y"), ord("Y")]:
                return "y"
            elif ch in [ord("f"), ord("F")]:
                return "force-yes"
            elif ch == ord("a"):
                if self.alternative_text:
                    self.text, self.alternative_text = self.alternative_text, self.text
                self.screen.clear()
                self._parse_text()
                self._init_pad()
            elif ch == ord("d"):
                if self.debug_prompt.text == "":
                    self.debug_prompt.text = "init"
                else:
                    self.debug_prompt.text = ""
            elif ch == ord("n"):
                y_offset, x_offset = self.search_next()
                margin = 10
            elif ch == ord("N"):
                y_offset, x_offset = self.search_next(prev=True)
                margin = 10
            elif ch == ord("/"):
                y_offset, x_offset = self._search_prompt()
                margin = 10
            elif ch == curses.KEY_UP:
                y_offset = -1
            elif ch == curses.KEY_PPAGE:
                y_offset = -10
            elif ch == curses.KEY_HOME:
                y_offset = -len(self.lines)
            elif ch == curses.KEY_DOWN:
                y_offset = 1
            elif ch == curses.KEY_NPAGE:
                y_offset = 10
            elif ch == curses.KEY_END:
                y_offset = len(self.lines)
            elif ch == curses.KEY_LEFT:
                x_offset = -1
            elif ch == curses.KEY_RIGHT:
                x_offset = 1

            if y_offset or x_offset:
                y = max(0, y + y_offset)
                y = min(self.rows, y)
                x = max(0, x + x_offset)
                x = min(self.cols, x)

                y_delta = y - (self.top + max_y - margin)
                if y_delta > 0:
                    self.top += y_delta
                elif (y - margin) < self.top:
                    self.top = y

                self.top = min(self.top, len(self.lines) - max_y)

                x_delta = x - (self.left + max_x)
                if x_delta > 0:
                    self.left += x_delta
                elif x < self.left:
                    self.left = x

                x = min(x, pad_max_x - 1)
                self.pad.move(y, x)

            if self.debug_prompt.text != "":
                debug_line = "y=%s x=%s, x_delta=%s y_delta=%s top=%s, max_y=%s max_x=%s lines=%s" % \
                             (y, x, x_delta, y_delta, self.top, max_y, max_x, len(self.lines))
                self.debug_prompt.text = debug_line
                self.debug_prompt.color = "green_bold"
                self.debug_prompt.offset = max_x - len(debug_line) - 1

            if self.debug_prompt.text == "":
                self.page_position.color = "highlight"
                self.page_position.text = "line %s/%s" % (y, len(self.lines))
                self.page_position.offset = max_x - len(self.page_position.text) - 1

            self.show()

    def loop(self):
        import curses

        res = None
        old_cursor = None
        try:
            self.screen = curses.initscr()
            self.screen.leaveok(True)
            self.curses_lines = curses.LINES  # pylint: disable=maybe-no-member
            curses.start_color()
            curses.noecho()  # no echo key input
            curses.cbreak()  # input with no-enter keyed
            try:
                old_cursor = curses.curs_set(2)
            except Exception:
                pass
            self._init_colors()
            self._parse_text()
            self._init_pad()
            self.pad.move(0, 0)
            self.show()
            res = self._do_commands()
        except Exception as err:
            get_logger().exception("%s", err)
        finally:
            if old_cursor is not None:
                curses.curs_set(old_cursor)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
        return res


def init_colors():
    import curses

    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_BLUE, curses.COLOR_WHITE)
    curses.init_pair(7, curses.COLOR_RED, curses.COLOR_WHITE)
    curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(9, curses.COLOR_CYAN, curses.COLOR_BLUE)
    return {
        "green": curses.color_pair(1),
        "green_bold": curses.color_pair(1) | curses.A_BOLD,
        "cyan": curses.color_pair(2),
        "red": curses.color_pair(3),
        "magenta": curses.color_pair(4),
        "yellow": curses.color_pair(5),
        "blue": curses.color_pair(6),
        "highlight": curses.color_pair(7),
        None: curses.color_pair(8),
        "cyan_blue": curses.color_pair(9),
    }


class RulebookQuestionHandler:
    def __init__(self, dialogs):
        self._dialogs = dialogs

    def __call__(self, dev: Connector, cmd: Command, match_content: bytes):
        content = match_content.strip()
        content = content.decode()
        for matcher, answer in self._dialogs.items():
            if matcher(content):
                return Command(answer.text)

        get_logger().info("no answer in rulebook. dialogs=%s match_content=%s", self._dialogs, match_content)
        return None


def rb_question_to_question(q: MakeMessageMatcher, a: Answer) -> Question:  # TODO: drop MakeMessageMatcher
    if not a.send_nl:
        raise Exception("not supported false send_nl")
    text: str = q._text  # pylint: disable=protected-access
    is_regexp = False
    if text.startswith("/") and text.endswith("/"):
        is_regexp = True
        text = text[1:-1]
    res = Question(question=text, answer=a.text, is_regexp=is_regexp)
    return res


def make_cmd_params(rule: Dict[str, Any]) -> Dict[str, Any]:
    if rule:
        qa_handler = RulebookQuestionHandler(rule["attrs"]["dialogs"])
        qa_list: List[Question] = []
        for matcher, answer in qa_handler._dialogs.items():  # pylint: disable=protected-access
            qa_list.append(rb_question_to_question(matcher, answer))
        return {
            "questions": qa_list,
            "timeout": rule["attrs"]["timeout"],
        }
    return {
        "timeout": 30,
    }


def make_apply_commands(rule: dict, hw: HardwareView, do_commit: bool, do_finalize: bool, path: Optional[str] = None):
    apply_logic = rule["attrs"]["apply_logic"]
    before, after = apply_logic(hw, do_commit=do_commit, do_finalize=do_finalize, path=path)
    return before, after


def fill_cmd_params(rules: OrderedDict, cmd: Command):
    rule = deploying.match_deploy_rule(rules, (cmd.cmd,), {})
    if rule:
        cmd_params = make_cmd_params(rule)
        cmd.questions = cmd_params.get("questions", None)
        cmd.timeout = cmd_params["timeout"]


def apply_deploy_rulebook(hw: HardwareView, cmd_paths, do_finalize=True, do_commit=True):
    rules = get_rulebook(hw)["deploying"]
    cmds_with_apply = []
    for cmd_path, context in cmd_paths.items():
        rule = deploying.match_deploy_rule(rules, cmd_path, context)
        cmd_params = make_cmd_params(rule)
        before, after = make_apply_commands(rule, hw, do_commit, do_finalize)

        cmd = Command(cmd_path[-1], **cmd_params)
        # XXX более чистый способ передавать-мета инфу о команде
        cmd.level = len(cmd_path) - 1
        cmds_with_apply.append((cmd, before, after))

    def _key(item):
        _cmd, before, after = item
        return (tuple(cmd.cmd for cmd in before), tuple(cmd.cmd for cmd in after))

    cmdlist = CommandList()
    for _k, cmd_before_after in itertools.groupby(cmds_with_apply, key=_key):
        cmd_before_after = list(cmd_before_after)
        _, before, after = cmd_before_after[0]
        for c in before:
            c.level = 0
            fill_cmd_params(rules, c)
            cmdlist.add_cmd(c)
        for cmd, _before, _after in cmd_before_after:
            cmdlist.add_cmd(cmd)
        for c in after:
            c.level = 0
            fill_cmd_params(rules, c)
            cmdlist.add_cmd(c)
    return cmdlist
