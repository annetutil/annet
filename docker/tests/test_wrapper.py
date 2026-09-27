"""Exercise the shell wrapper with a recording Docker executable."""

import json
import os
import pty
import subprocess
import sys
from pathlib import Path

import pytest


WRAPPER = Path(__file__).resolve().parents[1] / "annet-docker"


@pytest.fixture
def runner(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['DOCKER_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
        "sys.exit(int(os.environ.get('DOCKER_STATUS', '0')))\n"
    )
    docker.chmod(0o755)
    workdir = tmp_path / "project with spaces"
    workdir.mkdir()
    log = tmp_path / "args.json"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", DOCKER_LOG=str(log), PWD=str(workdir))
    for name in ("ANNET_IMAGE", "ANNET_DOCKER_NETWORK", "DOCKER_STATUS"):
        env.pop(name, None)

    def run(args=(), overrides=None, interactive=False):
        run_env = dict(env, **(overrides or {}))
        if interactive:
            master, slave = pty.openpty()
            try:
                result = subprocess.run(
                    [str(WRAPPER), *args],
                    cwd=workdir,
                    env=run_env,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    timeout=10,
                )
            finally:
                os.close(slave)
                os.close(master)
        else:
            result = subprocess.run(
                [str(WRAPPER), *args],
                cwd=workdir,
                env=run_env,
                input="",
                capture_output=True,
                text=True,
                timeout=10,
            )
        return result.returncode, json.loads(log.read_text()), workdir

    return run


def test_defaults(runner):
    status, args, workdir = runner()
    assert status == 0
    assert args == [
        "run",
        "--rm",
        "--init",
        "-i",
        "--network",
        "host",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        "HOME=/tmp",
        "--mount",
        f"type=bind,src={workdir},dst=/work",
        "--workdir",
        "/work",
        "ghcr.io/annetutil/annet:latest",
        "--help",
    ]


@pytest.mark.parametrize("command", ["gen", "diff", "deploy"])
def test_arguments_and_overrides(runner, command):
    forwarded = [command, "switch.example.test", "argument with spaces", "", "$(false)", "*"]
    status, args, _ = runner(forwarded, {"ANNET_IMAGE": "annet:local", "ANNET_DOCKER_NETWORK": "bridge"})
    assert status == 0
    assert args[args.index("--network") + 1] == "bridge"
    assert args[-len(forwarded) - 1 :] == ["annet:local", *forwarded]
    assert "-t" not in args


def test_exit_status(runner):
    status, _, _ = runner(["diff"], {"DOCKER_STATUS": "17"})
    assert status == 17


def test_interactive_tty(runner):
    status, args, _ = runner(["deploy", "switch.example.test"], interactive=True)
    assert status == 0
    assert args[-4:] == ["-t", "ghcr.io/annetutil/annet:latest", "deploy", "switch.example.test"]
