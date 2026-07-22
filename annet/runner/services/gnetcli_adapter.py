"""
FIXME: This module should be part of gnetcli packages
"""
import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager
from datetime import datetime

from annet.annlib.command import CommandList
from annet.deploy import ProgressBar
from annet.storage import Device
from gnetcli_adapter.gnetcli_adapter import AppSettings, ApiMaker
from gnetcli_adapter.gnetcli_adapter import breed_to_device
from gnetcli_adapter.gnetcli_adapter import get_device_ip
from gnetcli_adapter.gnetcli_adapter import parse_annet_qa
from gnetcli_adapter.progress_tracker import CompositeTracker
from gnetcli_adapter.progress_tracker import FileProgressTracker
from gnetcli_adapter.progress_tracker import LogProgressTracker
from gnetcli_adapter.progress_tracker import ProgressBarTracker
from gnetcli_adapter.progress_tracker import ProgressTracker
from gnetclisdk.client import File
from gnetclisdk.client import Gnetcli
from gnetclisdk.client import GnetcliSessionCmd
from gnetclisdk.client import HostParams
from gnetclisdk.exceptions import EOFError
from gnetclisdk.proto.server_pb2 import CMDResult
from gnetclisdk.proto.server_pb2 import FileStatus

from annet.runner.deploy_protocols import CommandResult
from annet.runner.deploy_protocols import DeviceCommands
from annet.runner.deploy_protocols import DeviceDriver
from annet.runner.deploy_protocols import DeviceDriverFactory
from annet.runner.deploy_protocols import DeviceID
from annet.runner.deploy_protocols import DeviceResult
from annet.runner.deploy_protocols import FileCommands
from annet.runner.deploy_protocols import FileResult

logger = logging.getLogger(__name__)


class FixedFileProgressTracker(FileProgressTracker):
    def __init__(self, device: Device, dirname: str, start_time: datetime) -> None:
        super().__init__(device, dirname)
        self._start_time = start_time

    def _make_file_path(self) -> str:
        datedir = f"{self._start_time:%Y-%m-%d-%H-%M}"
        return os.path.join(  # noqa: PTH118
            self.dirname,
            datedir,
            f"{self.device.fqdn}_{self._start_time.timestamp():.0f}",
        )


class GnetCliDriver(DeviceDriver):
    def __init__(
        self,
        api: Gnetcli,
        conf: AppSettings,
        logs_dir: str | None,
        start_time: datetime,
    ) -> None:
        self._api = api
        self._conf = conf
        self._logs_dir = logs_dir
        self._sessions: dict[DeviceID, GnetcliSessionCmd] = {}
        self._connection_errors: dict[DeviceID, str] = {}
        self._exit_stack = AsyncExitStack()
        self._start_time = start_time

    def get_connection_errors(self, devices: list[Device]) -> dict[DeviceID, str]:
        res = {}
        for d in devices:
            if d.id in self._connection_errors:
                res[d.id] = self._connection_errors[d.id]
            elif d.id not in self._sessions:
                res[d.id] = "Session not found"
        return res

    async def execute(
        self,
        devices: list[Device],
        deploy_cmds: dict[DeviceID, DeviceCommands],
        progressbar: ProgressBar | None,
    ) -> dict[DeviceID, DeviceResult]:
        return dict(
            await asyncio.gather(
                *(
                    self._execute_device(device, progressbar, deploy_cmds[device.id])
                    for device in devices
                    if device.id in deploy_cmds
                )
            )
        )

    async def _execute_device(
        self,
        device: Device,
        progressbar: ProgressBar | None,
        deploy_cmd: DeviceCommands,
    ) -> tuple[DeviceID, DeviceResult]:
        with self._init_progress_tracker(progressbar, device) as tracker:
            tracker.set_total(self._total_steps(deploy_cmd))
            try:
                res = await self._execute_device_impl(device, deploy_cmd, tracker)
            except Exception as e:  # noqa: BLE001
                tracker.finish_err(f"Seen exception: {e}")
                return device.id, DeviceResult(errors=[str(e)])
            else:
                tracker.finish_ok("All done")
                return device.id, res

    def _init_progress_tracker(self, progressbar: ProgressBar | None, device: Device) -> ProgressTracker:
        tracker = CompositeTracker(LogProgressTracker(device))
        if progressbar:
            tracker.add_tracker(ProgressBarTracker(device, progressbar))
        if self._logs_dir:
            tracker.add_tracker(FixedFileProgressTracker(device, self._logs_dir, self._start_time))
        return tracker

    def _total_steps(self, deploy_cmd: DeviceCommands) -> int:
        res = len(deploy_cmd.before_cmds) + len(deploy_cmd.after_cmds)
        for file_cmd in deploy_cmd.upload_files.values():
            res += len(file_cmd.before_cmds) + len(file_cmd.after_cmds)
        res += bool(deploy_cmd.download_files) + bool(deploy_cmd.upload_files)
        return res or 1

    async def _execute_device_impl(
        self,
        device: Device,
        deploy_cmd: DeviceCommands,
        tracker: ProgressTracker,
    ) -> DeviceResult:
        res = DeviceResult(errors=[], upload_files={fname: FileResult() for fname in deploy_cmd.upload_files})
        session = self._sessions.get(device.id)
        if not session:
            tracker.finish_err("Device is not connected")
            res.errors.append(f"Device {device.fqdn} is not connected")
            return res

        ip = get_device_ip(device)
        gnetcli_device = breed_to_device.get(device.breed, device.breed)
        host_params = HostParams(
            credentials=self._conf.make_dev_credentials(),
            device=gnetcli_device,
            ip=ip,
        )
        res.before_cmds = await self._execute_list(device.id, session, host_params, deploy_cmd.before_cmds, tracker)

        for filename, filecmd in deploy_cmd.upload_files.items():
            res.upload_files[filename].before_cmds = await self._execute_list(
                device.id, session, host_params, filecmd.before_cmds, tracker
            )
        await self._upload_files(device, host_params, deploy_cmd.upload_files, tracker)
        for filename, filecmd in deploy_cmd.upload_files.items():
            res.upload_files[filename].after_cmds = await self._execute_list(
                device.id, session, host_params, filecmd.after_cmds, tracker
            )

        res.download_files = await self._download_files(device, host_params, deploy_cmd.download_files, tracker)

        res.after_cmds = await self._execute_list(device.id, session, host_params, deploy_cmd.after_cmds, tracker)
        return res

    async def _upload_files(
        self,
        device: Device,
        host_params: HostParams,
        files: dict[str, FileCommands],
        tracker: ProgressTracker,
    ) -> None:
        if not files:
            return
        tracker.upload_files(list(files))
        to_upload = {
            file: File(content=filecmd.data, status=FileStatus.FileStatus_notset) for file, filecmd in files.items()
        }
        await self._api.upload(device.fqdn, to_upload, host_params)
        tracker.files_uploaded()

    async def _download_files(
        self,
        device: Device,
        host_params: HostParams,
        files: list[str],
        tracker: ProgressTracker,
    ) -> dict[str, bytes]:
        if not files:
            return {}
        logger.info("Downloading files %s", files)
        tracker.run_command("Download files")
        downloaded = await self._api.download(hostname=device.fqdn, paths=files, host_params=host_params)
        tracker.command_done_ok(CMDResult())
        return {fname: file.content for fname, file in downloaded.items()}

    async def _execute_list(
        self,
        device_id: DeviceID,
        session: GnetcliSessionCmd,
        host_params: HostParams,
        cmds: CommandList,
        tracker: ProgressTracker,
    ) -> list[CommandResult]:
        res = []
        for cmd in cmds:
            tracker.run_command(cmd.cmd)
            try:
                cmd_res = await session.cmd(
                    cmd=cmd.cmd,
                    cmd_timeout=cmd.timeout,
                    host_params=host_params,
                    qa=parse_annet_qa(cmd.questions or []),
                    trace=True,
                )
            except EOFError:
                self._sessions.pop(device_id, None)
                if cmd.suppress_eof:
                    # TODO: check last cmd
                    tracker.command_done_error_suppressed("Suppressed EOF")
                    res.append(
                        CommandResult(
                            cmd=cmd.cmd,
                            out="",
                            error=None,
                        )
                    )
                    continue

                tracker.command_done_error("Unexpected EOFError")
                res.append(
                    CommandResult(
                        cmd=cmd.cmd,
                        out="",
                        error="Unexpected EOFError",
                    )
                )
                return res
            else:
                if cmd_res.status == 0:
                    tracker.command_done_ok(cmd_res)
                    res.append(
                        CommandResult(
                            cmd=cmd.cmd,
                            out=cmd_res.out.decode(),
                            error=None,
                        )
                    )
                elif cmd.suppress_nonzero:
                    tracker.command_done_error_suppressed(cmd_res.error.decode())
                    res.append(
                        CommandResult(
                            cmd=cmd.cmd,
                            out=cmd_res.out.decode(),
                            error=None,
                        )
                    )
                else:
                    tracker.command_done_error(cmd_res.error.decode())
                    res.append(
                        CommandResult(
                            cmd=cmd.cmd,
                            out=cmd_res.out.decode(),
                            error=cmd_res.error.decode() or None,
                        )
                    )
                    return res
        return res

    async def connect(self, device: Device) -> None:
        try:
            cm = self._api.cmd_session(hostname=device.fqdn)
            session = await self._exit_stack.enter_async_context(cm)
            self._sessions[device.id] = session
        except Exception as e:
            logger.exception("Failed to connect to device %s", device.fqdn)
            self._connection_errors[device.id] = repr(e)

    async def disconnect_all(self) -> None:
        await self._exit_stack.aclose()


class GnetCliDriverFactory(ApiMaker, DeviceDriverFactory):
    def __init__(
        self,
        settings: AppSettings,
        logs_dir: str | None,
        start_time: datetime,
    ) -> None:
        self.conf = settings
        self._logs_dir = logs_dir
        self._start_time = start_time
        super().__init__()

    @asynccontextmanager
    async def make_driver(
        self,
        devices: list[Device],
        quit_commands: dict[DeviceID, DeviceCommands],
    ) -> AsyncIterator[DeviceDriver]:
        async with self.make_api() as api:
            driver = GnetCliDriver(api, self.conf, self._logs_dir, self._start_time)
            await asyncio.gather(*(driver.connect(d) for d in devices))
            yield driver
            await driver.execute(devices, quit_commands, None)
            await driver.disconnect_all()
