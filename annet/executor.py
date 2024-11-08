import asyncio
import logging
import multiprocessing
import os
import platform
import resource
import signal
import statistics
import time
from abc import ABC, abstractmethod
from functools import partial
from operator import itemgetter
from queue import Empty
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import colorama
import psutil

import annet.lib
from annet.annlib.command import Command, CommandList, Question  # noqa: F401
from annet.storage import Device


_logger = logging.getLogger(__name__)
FIRST_EXCEPTION = 1
ALL_COMPLETED = 2


class CommandResult(ABC):
    @abstractmethod
    def get_out(self) -> str:
        pass


class Connector(ABC):
    @abstractmethod
    async def cmd(self, cmd: Union[Command, str]) -> CommandResult:
        pass

    @abstractmethod
    async def download(self, files: List[str]) -> Dict[str, str]:
        pass

    @abstractmethod
    async def upload(self, files: Dict[str, str]):
        pass

    @abstractmethod
    def get_conn_trace(self) -> str:
        pass

    @abstractmethod
    async def aclose(self) -> str:
        pass


class Executor(ABC):
    # method for bulk config downloading TODO: remove in favor Connector.cmd
    @abstractmethod
    def fetch(self,
              devices: List[Device],
              files_to_download: Dict[str, List[str]] = None) -> Tuple[Dict[Device, str], Dict[Device, Any]]:
        pass

    @abstractmethod
    async def amake_connection(self, device: Device) -> Connector:
        pass


class ExecutorException(Exception):
    def __init__(self, *args: List[Any], auxiliary: Optional[Any] = None, **kwargs: object):
        self.auxiliary = auxiliary
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return "%s(args=%r,auxiliary=%s)" % (self.__class__.__name__, self.args, self.auxiliary)


class ExecException(ExecutorException):
    def __init__(self, msg: str, cmd: str, res: str, **kwargs):
        super().__init__(**kwargs)
        self.args = msg, cmd, res
        self.kwargs = kwargs
        self.msg = msg
        self.cmd = cmd
        self.res = res

    def __str__(self) -> str:
        return str(self.msg)

    def __repr__(self) -> str:
        return "%s<%s, %s>" % (self.__class__.__name__, self.msg, self.cmd)


class BadCommand(ExecException):
    pass


class NonzeroRetcode(ExecException):
    pass


class CommitException(ExecException):
    pass

def chunks_tuple(l, n):  # noqa
    return [tuple(l[i:i + n]) for i in range(0, len(l), n)]


def async_bulk(
        executor: Executor,
        devices: List[Device],
        coro_gen: Callable[[Connector, Device], Any],
        *args,
        processes: int = 1,
        show_report: bool = True,
        do_log: bool = True,
        log_dir: Optional[str] = None,
        policy: int = ALL_COMPLETED,
        **kwargs,
):
    """Connect to specified devices and work with their CLI.

    Note: this function is not allowed to be run in parallel, since it's using global state (TODO: fixme)

    :param devices: List of devices' fqdns to use their CLI.
    :param coro_gen: Async function. It contains all logic about usage of CLI.
        See docstring of "bind_coro_args" for allowed function signature and examples.
    :param args: Positional arguments to "bulk" function.
    :type processes: Amount of processes to fork for current work.
    :param show_report: Set this flag to show report to stdout.
    :param do_log: If True and log_dir is not set, then log_dir will be filled automatically.
    :param log_dir: Specify path to log all response from devices.
    :param policy: int flag. If FIRST_EXCEPTION, then work will be stopped after first error.
        Otherwise all hosts will be processed.
        TODO: fix that policy is not used if processes=1
    :param kwargs: other arguments to pass to "bulk" function.
        Note: it is not passed directly to "coro_gen" function!
            kwargs should be {'kwargs': {'var1': value1}} to set "var1" with "value1" in "coro_gen" function.

    TODOs:
        * do not log if do_log=False and log_dir is set.

    """
    res = {}
    deploy_durations = {}
    kwargs["log_dir"] = log_dir
    kwargs["policy"] = policy

    if processes == 1:
        host_res, host_duration = annet.lib.do_async(bulk(executor, devices, coro_gen, *args, **kwargs))
        res.update(host_res)
        deploy_durations.update(host_duration)
    else:
        # FIXME: show_report works per process
        if len(devices) != len(set(devices)):
            raise Exception("hostnames should be unique")
        # warm up a cache
        # asyncio.get_event_loop().run_until_complete(get_validator_rt_data(hostnames))
        if isinstance(devices, dict):
            devices = list(devices.keys())
        hostnames_chunks = chunks_tuple(devices, int(len(devices) / processes) + 1)
        pool = {}
        for hostnames_chunk in hostnames_chunks:
            res_q = multiprocessing.Queue()
            p = multiprocessing.Process(target=_mp_async_bulk, args=[res_q, hostnames_chunk, coro_gen, *args], kwargs=kwargs)
            pool[p] = [res_q, hostnames_chunk]
            p.start()
            _logger.info("process (id=%d) work with %d chunks", p.pid, len(hostnames_chunks))

        seen_error = False
        while True:
            done = []
            for p in pool:
                host_res = None
                try:
                    # proc wont be exited till q.get() call
                    host_res, host_duration = pool[p][0].get(timeout=0.2)
                except Empty:
                    pass
                else:
                    done.append(p)

                if not p.is_alive() and not host_res:
                    _logger.error("process %s has died: hostnames: %s", p.pid, pool[p][1])
                    host_res = {hostname: Exception("died with exitcode %s" % p.exitcode) for hostname in pool[p][1]}
                    host_duration = {hostname: 0 for hostname in pool[p][1]}  # FIXME:
                    done.append(p)

                if host_res:
                    res.update(host_res)
                    deploy_durations.update(host_duration)

                if p.exitcode:
                    _logger.error("process %s finished with bad exitcode %s", p.pid, p.exitcode)
                    seen_error = True
            for p in done:
                pool.pop(p)
            if policy == FIRST_EXCEPTION and seen_error:
                for p in pool:
                    p.terminate()
                    if p.is_alive():
                        time.sleep(0.4)
                    if p.is_alive():
                        os.kill(p.pid, signal.SIGKILL)
                    for hostname in pool[p][1]:
                        res[hostname] = Exception("force kill with exitcode %s" % p.exitcode)
                        deploy_durations[hostname] = 0  # FIXME:
            if not pool:
                break

    if show_report:
        show_bulk_report(devices, res, deploy_durations, do_log and log_dir)

    return res


def _show_type_summary(caption, items, total, stat_items=None):
    if items:
        if not stat_items:
            stat = ""
        else:
            avg = statistics.mean(stat_items)
            stat = "   %(min).1f/%(max).1f/%(avg).1f/%(stdev)s  (min/max/avg/stdev)" % dict(
                min=min(stat_items),
                max=max(stat_items),
                avg=avg,
                stdev="-" if len(stat_items) < 2 else "%.1f" % statistics.stdev(stat_items, xbar=avg)
            )

        print("%-8s %d of %d%s" % (caption, len(items), total, stat))


def show_bulk_report(hostnames, res, durations, log_dir):
    total = len(hostnames)
    if not total:
        return

    colorama.init()

    print("\n====== bulk deploy report ======")

    done = [host for (host, hres) in res.items() if not isinstance(hres, Exception)]
    cancelled = [host for (host, hres) in res.items() if isinstance(hres, asyncio.CancelledError)]
    failed = [host for (host, hres) in res.items() if isinstance(hres, Exception) and host not in cancelled]
    lost = [host for host in hostnames if host not in res]
    limit = 30

    _show_type_summary("Done :", done, total, [durations[h] for h in done])
    _print_limit(done, partial(_print_hostname, style=colorama.Fore.GREEN), limit, total)

    _show_type_summary("Failed :", failed, total, [durations[h] for h in failed])

    _print_limit(failed, partial(_print_failed, res=res), limit, total)

    _show_type_summary("Cancelled :", cancelled, total, [durations[h] for h in cancelled if durations[h] is not None])
    _print_limit(cancelled, partial(_print_hostname, style=colorama.Fore.RED), limit, total)

    _show_type_summary("Lost :", lost, total)
    _print_limit(lost, _print_hostname, limit, total)

    err_limit = 5
    if failed:
        errs = {}
        for hostname in failed:
            fmt_err = _format_exc(res[hostname])
            if fmt_err in errs:
                errs[fmt_err] += 1
            else:
                errs[fmt_err] = 1
        print("Top errors :")
        for fmt_err, n in sorted(errs.items(), key=itemgetter(1), reverse=True)[:err_limit]:
            print("  %-4d %s" % (n, fmt_err))
        print("\n", end="")

    if log_dir:
        print("See deploy logs in %s/\n" % os.path.relpath(log_dir))


def _format_exc(exc):
    if isinstance(exc, ExecException):
        cmd = str(exc.cmd)
        if len(cmd) > 50:
            cmd = cmd[:50] + "~.."
        return "'%s', cmd '%s'" % (exc.msg, cmd)
    elif isinstance(exc, ExecutorException):
        return "%s%r" % (exc.__class__.__name__, exc.args)  # исключить многословный auxiliary
    else:
        return repr(exc)


def _print_hostname(host, style=None):
    if style:
        host = style + host + colorama.Style.RESET_ALL
    print("  %s" % host)


def _print_limit(items, printer, limit, total, end="\n"):
    if not items:
        return
    if len(items) > limit and len(items) > total * 0.7:
        print("  ... %d hosts" % len(items))
    for host in items[:limit]:
        printer(host)
    if len(items) > limit:
        print("  ... %d more hosts" % (len(items) - limit))

    print(end, end="")


def _print_failed(host, res):
    exc = res[host]
    color = colorama.Fore.YELLOW if isinstance(exc, Warning) else colorama.Fore.RED
    print("  %s - %s" % (color + host + colorama.Style.RESET_ALL, _format_exc(exc)))


def _mp_async_bulk(res_q: multiprocessing.Queue, *args, **kwargs):
    res = annet.lib.do_async(bulk(*args, **kwargs))
    res_q.put(res)
    res_q.close()


async def bulk(
        executor: Executor,
        devices: List[Device],
        coro_gen: Callable[[Connector, Device, Optional[Dict[str, Any]]], Any],
        max_parallel: float = 100,
        policy: int = ALL_COMPLETED,
        log_dir: str = True,  # pylint: disable=unused-argument
        kwargs: Optional[dict] = None,
        console_log: bool = True
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """Connect to specified devices and work with their CLI.

    :param hostnames: List of devices' fqdns to use their CLI.
    :param coro_gen: Async function. It contains all logic about usage of CLI.
        See docstring of "bind_coro_args" for allowed function signature and examples.
    :param max_parallel: Upper border to CPU usage (in percentage 1 CPU = 100).
        If cpu usage is over, then tasks are trottled.
    :param policy: Flag to specify when tasks are completed.
    :param log_dir: Specify path to log all response from devices.
        TODO: fix default value.
    :param kwargs: Device independent arguments to call function. See @bind_coro_args for details.
    :param get_device: See "make_connection" for better understanding.
    :param device_cls: See "make_connection" for better understanding.
    :param streamer_cls: See "make_connection" for better understanding.
    :param console_log: If True and there is no handlers for root logger, then stderr will be used for logging.
    :return: two dicts with results per host and execution duration per host.

    """
    if console_log:
        init_log()

    tasks = []
    res = {}
    pending = set()
    tasks_to_device = {}
    time_of_start = {}
    deploy_durations = {}
    now = None
    if not kwargs:
        kwargs = {}

    def start_hook(device: Device):
        time_of_start[device.hostname] = time.monotonic()

    def end_hook(device: Device, task: asyncio.Task):
        duration = now - time_of_start[device.hostname]
        deploy_durations[device.hostname] = duration

        coro_exc = task.exception()
        if coro_exc:
            if policy == FIRST_EXCEPTION:
                _logger.error("%s %r", device.hostname, coro_exc, exc_info=coro_exc)
                _logger.info("Terminating all running tasks according to FIRST_EXCEPTION policy")
                res[device.hostname] = coro_exc
                raise CancelAllTasks
            else:
                if isinstance(coro_exc, AssertionError):
                    _logger.error("%s %r", device.hostname, coro_exc, exc_info=coro_exc)
                else:
                    _logger.error("%s %r", device.hostname, coro_exc)
            return coro_exc
        else:
            _logger.info("Finished in %0.2fs, hostname=%s", duration, device.hostname)
            return task.result()

    for device in devices:
        try:
            conn = await executor.amake_connection(device=device)
        except Exception as exc:
            _logger.error("failed to connect to %s %r", device.hostname, exc)
            res[device] = exc
            continue
        start_hook(device)
        task = asyncio.create_task(coro_gen(conn=conn, device=device, **kwargs))
        tasks_to_device[task] = device
        tasks.append(task)
    try:
        ndone = 0
        with CpuThrottler(asyncio.get_event_loop(), maximum=max_parallel) as throttler:
            while pending or tasks:
                left_fds = int(fd_left() / 2)  # better to be safe than sorry

                for _ in range(min(throttler.curr - len(pending), len(tasks), left_fds)):
                    pending.add(tasks.pop(0))
                if len(pending) == 0:
                    _logger.debug("empty pending list. tasks=%s throttler curr=%s left_fds=%s. waiting", len(tasks),
                                  throttler.curr, left_fds)
                    await asyncio.sleep(1)
                    continue
                example_host = next(iter(pending))
                _logger.debug("tasks status: %d pending, %d queued, pending example %s", len(pending), len(tasks), example_host)
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                now = time.monotonic()
                for task in done:
                    device = tasks_to_device[task]
                    res[device] = end_hook(device, task)
                    ndone += 1
    except CancelAllTasks:
        exc = asyncio.CancelledError()

        now = time.monotonic()
        for device, task in _get_remaining(tasks, pending, tasks_to_device):
            res[device] = exc

            if device.hostname in time_of_start:
                duration = now - time_of_start[device.hostname]
            else:
                duration = None
            deploy_durations[device.hostname] = duration

            if not asyncio.iscoroutine(task):
                _logger.info("task %s", task)
                task.cancel()

    return res, deploy_durations


def init_log():
    streamer = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(filename)s:%(lineno)d - %(funcName)s() - %(levelname)s - %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    streamer.setFormatter(fmt)
    if not logging.root.handlers:
        logging.root.addHandler(streamer)


class DeferredFileWrite:
    def __init__(self, file, mode="r"):
        self._file = file
        wrapper = {"w": "a", "wb": "ab"}
        if mode in wrapper:
            self._mode = wrapper[mode]
        else:
            raise Exception()

    def write(self, data):
        with open(self._file, self._mode) as fh:
            fh.write(data)

    def close(self):
        pass

    def flush(self):
        pass


class CancelAllTasks(Exception):
    pass


def _get_remaining(tasks, pending, tasks_to_device):
    for task in pending:
        yield (tasks_to_device[task], task)
    for task in tasks:
        yield (tasks_to_device[task], task)


_platform = platform.system()
_fd_available = resource.getrlimit(resource.RLIMIT_NOFILE)[0]


def fd_left():
    res = _fd_available
    if _platform == "Linux":
        res = _fd_available - len(list(os.scandir(path="/proc/self/fd/")))
    return res


class CpuThrottler:
    def __init__(self, loop, start=20, maximum=None, minimum=5, hz=1.0, target=80.0):
        self.loop = loop
        self.minimum = int(minimum)
        self.maximum = int(maximum or 0)
        self.hz = hz
        self.target = target
        self.timer_handle = None
        self.last_usage = 0
        self.curr = int(start)
        self.proc = psutil.Process(os.getpid())

    def __enter__(self):
        if self.proc and self.maximum:
            self.proc.cpu_percent()  # initialize previous value
            self.timer_handle = self.loop.call_later(self.hz, self.schedule)
        return self

    def __exit__(self, type_, value, tb):
        if self.timer_handle:
            self.timer_handle.cancel()

    def schedule(self):
        # re-schedule
        self.timer_handle = self.loop.call_later(self.hz, self.schedule)

        cpu_usage = self.proc.cpu_percent()
        self.last_usage = cpu_usage
        _logger.debug("current cpu_usage=%s", cpu_usage)
        if cpu_usage > self.target:
            self.change_by(0.5)
        elif cpu_usage > self.target * 0.8:
            pass
        elif cpu_usage > self.target * 0.2:
            self.change_by(1.2)
        else:
            self.change_by(1.5)

    def change_by(self, rate):
        new_curr = int(self.curr * rate)
        # округлим в нужную сторону
        if new_curr == self.curr:
            if rate > 1:
                new_curr += 1
            elif rate < 1:
                new_curr -= 1
        # ограничим пределами
        if new_curr < self.curr:
            new_curr = max(self.minimum, new_curr)
        else:
            if self.maximum is not None:
                new_curr = min(self.maximum, new_curr)

        if new_curr < self.curr:
            _logger.info("decreasing max_slots %d -> %d, cpu_usage=%.1f", self.curr, new_curr, self.last_usage)
        elif new_curr > self.curr:
            _logger.info("increasing max_slots %d -> %d, cpu_usage=%.1f", self.curr, new_curr, self.last_usage)

        # new_curr не делаем меньше 0, иначе не сможем его увеличить
        self.curr = max(new_curr, 1)
