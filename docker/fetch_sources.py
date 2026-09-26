"""Download Gnetcli using the manifest resolved for this build (not checked into Git)."""

import argparse
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("/sources"))
output = parser.parse_args().output
source = json.loads(Path("sources.json").read_text())["gnetcli"]
with urllib.request.urlopen(source["url"], timeout=120) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != source["sha256"]:
    raise ValueError("Gnetcli archive changed since release resolution")
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    # Upstream archives can contain absolute test-output symlinks.
    archive.extractall(output, members=(m for m in archive if m.isfile() or m.isdir()), filter="data")
(output / ("gnetcli-" + source["revision"])).rename(output / "gnetcli")
