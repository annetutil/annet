# ruff: noqa: T201
import itertools
import json
import operator

import tabulate  #  type: ignore[import-untyped]
from adaptix import Retort

from annet.runner.protocols import ShowGenInfo

retort = Retort()


def print_json(output_data: list[ShowGenInfo]) -> None:
    print(json.dumps(retort.dump(output_data, list[ShowGenInfo])))


def _gen_sort_key(gen: ShowGenInfo) -> tuple[int, str, str]:
    if gen.type == "PARTIAL":
        return 0, gen.type, gen.name
    if gen.type == "JSON_FRAGMENT":
        return 1, gen.type, gen.name
    if gen.type == "ENTIRE":
        return 2, gen.type, gen.name
    return 3, gen.type, gen.name


def print_text(output_data: list[ShowGenInfo]) -> None:
    output_data = sorted(output_data, key=_gen_sort_key)
    for gen_type, gens in itertools.groupby(output_data, operator.attrgetter("type")):
        print(
            tabulate.tabulate(
                [(g.name, ", ".join(g.tags), g.module, g.description) for g in gens],
                [f"{gen_type}-Class", "Tags", "Module", "Description"],
                tablefmt="orgtbl",
            ),
        )
        print()
