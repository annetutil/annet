from collections import OrderedDict
from typing import Any

from annet.annlib.types import OpType
from annet.rulebook.juniper import default_diff


def level2_interface_diff(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[OpType, ...],
) -> Any:
    """
    Блок:
        protocols
            isis
                interface ae0.0
                    level 2
                        metric 20
                        post-convergence-lfa
    ```
    Но коробка может отдать `level 2 metric 20`, если терм один
    При расчете дифа если видим, что начинается с level 2, руками level 2 превращаем в блок
    """

    updated_old: OrderedDict[str, Any] = OrderedDict()
    for k, v in old.items():
        items = list(map(str.strip, k.split(" ")))

        if len(items) > 2 and items[0] == "level" and items[1] == "2":
            if "level 2" in diff_pre and "subtree" in diff_pre["level 2"] and k in diff_pre:
                key = " ".join(items[2:])
                updated_old.setdefault("level 2", OrderedDict())[key] = OrderedDict()
                diff_pre["level 2"]["subtree"][key] = diff_pre[k]
                diff_pre["level 2"]["subtree"][key]["match"]["attrs"]["reverse"] = f"delete {key}"
            else:
                return default_diff(old, new, diff_pre, _pops)
        else:
            updated_old[k] = v

    return default_diff(updated_old, new, diff_pre, _pops)


def syslog_archive_diff(
    old: OrderedDict[str, Any],
    new: OrderedDict[str, Any],
    diff_pre: OrderedDict[str, Any],
    _pops: tuple[OpType, ...],
) -> Any:
    """
    Блок:
    ```
    archive
        size 10m
        files 10
        world-readable
    ```
    Но коробка может отдать `archive size 10m files 10 world-readable`
    При расчете дифа если видим, что слева archive в одну строку, а справа нет, то справа схлопываем блок
    """

    for k, v in old.items():
        if k.startswith("archive") and not v and "archive" in new and new["archive"]:
            items = new.pop("archive")
            key = " ".join(["archive", *items.keys()])

            new[key] = OrderedDict()
            diff_pre[key] = diff_pre.pop("archive")

    return default_diff(old, new, diff_pre, _pops)
