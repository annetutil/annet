import os

import pytest
from annet.lib import add_context_extension


@pytest.fixture
def mock_home_directory(tmp_path, monkeypatch):
    def mock_expanduser(path):
        if path.startswith("~"):
            return str(tmp_path) + path[1:]
        return path
    
    monkeypatch.setattr(os.path, "expanduser", mock_expanduser)
    return tmp_path


def test_add_context_extension_no_files_exist(tmp_path):
    base_path = str(tmp_path / "context")
    result = add_context_extension(base_path, ".yml", ".yaml")
    assert result == base_path + ".yml"


def test_add_context_extension_default_exists(tmp_path):
    base_path = tmp_path / "context"
    default_path = base_path.with_suffix(".yml")
    default_path.touch()
    
    result = add_context_extension(base_path, ".yml", ".yaml")
    assert result == str(default_path)


def test_add_context_extension_check_exists(tmp_path):
    base_path = tmp_path / "context"
    check_file = base_path.with_suffix(".yml")
    check_file.touch()

    result = add_context_extension(base_path, ".yml", ".json", ".yaml", ".toml")
    assert result == str(check_file)


def test_add_context_extension_multiple_files(tmp_path):
    base_path = tmp_path / "context"
    yml_file = base_path.with_suffix(".yml")
    yaml_file = base_path.with_suffix(".yaml")
    yml_file.touch()
    yaml_file.touch()

    with pytest.raises(ValueError) as exc_info:
        add_context_extension(base_path, ".yml", ".yaml")

    assert "Multiple context files found" in str(exc_info.value)
    assert str(yml_file) in str(exc_info.value)
    assert str(yaml_file) in str(exc_info.value)
