"""Download and verify the exact source archives used for binaries and wheels."""

import argparse
import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("/sources"))
output = parser.parse_args().output
sources = json.loads(Path("sources.json").read_text())
for name in ("gnetcli", "gnetcli_adapter"):
    source = sources[name]
    data = urllib.request.urlopen(source["url"], timeout=120).read()
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(f"Checksum mismatch: {name}")
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        # Some upstream archives contain absolute test-output symlinks.
        # Only regular files/directories are needed for binary/wheel builds.
        archive.extractall(output, members=(m for m in archive if m.isfile() or m.isdir()), filter="data")
    (output / (name + "-" + source["revision"])).rename(output / name)

# Materialize the SDK's safe in-repository proto link, without archive links.

shutil.copytree(output / "gnetcli/pkg/server/proto", output / "gnetcli/grpc_sdk/python/gnetclisdk/proto")
