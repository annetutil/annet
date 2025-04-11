import asyncio
import os
import statistics
from abc import ABC, abstractmethod
from functools import partial
from operator import itemgetter
from typing import Any, List, Optional

import colorama
from annet.annlib.command import Command, CommandList, Question  # noqa: F401


class CommandResult(ABC):
    @abstractmethod
    def get_out(self) -> str:
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


class DeferredFileWrite:
    def __init__(self, file, mode="r"):
        self._file = file
        wrapper = {"w": "a", "wb": "ab"}
        if mode in wrapper:
            self._mode = wrapper[mode]
        else:
            raise Exception()

    def write(self, data):
        with open(self._file, self._mode, encoding="utf-8") as fh:
            fh.write(data)

    def close(self):
        pass

    def flush(self):
        pass
