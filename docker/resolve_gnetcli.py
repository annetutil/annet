#!/usr/bin/env python3
"""Resolve a Gnetcli release or commit into a per-build source manifest."""

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://api.github.com/repos/annetutil/gnetcli"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--version", default="latest", help="latest, a published stable release tag, or a full commit SHA"
    )
    args = parser.parse_args()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "annet-container-build"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + token

    def get_json(path: str) -> dict[str, Any]:
        request = urllib.request.Request(API + path, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            data: dict[str, Any] = json.load(response)
            return data

    tag = None
    if re.fullmatch(r"[0-9a-f]{40}", args.version):
        revision = args.version
    else:
        if args.version != "latest" and not re.fullmatch(r"v?\d+\.\d+\.\d+", args.version):
            raise ValueError("Expected latest, a stable release tag, or a full commit SHA")
        endpoint = (
            "/releases/latest"
            if args.version == "latest"
            else "/releases/tags/" + urllib.parse.quote(args.version, safe="")
        )
        release = get_json(endpoint)
        tag = release["tag_name"]
        if release["draft"] or release["prerelease"] or not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
            raise ValueError("Expected a published stable Gnetcli release with a semantic version tag")
        # target_commitish can be a moving branch. Resolve the tag to its exact commit.
        revision = get_json("/commits/" + urllib.parse.quote(tag, safe=""))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid Gnetcli commit SHA")
    url = "https://codeload.github.com/annetutil/gnetcli/tar.gz/" + revision
    # Never send the API token to the archive endpoint.
    with urllib.request.urlopen(url, timeout=120) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
    sources = {}
    sources["gnetcli"] = {
        "revision": revision,
        "url": url,
        "sha256": digest,
    }
    if tag is not None:
        sources["gnetcli"]["release"] = tag
    args.output.write_text(json.dumps(sources, indent=2) + "\n")
    print(f"Gnetcli {tag or 'commit'}: {revision} (archive sha256:{digest})")


if __name__ == "__main__":
    main()
