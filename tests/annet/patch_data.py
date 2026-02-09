import os
from collections import OrderedDict

import yaml

from annet.vendors import registry_connector, tabparser

from .. import get_test_data, get_test_data_list


def get_configs(hw, data):
    assert "patch" in data
    assert ("before" in data and "after" in data) ^ ("diff" in data)

    formatter = registry_connector.get().match(hw).make_formatter()
    splitter = formatter.split

    if "diff" in data:
        before, after = expand_diff(data["diff"], splitter)
    else:
        before, after = tuple(tabparser.parse_to_tree(text=data[k], splitter=splitter) for k in ["before", "after"])
    patch = data["patch"]

    return before, after, patch


def expand_diff(diff, splitter):
    def _process_node(node, deep=0, sign=0):
        ret1 = OrderedDict()
        ret2 = OrderedDict()
        for line, children in node.items():
            line = line.strip()
            line_sign = 0
            if line.startswith("-") or line.startswith("+"):
                line_sign = 1 if line[0] == "+" else -1
                line = line[1:].strip()
            assert sign == 0 or line_sign == sign

            sub1, sub2 = _process_node(children, deep + 1, line_sign)
            if line_sign != 1:
                ret1[line] = sub1
            if line_sign != -1:
                ret2[line] = sub2
        return (ret1, ret2)

    return _process_node(tabparser.parse_to_tree(text=diff, splitter=splitter))


def get_samples(dirname):
    for fname in get_test_data_list(dirname):
        if fname.endswith(".yaml"):
            file_data = yaml.load(
                get_test_data(os.path.join(dirname, fname)),
                Loader=yaml.BaseLoader,
            )
            if isinstance(file_data, list):
                for i, sample in enumerate(file_data, start=1):
                    key = fname
                    if "name" in sample:
                        key += " (%s)" % sample["name"]
                    else:
                        key += " #%d" % i
                    yield (key, sample)
            else:
                key = fname
                if "name" in file_data:
                    key += " (%s)" % file_data["name"]
                yield (key, file_data)
