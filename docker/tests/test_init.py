"""Verify project initialization in the installed image."""

import os
import subprocess

import pytest


@pytest.mark.skipif(not os.environ.get("ANNET_TEST_IMAGE"), reason="requires the Docker image")
@pytest.mark.parametrize("storage", ["file", "netbox"])
def test_image_init(tmp_path, storage):
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        "HOME=/tmp",
        "--mount",
        f"type=bind,src={tmp_path},dst=/work",
        os.environ["ANNET_TEST_IMAGE"],
    ]
    result = subprocess.run(command + ["init", "--storage", storage], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    config_path = tmp_path / "context.yml"
    content = config_path.read_text()
    assert config_path.stat().st_mode & 0o777 == 0o600
    assert config_path.stat().st_uid == os.getuid()
    if storage == "file":
        result = subprocess.run(command + ["gen", "switch.example.test"], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert "description Managed by Annet quick start" in result.stdout
    result = subprocess.run(command + ["init", "--storage", storage], capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert config_path.read_text() == content
