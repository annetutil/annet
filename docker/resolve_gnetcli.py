#!/usr/bin/env python3
"""Resolve the latest published Gnetcli release into a per-build source manifest."""

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


API = "https://api.github.com/repos/annetutil/gnetcli"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "annet-container-build"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + token

    def get_json(path):
        request = urllib.request.Request(API + path, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    release = get_json("/releases/latest")
    tag = release["tag_name"]
    version = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag)
    if release["draft"] or release["prerelease"] or not version:
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
        "release": tag,
    }
    args.output.write_text(json.dumps(sources, indent=2) + "\n")
    print(f"Gnetcli {tag}: {revision} (archive sha256:{digest})")


if __name__ == "__main__":
    main()
