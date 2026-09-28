"""Exercise project initialization through the public Annet CLI."""

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def source_environment(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(ROOT))


def run_init(work, *args, **kwargs):
    return subprocess.run(
        [sys.executable, "-m", "annet.annet", "init", *args],
        cwd=work,
        input="",
        capture_output=True,
        text=True,
        timeout=10,
        **kwargs,
    )


def test_file_init(tmp_path):
    result = run_init(tmp_path, "--storage", "file")
    assert result.returncode == 0, result.stderr
    config = yaml.safe_load((tmp_path / "context.yml").read_text())
    assert config["storage"]["default"] == {"adapter": "file", "params": {"path": "./inventory.yml"}}
    assert config["generators"]["default"] == ["generators/__init__.py"]
    assert (tmp_path / "generators/__init__.py").is_file()
    assert (tmp_path / "inventory.yml").is_file()
    assert (tmp_path / "context.yml").stat().st_mode & 0o777 == 0o600


def test_netbox_init(tmp_path):
    token = 'test-token: "quoted"\nnext-line'
    env = dict(os.environ, NETBOX_TOKEN=token)
    result = run_init(tmp_path, "--storage", "netbox", "--netbox-url", "https://netbox.test", env=env)
    assert result.returncode == 0, result.stderr
    config = yaml.safe_load((tmp_path / "context.yml").read_text())
    assert config["storage"]["default"] == {
        "adapter": "netbox",
        "params": {"url": "https://netbox.test", "token": token},
    }
    assert not (tmp_path / "inventory.yml").exists()
    assert token not in result.stdout + result.stderr
    assert (tmp_path / "context.yml").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("path", ["context.yml", "inventory.yml", "generators"])
@pytest.mark.parametrize("symlink", [False, True])
def test_refuse_existing_paths(tmp_path, path, symlink):
    existing = tmp_path / path
    if symlink:
        existing.symlink_to(tmp_path / "missing")
    else:
        existing.write_text("preserve me")
    result = run_init(tmp_path, "--storage", "file")
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert list(tmp_path.iterdir()) == [existing]
    if symlink:
        assert existing.is_symlink()
    else:
        assert existing.read_text() == "preserve me"


@pytest.mark.parametrize("args", [[], ["--storage", "invalid"], ["--storage", "file", "--netbox-url", "url"]])
def test_invalid_arguments_leave_no_files(tmp_path, args):
    assert run_init(tmp_path, *args).returncode != 0
    assert not list(tmp_path.iterdir())


def test_init_help(tmp_path):
    assert run_init(tmp_path, "--help").returncode == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("storage", ["file", "netbox"])
def test_interactive_init(tmp_path, storage):
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "annet.annet", "init"],
        cwd=tmp_path,
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    transcript = b""

    def answer(prompt, value):
        nonlocal transcript
        deadline = time.monotonic() + 10
        while prompt not in transcript:
            assert time.monotonic() < deadline, transcript
            if select.select([master], [], [], 0.1)[0]:
                transcript += os.read(master, 4096)
        os.write(master, value + b"\n")

    try:
        answer(b"Device source", storage.encode())
        if storage == "netbox":
            answer(b"NetBox URL", b"https://netbox.test")
            answer(b"NetBox token", b"secret-test-token")
        assert process.wait(timeout=10) == 0
        while select.select([master], [], [], 0)[0]:
            transcript += os.read(master, 4096)
        assert b"secret-test-token" not in transcript
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(slave)
        os.close(master)
    config = yaml.safe_load((tmp_path / "context.yml").read_text())
    assert config["storage"]["default"]["adapter"] == storage
    if storage == "netbox":
        assert config["storage"]["default"]["params"]["token"] == "secret-test-token"


def test_generate_from_initialized_project(tmp_path):
    result = run_init(tmp_path, "--storage", "file")
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [sys.executable, "-m", "annet.annet", "gen", "switch.example.test"],
        cwd=tmp_path,
        env=dict(os.environ, ANN_CONTEXT_CONFIG_PATH=str(tmp_path / "context.yml")),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "description Managed by Annet quick start" in result.stdout
