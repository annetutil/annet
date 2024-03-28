import re
from itertools import groupby
from typing import Generator, List, Mapping, Tuple, Union

from annet.annlib.diff import (  # pylint: disable=unused-import
    colorize_line,
    diff_cmp,
    diff_ops,
    gen_pre_as_diff,
    resort_diff,
)
from annet.annlib.output import format_file_diff

from annet import patching
from annet.cli_args import ShowDiffOptions
from annet.output import output_driver_connector
from annet.storage import Device
from annet.tabparser import make_formatter
from annet.types import Diff, PCDiff


# NOCDEV-1720


def gen_sort_diff(
    diffs: Mapping[Device, Union[Diff, PCDiff]], args: ShowDiffOptions
) -> Generator[Tuple[str, Generator[str, None, None], bool], None, None]:
    """
    Возвращает осортированный дифф, совместимый с write_output
    :param diffs: Маппинг устройства в дифф
    :param args: Параметры коммандной строки
    """
    if args.no_collapse:
        devices_to_diff = {(dev,): diff for dev, diff in diffs.items()}
    else:
        non_pc_diffs = {dev: diff for dev, diff in diffs.items() if not isinstance(diff, PCDiff)}
        devices_to_diff = collapse_diffs(non_pc_diffs)
        devices_to_diff.update({(dev,): diff for dev, diff in diffs.items() if isinstance(diff, PCDiff)})
    for devices, diff_obj in devices_to_diff.items():
        if not diff_obj:
            continue
        if isinstance(diff_obj, PCDiff):
            for diff_file in diff_obj.diff_files:
                diff_text = (
                    "\n".join(diff_file.diff_lines)
                    if args.no_color
                    else "\n".join(format_file_diff(diff_file.diff_lines))
                )
                yield diff_file.label, diff_text, False
        else:
            output_driver = output_driver_connector.get()
            dest_name = ", ".join([output_driver.cfg_file_names(dev)[0] for dev in devices])
            pd = patching.make_pre(resort_diff(diff_obj))
            yield dest_name, gen_pre_as_diff(pd, args.show_rules, args.indent, args.no_color), False


def _transform_text_diff_for_collapsing(text_diff) -> List[str]:
    for line_no, line in enumerate(text_diff):
        text_diff[line_no] = re.sub(r"(snmp-agent .+) cipher \S+ (.+)", r"\1 cipher ENCRYPTED \2", line)
    return text_diff


def _make_text_diff(device: Device, diff: Diff) -> List[str]:
    formatter = make_formatter(device.hw)
    res = formatter.diff(diff)
    return res


def collapse_diffs(diffs: Mapping[Device, Diff]) -> Mapping[Tuple[Device, ...], Diff]:
    """
    Группировка диффов.
    :param diffs:
    :return: дикт аналогичный типу Diff, но с несколькими dev в ключе.
        Нужно учесть что дифы сверяются в отформатированном виде
    """
    diffs_with_test = {dev: [diff, _transform_text_diff_for_collapsing(_make_text_diff(dev, diff))] for dev, diff in
                       diffs.items()}
    res = {}
    for _, collapsed_diff_iter in groupby(sorted(diffs_with_test.items(), key=lambda x: (x[0].hw.vendor, x[1][1])),
                                          key=lambda x: x[1][1]):
        collapsed_diff = list(collapsed_diff_iter)
        res[tuple(x[0] for x in collapsed_diff)] = collapsed_diff[0][1][0]

    return res
