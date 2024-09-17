from annet.deploy import DeployDriver, DeployOptions, DeployResult
from annet.annlib.netdev.views.hardware import HardwareView


class StubDeployDriver(DeployDriver):
    async def bulk_deploy(self, deploy_cmds: dict, args: DeployOptions) -> DeployResult:
        raise NotImplementedError()

    def apply_deploy_rulebook(self, hw: HardwareView, cmd_paths, do_finalize=True, do_commit=True):
        raise NotImplementedError()

    def build_configuration_cmdlist(self, hw: HardwareView, do_finalize=True, do_commit=True):
        raise NotImplementedError()

    def build_exit_cmdlist(self, hw):
        raise NotImplementedError()
