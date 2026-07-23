from __future__ import annotations

from typing import Any, cast
from annet import patching, rulebook
from annet.annlib.netdev.views.hardware import HardwareView
from annet.hardware import hardware_connector
from annet.reference import RefTracker
from annet.types import Op
from annet.vendors import registry_connector, tabparser

DEFAULT_INDENT = "  "


def patch_from_pre(
    pre: Any,
    hw: HardwareView,
    rb: Any,
    add_comments: bool,
    ref_track: RefTracker | None = None,
    do_commit: bool = True,
) -> patching.PatchTree:
    if not ref_track:
        ref_track = RefTracker()
    orderer = patching.Orderer(rb["ordering"], cast(str, hw.vendor))
    orderer.ref_insert(ref_track)
    return patching.make_patch(
        pre=pre,
        rb=rb,
        hw=hw,
        add_comments=add_comments,
        orderer=orderer,
        do_commit=do_commit,
    )


def guess_hw(config_text: str) -> tuple[HardwareView, float]:
    """Пытаемся угадать вендора и hw на основе
    текста конфига и annet/rulebook/texts/*.rul"""
    scores = []
    hw_provider = hardware_connector.get()
    vendor_registry = registry_connector.get()
    for vendor in vendor_registry:
        hw = hw_provider.vendor_to_hw(vendor)
        rb = rulebook.get_rulebook(hw)
        fmtr = vendor_registry[vendor].make_formatter()

        try:
            config = tabparser.parse_to_tree(config_text, fmtr.split)
        except Exception:
            continue

        pre = patching.make_pre(patching.make_diff({}, config, rb, []))
        metric = _count_pre_score(pre)
        scores.append((hw, metric))

    if not scores:
        raise RuntimeError("No formatter was guessed")

    scores.sort(key=lambda x: (x[1], x[0].vendor), reverse=True)
    return scores[0]


def _count_pre_score(top_pre: dict[str, Any]) -> float:
    """Обходим вширь pre-конфиг
    и подсчитываем количество заматчившихся
    правил на каждом из уровней.

    Чем больше результирующий приоритет
    тем больше рулбук соответсвует конфигу.
    """
    score = 0
    scores = []
    cur, child = [top_pre], []
    while cur:
        for pre in cur.pop().values():
            score += 1
            for item in pre["items"].values():
                for op in [Op.ADDED, Op.AFFECTED, Op.REMOVED]:
                    child += [x["children"] for x in item[op]]
        if not cur:
            scores.append(score)
            score = 0
            cur, child = child, []
    result = 0
    for i in reversed(scores):
        result <<= i.bit_length()
        result += i
    if result > 0:
        return 1.0 - (1 / result)
    return float(result)
