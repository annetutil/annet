import functools
import json
import re
from os import path
from typing import Any, Dict

from annet.annlib.netdev.db import find_true_sequences, get_db


@functools.lru_cache(None)
def parse_hw_model(hw_model):
    prepared = _prepare_db()
    (tree, all_sequences) = get_db(prepared)
    true_sequences = find_true_sequences(hw_model, tree)
    return (
        sorted(true_sequences),
        all_sequences.difference(true_sequences),
    )


def _prepare_db() -> Dict[str, Any]:
    try:
        from library.python import resource
        raw = json.loads(resource.resfs_read("contrib/python/annet/annet/annlib/netdev/devdb/data/devdb.json").decode("utf-8"))
    except ImportError:
        with open(path.join(path.dirname(__file__), "data", "devdb.json"), "r") as f:
            raw = json.load(f)
    return {tuple(seq.split(".")): re.compile(regexp) for (seq, regexp) in raw.items()}
