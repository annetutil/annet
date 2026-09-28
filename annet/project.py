"""Create a local project without accessing storage or network devices."""

import getpass
import os
import sys
from importlib.resources import files
from pathlib import Path

import yaml


TEMPLATE = files("annet") / "configs" / "project"


def init_project(storage: str | None = None, netbox_url: str | None = None) -> int:
    interactive = storage is None
    if interactive:
        if not sys.stdin.isatty():
            raise ValueError("use --storage file or --storage netbox when stdin is not a terminal")
        while storage not in ("file", "netbox"):
            storage = input("Device source [file/netbox] (file): ").strip().lower() or "file"
    if netbox_url and storage != "netbox":
        raise ValueError("--netbox-url requires --storage netbox")

    targets = [Path("context.yml"), Path("generators")]
    if storage == "file":
        targets.append(Path("inventory.yml"))
    for target in targets:
        if target.exists() or target.is_symlink():
            raise ValueError(f"refusing to overwrite {target}; use an empty project directory")

    config = yaml.safe_load((TEMPLATE / "context.yml").read_text())
    config["generators"]["default"] = ["generators/__init__.py"]
    if storage == "file":
        config["storage"]["default"]["params"]["path"] = "./inventory.yml"
    else:
        url = netbox_url or "https://netbox.example.test"
        token = os.environ.get("NETBOX_TOKEN", "REPLACE_ME")
        if interactive:
            url = netbox_url or input(f"NetBox URL ({url}): ").strip() or url
            token = getpass.getpass("NetBox token (empty to configure later): ") or "REPLACE_ME"
        config["storage"]["default"] = {"adapter": "netbox", "params": {"url": url, "token": token}}

    # Exclusive creation also protects against files appearing after the check.
    Path("generators").mkdir()
    with Path("generators/__init__.py").open("x") as stream:
        stream.write((TEMPLATE / "generator.py.txt").read_text())
    if storage == "file":
        with Path("inventory.yml").open("x") as stream:
            stream.write((TEMPLATE / "inventory.yml").read_text())
    fd = os.open("context.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    print("Created context.yml and generators/__init__.py" + (" and inventory.yml" if storage == "file" else ""))
    print("Edit the placeholders and generator before using your devices. The example targets Cisco IOS.")
    print(
        "Next: ANN_CONTEXT_CONFIG_PATH=./context.yml annet gen "
        + ("switch.example.test" if storage == "file" else "DEVICE")
    )
    return 0
