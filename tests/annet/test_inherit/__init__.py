from annet.lib import uniq
from annet.rulebook.deploying import _get_rule_pre_merge as get_deploy_data
from annet.rulebook.patching import _get_pre_merge as get_patch_data
from tests.annet.patch_data import get_samples


class TestRulebookNotFoundError(Exception):
    pass


def check_patch_rulebook_equal(getting_rb, expected_rb):
    getting_data = get_patch_data(getting_rb)
    expected_data = get_patch_data(expected_rb)
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
        check_patch_rulebook_equal(inherited_children, expected_children)


def check_deploy_rulebook_equal(getting_rb, expected_rb):
    getting_data = get_deploy_data(getting_rb)
    expected_data = get_deploy_data(expected_rb)
    for row in uniq(expected_data, getting_data):
        assert row in getting_data and row in expected_data, f"Rule '{row}': rule missing in one of the rulebooks."
        getting_rule = getting_data[row]
        expected_rule = expected_data[row]
        assert getting_rule["params"] == expected_rule["params"], f"Rule '{row}': params do not match."
        getting_dialogs = getting_rule["rules"]["attrs"].pop("dialogs")
        expected_dialogs = expected_rule["rules"]["attrs"].pop("dialogs")
        assert getting_rule["rules"]["attrs"] == expected_rule["rules"]["attrs"], f"Rule '{row}': attrs do not match."
        for dialog in uniq(getting_dialogs, expected_dialogs):
            assert dialog in getting_dialogs and dialog in expected_dialogs, (
                f"Rule '{row}': dialog '{dialog}' missing in one of the rulebooks."
            )
        getting_rule["rules"]["attrs"]["dialogs"] = getting_dialogs
        expected_rule["rules"]["attrs"]["dialogs"] = expected_dialogs
        check_deploy_rulebook_equal(getting_rule["rules"]["children"], expected_rule["rules"]["children"])


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
