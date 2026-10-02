"""Ensure PR CI tests the checkout and records the package it actually installed."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_pr_overlay_is_separate_from_publish_build():
    workflow = yaml.safe_load((ROOT / ".github/workflows/container.yml").read_text())
    steps = workflow["jobs"]["build"]["steps"]
    overlay = next(step for step in steps if step.get("name") == "Install checkout wheel in the PR test image")
    assert overlay["if"] == "github.event_name == 'pull_request'"
    assert 'VERSION="$version" python -m pip wheel --no-deps' in overlay["run"]
    assert 'version="$base_version+pr.$revision"' in overlay["run"]
    assert "docker/Dockerfile.pr" in overlay["run"]
    smoke = next(step for step in steps if step.get("name") == "Exercise quick start and container lifecycle")
    assert steps.index(overlay) < steps.index(smoke)
    assert "github.event_name == 'pull_request'" not in workflow["jobs"]["publish"]["if"]
    for step in steps:
        if step.get("name") == "Save the tested image for publishing":
            assert step["if"] == "github.event_name != 'pull_request'"


@pytest.mark.skipif(not os.environ.get("ANNET_TEST_REVISION"), reason="requires a checkout wheel image")
def test_pr_image_version_manifest():
    image = os.environ["ANNET_TEST_IMAGE"]
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "python",
            image,
            "-c",
            "import json, importlib.metadata as m; from pathlib import Path; "
            "print(json.dumps([m.version('annet'), json.loads(Path('/usr/local/share/annet/versions.json').read_text())]))",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    version, manifest = json.loads(result.stdout)
    assert version == os.environ["ANNET_TEST_VERSION"]
    assert manifest["packages"]["annet"] == version
    assert manifest["annet_checkout"] == os.environ["ANNET_TEST_REVISION"]
