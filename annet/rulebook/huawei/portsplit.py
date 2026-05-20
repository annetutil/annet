import re
from collections import defaultdict
from collections.abc import Iterable
from itertools import groupby

from annet.annlib.types import Op
from annet.rulebook import common


def _groupby_sorted(iterable, *, key):
    return groupby(sorted(iterable, key=key), key=key)


def _remove_comments(row: str) -> str:
    # FIXME: dirty workaround for the issue described in NOCDEV-21151, it should eventually be removed
    # NOTE: it is observed for comments to be here only in `ann file-diff`
    return row.partition("!!")[0]


def _parse_port_split_args(args: str) -> tuple[set[tuple[str, int]], str]:
    """
    Parses `port split dimension interface` command.
    Returns `split-type` argument if there was any, and the set of interfaces on which split is performed.

    Huawei's documentation (for NE40E-M2):
        https://support.huawei.com/hedex/hdx.do?docid=EDOC1100512787&id=EN-US_CLIREF_0000002330666798
    """

    # `split-type` is expected to be the last argument
    if m := re.search(r"\s+split-type\s+([^\s]+)$", args.strip()):
        args = args[: -len(m[0])]
        split_type = m[1]
    else:
        split_type = ""

    ifaces = set()
    while args := args.strip():
        # match either just, e.g., `100GE1/0/10`, or `100GE1/0/17 to 100GE1/0/24`
        #  m["prefix"]: "100GE1/0/"
        #  m["start"]: "10" / "17"
        #  m["end"]: None / "24"
        m = re.match(
            r"(?P<prefix>\d+(?:\|\d+)*GE\s*\d+/\d+/)(?P<start>\d+)(?:\s+to\s+(?P=prefix)(?P<end>\d+))?",
            args,
            flags=re.IGNORECASE,
        )
        if m is None:
            # match is performed only on the start of `r`, so if there is garbage, we'll catch it here
            raise ValueError(f"Invalid port split definition: {args!r}")
        args = args[m.end() :]  # remove found interface/range specification

        prefix = m["prefix"]
        start = int(m["start"])
        if m["end"] is None:
            ifaces.add((prefix, start))
        else:
            end = int(m["end"])
            ifaces.update(((prefix, i) for i in range(start, end + 1)))

    return ifaces, split_type


def _unparse_port_split_args(ifaces: Iterable[tuple[str, int]], *, split_type: str) -> str:
    """
    Unparses input into `port split dimension interface` command.
    If a list of interfaces can be converted to a range, it will be converted to it.
    """

    parts = []
    for prefix, gen in groupby(sorted(ifaces), key=lambda x: x[0]):
        _, last_num = next(gen)
        cur_range_start = last_num
        parts.append(f"{prefix}{last_num}")
        for _, num in gen:
            if num != last_num + 1:
                # outside of current range
                parts.append(f"{prefix}{num}")
                cur_range_start = num
            elif num - cur_range_start <= 1:
                # too small a difference to make a range
                # e.g., `100GE1/0/10`, `100GE1/0/11`
                parts.append(f"{prefix}{num}")
            else:
                # update range end (or convert to a range)
                # e.g., `100GE1/0/10`, `to 100GE1/0/12`
                parts[-1] = f"to {prefix}{num}"
            last_num = num

    result = " ".join(parts)
    if split_type:
        result += f" split-type {split_type}"

    return result


def port_split_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
    # pylint: disable=unused-argument

    old_row_by_iface = {}
    old_ifaces_by_type = defaultdict(set)
    for row in old:
        (row_args,) = diff_pre[row]["match"]["key"]
        ifaces, split_type = _parse_port_split_args(_remove_comments(row_args))
        old_ifaces_by_type[split_type].update(ifaces)
        for iface in ifaces:
            old_row_by_iface[iface] = row

    new_row_by_iface = {}
    new_ifaces_by_type = defaultdict(set)
    for row in new:
        (row_args,) = diff_pre[row]["match"]["key"]
        ifaces, split_type = _parse_port_split_args(_remove_comments(row_args))
        new_ifaces_by_type[split_type].update(ifaces)
        for iface in ifaces:
            if iface in new_row_by_iface:
                raise ValueError(f"Multiple split types defined for interface {iface[0]}{iface[1]}")
            new_row_by_iface[iface] = row

    for split_type in old_ifaces_by_type.keys():
        if removed := old_ifaces_by_type[split_type] - new_ifaces_by_type[split_type]:
            for orig_row, ifaces in _groupby_sorted(removed, key=lambda x: old_row_by_iface[x]):
                args = _unparse_port_split_args(ifaces, split_type=split_type)
                yield common.DiffItem(
                    Op.REMOVED,
                    f"port split dimension interface {args}",
                    [],
                    {**diff_pre[orig_row]["match"], "key": (args,)},
                )

    for split_type in new_ifaces_by_type.keys():
        if added := new_ifaces_by_type[split_type] - old_ifaces_by_type[split_type]:
            for orig_row, ifaces in _groupby_sorted(added, key=lambda x: new_row_by_iface[x]):
                args = _unparse_port_split_args(ifaces, split_type=split_type)
                yield common.DiffItem(
                    Op.ADDED,
                    f"port split dimension interface {args}",
                    [],
                    {**diff_pre[orig_row]["match"], "key": (args,)},
                )


def port_split(rule, key, diff, hw, **_):
    yield from common.default(rule, key, diff)
    if not hw.Huawei.NE and not hw.Huawei.CE.CE8800.CE8875 and not hw.Huawei.CE.CE8800.CE8851:
        # some devices require `port split refresh`, some do not
        # examples of the devices which do not:
        # * NE8000E-F2C
        #   (reference: https://support.huawei.com/hedex/hdx.do?docid=EDOC1100408233&id=EN-US_CLIREF_0000002370625224)
        # * CE8875-24BQ8DQ
        #   (reference: https://support.huawei.com/hedex/hdx.do?docid=EDOC1100512869&id=EN-US_CLIREF_0000002188920737)
        # * CE8851-32CQ8DQ (NOCREQUESTS-90489)
        if diff[Op.ADDED] or diff[Op.REMOVED]:
            yield (True, "port split refresh", None)
