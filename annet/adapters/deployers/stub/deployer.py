from __future__ import annotations

from typing import TYPE_CHECKING, Any

from annet.annlib.command import CommandList
from annet.annlib.netdev.views.hardware import HardwareView
from annet.deploy import DeployDriver, DeployOptions, DeployResult, ProgressBar


if TYPE_CHECKING:
    from annet.vendors.tabparser import NotUniquePatch


class StubDeployDriver(DeployDriver):
    async def bulk_deploy(
        self, deploy_cmds: dict[Any, Any], args: DeployOptions, progress_bar: ProgressBar | None = None
    ) -> DeployResult:
        raise NotImplementedError()

    def apply_deploy_rulebook(
        self, hw: HardwareView, cmd_paths: NotUniquePatch, do_finalize: bool = True, do_commit: bool = True
    ) -> CommandList:
        raise NotImplementedError()

    def build_configuration_cmdlist(
        self, hw: HardwareView, do_finalize: bool = True, do_commit: bool = True
    ) -> tuple[CommandList, CommandList]:
        raise NotImplementedError()

    def build_exit_cmdlist(self, hw: HardwareView) -> CommandList:
        raise NotImplementedError()
