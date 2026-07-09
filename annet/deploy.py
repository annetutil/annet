# pylint: disable=unused-argument
from __future__ import annotations

import abc
import itertools
from collections import namedtuple
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast

from contextlog import get_logger

from annet.annlib.command import Command, CommandList, Question
from annet.annlib.netdev.views.hardware import HardwareView
from annet.annlib.rbparser.deploying import Answer, MakeMessageMatcher
from annet.cli_args import DeployOptions as DeployOptions
from annet.connectors import Connector, get_connector_from_config
from annet.rulebook import deploying, get_rulebook
from annet.rulebook.types import DeployRule, DeployRulebook
from annet.storage import Device


if TYPE_CHECKING:
    from annet.vendors.tabparser import NotUniquePatch


_DeployResultBase = namedtuple("_DeployResultBase", ("hostnames", "results", "durations", "original_states"))


class ProgressBar(abc.ABC):
    @abc.abstractmethod
    def set_content(self, tile_name: str, content: str) -> None:
        pass

    @abc.abstractmethod
    def add_content(self, tile_name: str, content: str) -> None:
        pass

    @abc.abstractmethod
    def reset_content(self, tile_name: str) -> None:
        pass

    @abc.abstractmethod
    def set_progress(
        self,
        tile_name: str,
        iteration: int,
        total: int,
        prefix: str = "",
        suffix: str = "",
        fill: str = "",
        error: bool = False,
    ) -> None:
        pass

    @abc.abstractmethod
    def set_exception(self, tile_name: str, cmd_exc: str, last_cmd: str, progress_max: int, content: str = "") -> None:
        pass


class DeployResult(_DeployResultBase):  # noqa: E302
    def add_results(self, results: dict[str, Exception]) -> None:
        for hostname, excs in results.items():
            self.hostnames.append(hostname)
            self.results[hostname] = excs
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
    async def fetch_packages(
        self,
        devices: list[Device],
        processes: int = 1,
        max_slots: int = 0,
    ) -> tuple[dict[Device, frozenset[str]], dict[Device, Any]]:
        pass

    @abc.abstractmethod
    async def fetch(
        self,
        devices: list[Device],
        files_to_download: dict[Device, list[str] | Exception] | None = None,
        processes: int = 1,
        max_slots: int = 0,
    ) -> tuple[dict[Device, Any], dict[Device, Exception]]:
        pass


def get_fetcher() -> Fetcher:
    connectors = fetcher_connector.get_all()
    fetcher, _ = get_connector_from_config("fetcher", connectors)
    return fetcher


class DeployDriver(abc.ABC):
    @abc.abstractmethod
    async def bulk_deploy(
        self, deploy_cmds: dict[Device, Any], args: DeployOptions, progress_bar: ProgressBar | None = None
    ) -> DeployResult:
        pass

    @abc.abstractmethod
    def apply_deploy_rulebook(
        self, hw: HardwareView, cmd_paths: NotUniquePatch, do_finalize: bool = True, do_commit: bool = True
    ) -> CommandList:
        pass

    @abc.abstractmethod
    def build_configuration_cmdlist(
        self, hw: HardwareView, do_finalize: bool = True, do_commit: bool = True
    ) -> tuple[CommandList, CommandList]:
        pass

    @abc.abstractmethod
    def build_exit_cmdlist(self, hw: HardwareView) -> CommandList:
        pass


def get_deployer() -> DeployDriver:
    connectors = driver_connector.get_all()
    deployer, _ = get_connector_from_config("deployer", connectors)
    return deployer


# ===
def scrub_config(text: str, breed: str | None) -> str:
    return text


def show_bulk_report(
    hostnames: list[str],
    results: dict[str, Exception],
    durations: dict[str, float],
    log_dir: str | None,
) -> None:
    pass


class RulebookQuestionHandler:
    def __init__(self, dialogs: dict[MakeMessageMatcher, Answer]) -> None:
        self._dialogs = dialogs

    def __call__(self, dev: Connector[Any], cmd: Command, match_content: bytes) -> Command | None:
        content = match_content.strip().decode()
        for matcher, answer in self._dialogs.items():
            if matcher(content):
                return Command(answer.text)

        get_logger().info("no answer in rulebook. dialogs=%s match_content=%s", self._dialogs, match_content)
        return None


def rb_question_to_question(q: MakeMessageMatcher, a: Answer) -> Question:  # TODO: drop MakeMessageMatcher
    text: str = q.text
    answer: str = a.text
    is_regexp = False
    if text.startswith("/") and text.endswith("/"):
        is_regexp = True
        text = text[1:-1]
    res = Question(question=text, answer=answer, is_regexp=is_regexp, not_send_nl=not a.send_nl)
    return res


def make_cmd_params(rule: DeployRule) -> Dict[str, Any]:
    if rule:
        qa_handler = RulebookQuestionHandler(rule["attrs"]["dialogs"])
        qa_list: List[Question] = []
        for matcher, answer in qa_handler._dialogs.items():  # pylint: disable=protected-access
            qa_list.append(rb_question_to_question(matcher, answer))
        return {
            "questions": qa_list,
            "timeout": rule["attrs"]["timeout"],
            "suppress_errors": rule["attrs"]["suppress_errors"],
        }
    return {
        "timeout": 30,
    }


def make_apply_commands(
    rule: DeployRule, hw: HardwareView, do_commit: bool, do_finalize: bool, path: Optional[str] = None
) -> tuple[CommandList, CommandList]:
    apply_logic = rule["attrs"]["apply_logic"]
    before, after = apply_logic(hw, do_commit=do_commit, do_finalize=do_finalize, path=path)
    return before, after


def fill_cmd_params(rules: DeployRulebook, cmd: Command) -> None:
    rule = deploying.match_deploy_rule(rules, (str(cmd),), {})
    if rule:
        cmd_params = make_cmd_params(rule)
        cmd.questions = cmd_params.get("questions", None)
        if cmd.timeout is None:
            cmd.timeout = cmd_params["timeout"]
        if cmd.read_timeout is None:
            cmd.read_timeout = cmd.timeout
        if "suppress_errors" in cmd_params:
            cmd.suppress_errors |= cmd_params["suppress_errors"]


def apply_deploy_rulebook(
    hw: HardwareView, cmd_paths: NotUniquePatch, do_finalize: bool = True, do_commit: bool = True
) -> CommandList:
    rules = get_rulebook(hw)["deploying"]
    cmds_with_apply = []
    for cmd_path, context in cmd_paths.items():
        # match_deploy_rule declares cmd_path as tuple[str] (a 1-tuple), but real command
        # paths are variadic tuple[str, ...]; see annet/rulebook/deploying.py.
        rule = deploying.match_deploy_rule(rules, cast("tuple[str]", cmd_path), context)
        cmd_params = make_cmd_params(rule)
        before, after = make_apply_commands(rule, hw, do_commit, do_finalize)

        cmd = Command(cmd_path[-1], **cmd_params)
        # XXX более чистый способ передавать-мета инфу о команде
        cmd.level = len(cmd_path) - 1
        cmds_with_apply.append((cmd, before, after))

    def _key(item: tuple[Command, CommandList, CommandList]) -> tuple[tuple[str | bytes, ...], tuple[str | bytes, ...]]:
        _cmd, before, after = item
        return (tuple(cmd.cmd for cmd in before), tuple(cmd.cmd for cmd in after))

    cmdlist = CommandList()
    for _k, group in itertools.groupby(cmds_with_apply, key=_key):
        group_items = list(group)
        _, before, after = group_items[0]
        for c in before:
            c.level = 0
            fill_cmd_params(rules, c)
            cmdlist.add_cmd(c)
        for cmd, _before, _after in group_items:
            cmdlist.add_cmd(cmd)
        for c in after:
            c.level = 0
            fill_cmd_params(rules, c)
            cmdlist.add_cmd(c)
    return cmdlist
