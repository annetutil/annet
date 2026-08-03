import functools
import json
import re
from pathlib import Path

from annet.annlib.netdev.db import find_true_sequences, get_db
from annet.annlib.netdev.devdb.generate_stubs import canonicalize_devdb_key
from annet.lib import get_context


@functools.lru_cache(None)
def parse_hw_model(hw_model: str) -> tuple[list[tuple[str, ...]], set[tuple[str, ...]]]:
    prepared = prepare_db()
    (tree, all_sequences) = get_db(prepared)
    true_sequences = find_true_sequences(hw_model, tree)
    return (
        sorted(true_sequences),
        all_sequences.difference(true_sequences),
    )


def prepare_raw_db() -> dict[str, str]:
    raw: dict[str, str]

    try:
        from library.python import resource

        raw = json.loads(
            resource.resfs_read("contrib/python/annet/annet/annlib/netdev/devdb/data/devdb.json").decode("utf-8")
        )
    except ImportError:
        devdb_file = Path(get_context().get("devdb", {}).get("path", Path(__file__).parent / "data" / "devdb.json"))
        with devdb_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    return raw


def prepare_db() -> dict[tuple[str, ...], re.Pattern[str]]:
    raw = prepare_raw_db()
    prepared: dict[tuple[str, ...], re.Pattern[str]] = {}

    for seq, regexp in raw.items():
        canonical = canonicalize_devdb_key(seq)
        if canonical in prepared:
            raise ValueError(f"duplicate canonical devdb key {'.'.join(canonical)!r}")
        prepared[canonical] = re.compile(regexp)

    return prepared
