from annet.annlib.rbparser.syntax import get_row_and_raw_params
from annet.lib import uniq
from tests.annet.patch_data import get_samples


class TestRulebookNotFoundError(Exception):
    pass


def check_rulebook_equal(getting_rb, expected_rb):
    getting_data = get_rulebook_data(getting_rb)
    expected_data = get_rulebook_data(expected_rb)
    for row in uniq(getting_data.keys(), expected_data.keys()):
        assert row in getting_data and row in expected_data, f"Rule '{row}': rule missing in one of the rulebooks."
        assert getting_data[row]["scope"] == expected_data[row]["scope"], f"Rule '{row}': scopes do not match."
        assert getting_data[row]["params"] == expected_data[row]["params"], f"Rule '{row}': params do not match."
        assert getting_data[row]["rules"]["type"] == expected_data[row]["rules"]["type"], (
            f"Rule '{row}': type do not match."
        )
        assert getting_data[row]["rules"]["attrs"] == expected_data[row]["rules"]["attrs"], (
            f"Rule '{row}': attrs do not match."
        )
        inherited_children = getting_data[row]["rules"]["children"]
        expected_children = expected_data[row]["rules"]["children"]
        assert type(inherited_children) == type(expected_children), f"Rule '{row}': children types do not match."
        if inherited_children is None:
            continue
        check_rulebook_equal(inherited_children, expected_children)


def get_rulebook_data(rulebook):
    data = {}
    for scope in ["local", "global"]:
        for raw_row, rules in rulebook[scope].items():
            row, params = get_row_and_raw_params(raw_row)
            data[row] = {
                "params": params,
                "rules": rules,
                "scope": scope,
            }
    return data


def get_tests_data(test_dir):
    for file, data in get_samples(test_dir):
        for test_case, rulebooks in data.items():
            yield file, test_case, rulebooks


def mock_get_raw_rulebook_text(rulebooks):
    def get_rulebook(rulebook_path: str, extension: str):
        if rulebook_path not in rulebooks:
            raise TestRulebookNotFoundError(f"Mock file not found: {rulebook_path}")
        return rulebooks[rulebook_path]

    return get_rulebook
