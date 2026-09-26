"""Exercise the build-context command without downloading live releases."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("override", [False, True])
def test_context_contains_only_build_assets(tmp_path, override):
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(HERE, repo / "docker", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    # Neither checkout sources nor local secrets belong in a PyPI-based image.
    (repo / "annet").mkdir()
    (repo / "annet/__init__.py").write_text("# checkout source, not used\n")
    (repo / "annet/secret.py").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    (repo / "private-key").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    selected = {"gnetcli": {"revision": "a" * 40, "release": "v1.3.15"}}
    # Stub only the external release lookup, not prepare.py itself.
    (repo / "docker/resolve_gnetcli.py").write_text(
        f"import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text({json.dumps(selected)!r})\n"
    )
    target = tmp_path / "context"
    args = [sys.executable, str(repo / "docker/prepare.py"), str(target)]
    if override:
        manifest = tmp_path / "selected.json"
        manifest.write_text(json.dumps(selected))
        args += ["--sources", str(manifest)]
    subprocess.run(args, check=True)
    assert {p.name for p in target.iterdir()} == {
        "Dockerfile",
        "fetch_sources.py",
        "requirements.in",
        "sources.json",
        "versions.json",
    }
    assert json.loads((target / "sources.json").read_text()) == selected
    assert json.loads((target / "versions.json").read_text()) == selected
    assert not any("TEST_SECRET_NOT_FOR_IMAGE" in p.read_text() for p in target.iterdir())
    result = subprocess.run(args, capture_output=True)
    assert result.returncode != 0  # Never overwrite an existing context.


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
