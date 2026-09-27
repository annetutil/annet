"""Exercise the resolver's CLI with a fake GitHub API, without live releases."""

import hashlib
import io
import json
import runpy
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "resolve_gnetcli.py"
API = "https://api.github.com/repos/annetutil/gnetcli"


def invoke(monkeypatch, tmp_path, release=None, revision="a" * 40, failure=False, version="latest"):
    output = tmp_path / "selected.json"
    calls = []
    if release is None:
        release = {"tag_name": "v1.3.15", "draft": False, "prerelease": False, "target_commitish": "main"}

    def urlopen(request, timeout):
        url = request.full_url if isinstance(request, urllib.request.Request) else request
        calls.append(url)
        if failure:
            raise urllib.error.HTTPError(url, 503, "Unavailable", {}, None)
        if url.startswith(API):
            assert request.get_header("Authorization") == "Bearer test-token"
        else:
            assert isinstance(request, str)  # No authentication headers on codeload.
        if url in (API + "/releases/latest", API + "/releases/tags/" + release["tag_name"]):
            return io.BytesIO(json.dumps(release).encode())
        if url == API + "/commits/" + release["tag_name"]:
            return io.BytesIO(json.dumps({"sha": revision}).encode())
        assert url == "https://codeload.github.com/annetutil/gnetcli/tar.gz/" + revision
        return io.BytesIO(b"source archive")

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(output), "--version", version])
    try:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    finally:
        assert not SCRIPT.with_name("sources.json").exists()
    return json.loads(output.read_text()), calls


def test_latest_release_manifest(monkeypatch, tmp_path):
    selected, calls = invoke(monkeypatch, tmp_path)
    source = selected["gnetcli"]
    assert source["revision"] == "a" * 40
    assert source["release"] == "v1.3.15"
    assert source["sha256"] == hashlib.sha256(b"source archive").hexdigest()
    assert len(calls) == 3
    assert calls[1].endswith("/commits/v1.3.15")  # Never resolve the moving target_commitish.
    assert set(selected) == {"gnetcli"}


@pytest.mark.parametrize("field,value", [("draft", True), ("prerelease", True), ("tag_name", "invalid")])
def test_reject_non_release(monkeypatch, tmp_path, field, value):
    release = {"tag_name": "v1.3.15", "draft": False, "prerelease": False, field: value}
    with pytest.raises(ValueError):
        invoke(monkeypatch, tmp_path, release=release)
    assert not (tmp_path / "selected.json").exists()


def test_reject_invalid_commit(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="commit SHA"):
        invoke(monkeypatch, tmp_path, revision="main")
    assert not (tmp_path / "selected.json").exists()


def test_api_failure_has_no_fallback(monkeypatch, tmp_path):
    with pytest.raises(urllib.error.HTTPError):
        invoke(monkeypatch, tmp_path, failure=True)
    assert not (tmp_path / "selected.json").exists()


def test_explicit_release(monkeypatch, tmp_path):
    selected, calls = invoke(monkeypatch, tmp_path, version="v1.3.15")
    assert selected["gnetcli"]["release"] == "v1.3.15"
    assert calls[0] == API + "/releases/tags/v1.3.15"
    assert API + "/releases/latest" not in calls


def test_ci_commit_does_not_resolve_latest_again(monkeypatch, tmp_path):
    selected, calls = invoke(monkeypatch, tmp_path, version="a" * 40)
    assert selected["gnetcli"]["revision"] == "a" * 40
    assert "release" not in selected["gnetcli"]
    assert calls == ["https://codeload.github.com/annetutil/gnetcli/tar.gz/" + "a" * 40]


@pytest.mark.parametrize("version", ["main", "", "v1.3.15-rc1", "../main"])
def test_reject_moving_or_invalid_reference(monkeypatch, tmp_path, version):
    with pytest.raises(ValueError, match="Expected latest"):
        invoke(monkeypatch, tmp_path, version=version)
    assert not (tmp_path / "selected.json").exists()
