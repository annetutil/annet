#!/usr/bin/env python3
"""Create an allowlisted Docker context; never send the working tree to Docker."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.destination.mkdir(parents=True, exist_ok=False)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    for name in tracked:
        if not name or not (
            name.startswith(("annet/", "annet_generators/"))
            or name in {"setup.py", "pyproject.toml", "requirements.txt", "MANIFEST.in", "README.md", "LICENSE"}
        ):
            continue
        src = root / name
        if src.is_symlink():
            raise ValueError(f"Refusing symlink: {name}")
        dst = args.destination / "annet" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    for name in ["Dockerfile", "sources.json", "fetch_sources.py", "requirements.lock", "build.lock"]:
        shutil.copyfile(root / "docker" / name, args.destination / name)
    versions = json.loads((root / "docker/sources.json").read_text())
    versions["annet_revision"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    versions["annet_worktree_changes"] = bool(
        subprocess.check_output(
            ["git", "diff", "HEAD", "--", "annet", "annet_generators", "setup.py", "requirements.txt"], cwd=root
        )
    )
    (args.destination / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")


if __name__ == "__main__":
    main()
