"""Test the public context-preparation command, not its implementation helpers."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


def test_context_excludes_untracked_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(HERE, repo / "docker", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (repo / "annet").mkdir()
    (repo / "annet/__init__.py").write_text("# tracked\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "add", "annet/__init__.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
        cwd=repo,
        check=True,
    )
    (repo / "annet/secret.py").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    (repo / "private-key").write_text("TEST_SECRET_NOT_FOR_IMAGE\n")
    target = tmp_path / "context"
    subprocess.run([sys.executable, str(repo / "docker/prepare.py"), str(target)], check=True)
    assert (target / "annet/annet/__init__.py").exists()
    assert not (target / "annet/annet/secret.py").exists()
    assert not (target / "private-key").exists()
    assert not any("TEST_SECRET_NOT_FOR_IMAGE" in p.read_text() for p in target.rglob("*") if p.is_file())
    metadata = json.loads((target / "versions.json").read_text())
    assert metadata["gnetcli"]["revision"] == json.loads((HERE / "sources.json").read_text())["gnetcli"]["revision"]
    assert not (target / "patches").exists()
    assert not metadata["annet_worktree_changes"]
    result = subprocess.run([sys.executable, str(repo / "docker/prepare.py"), str(target)], capture_output=True)
    assert result.returncode != 0  # Never overwrite an existing context.

    selected = json.loads((HERE / "sources.json").read_text())
    selected["gnetcli"]["revision"] = "a" * 40
    override = tmp_path / "sources.json"
    override.write_text(json.dumps(selected))
    custom = tmp_path / "custom-context"
    subprocess.run(
        [sys.executable, str(repo / "docker/prepare.py"), str(custom), "--sources", str(override)], check=True
    )
    assert json.loads((custom / "sources.json").read_text()) == selected
    assert json.loads((custom / "versions.json").read_text())["gnetcli"] == selected["gnetcli"]
    assert json.loads((repo / "docker/sources.json").read_text())["gnetcli"]["revision"] != "a" * 40
