from annet.annlib import yamltools
from annet.annlib.lib import merge_dicts


def test_dump_merged_dicts_as_mappings():
    config = merge_dicts(
        {"set": {"system": {"hostname": "leaf"}}},
        {"set": {"system": {"aaa": {"user": {}}}}},
    )

    assert yamltools.dump(config) == "set:\n  system:\n    hostname: leaf\n    aaa:\n      user: {}\n"
