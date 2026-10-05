"""Check that local files are excluded from the actual Docker build context."""

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
    for name in (".dockerignore", "requirements.in", "resolve_gnetcli.py", "fetch_sources.py"):
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
    }
