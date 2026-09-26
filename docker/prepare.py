#!/usr/bin/env python3
"""Prepare a small build context without copying checkout sources or secrets."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--sources", type=Path, help="Reuse a generated Gnetcli manifest; otherwise resolve latest release"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    args.destination.mkdir(parents=True, exist_ok=False)
    for name in ["Dockerfile", "fetch_sources.py", "requirements.in"]:
        shutil.copyfile(root / name, args.destination / name)
    sources_path = args.destination / "sources.json"
    if args.sources:
        shutil.copyfile(args.sources, sources_path)
    else:
        subprocess.run([sys.executable, str(root / "resolve_gnetcli.py"), str(sources_path)], check=True)
    versions = json.loads(sources_path.read_text())
    (args.destination / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")


if __name__ == "__main__":
    main()
