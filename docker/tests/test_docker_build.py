"""Check Docker context filtering and the Annet version installation command."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("ANNET_TEST_IMAGE"), reason="Docker context checks require Docker")
def test_context_excludes_local_files(tmp_path):
    context = tmp_path / "context"
    context.mkdir()
    for name in (".dockerignore", "requirements.in", "resolve_gnetcli.py", "fetch_sources.py", "entrypoint.py"):
        shutil.copyfile(HERE / name, context / name)
    (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context/\n")
    (context / "secret.txt").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    shutil.copytree(HERE / "examples/quickstart", context / "examples/quickstart")
    (context / "examples/quickstart/secret.txt").write_text("TEST_SECRET_NOT_FOR_IMAGE")
    (context / "examples/config.yml").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    output = tmp_path / "output"
    subprocess.run(
        ["docker", "build", "--output", f"type=local,dest={output}", str(context)], check=True, capture_output=True
    )
    assert {str(p.relative_to(output / "context")) for p in (output / "context").rglob("*") if p.is_file()} == {
        "Dockerfile",
        "requirements.in",
        "resolve_gnetcli.py",
        "fetch_sources.py",
        "entrypoint.py",
        "examples/quickstart/context.yml",
        "examples/quickstart/inventory.yml",
        "examples/quickstart/generators/__init__.py",
    }


@pytest.mark.parametrize("version", ["", "4.6.1"])
@pytest.mark.parametrize("pip_status", [0, 7])
def test_annet_version_install_command(tmp_path, version, pip_status):
    # Run the actual Dockerfile shell instruction with a recording pip command.
    text = (HERE / "Dockerfile").read_text()
    install = "if [ -n " + text.split("RUN if [ -n ", 1)[1].split("\n\n", 1)[0]
    log = tmp_path / "pip-args"
    shell = 'pip() { printf "%s\\n" "$@" >> "$LOG"; return "$PIP_STATUS"; };\n' + install
    result = subprocess.run(
        ["sh", "-c", shell],
        env={"ANNET_VERSION": version, "LOG": str(log), "PIP_STATUS": str(pip_status)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == pip_status, result.stderr
    arguments = log.read_text().splitlines()
    assert arguments.count("install") == 1  # Failed exact version must not fall back to latest.
    assert ("annet[netbox]==4.6.1" in arguments) == bool(version)
    assert ("check" in arguments) == (pip_status == 0)
    requirements = (HERE / "requirements.in").read_text().splitlines()
    assert requirements == ["annet[netbox]", "gnetcli_adapter"]
