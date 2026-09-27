"""Docker-only project bootstrap; all other commands are executed by Annet."""

import argparse
import getpass
import os
import sys
from pathlib import Path

import yaml


TEMPLATE = Path(__file__).resolve().parent / "examples" / "quickstart"


def init_project(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="annet-docker init", description="Create configuration in the current directory"
    )
    parser.add_argument("--storage", choices=("file", "netbox"), help="omit to choose interactively")
    parser.add_argument("--netbox-url", help="NetBox URL (otherwise a placeholder is written in non-interactive mode)")
    args = parser.parse_args(argv)
    interactive = args.storage is None
    if interactive:
        if not sys.stdin.isatty():
            parser.error("use --storage file or --storage netbox when stdin is not a terminal")
        while args.storage not in ("file", "netbox"):
            args.storage = input("Device source [file/netbox] (file): ").strip().lower() or "file"
    if args.netbox_url and args.storage != "netbox":
        parser.error("--netbox-url requires --storage netbox")

    targets = [Path("context.yml"), Path("generators")]
    if args.storage == "file":
        targets.append(Path("inventory.yml"))
    for target in targets:
        if target.exists() or target.is_symlink():
            parser.error(f"refusing to overwrite {target}; use an empty project directory")

    config = yaml.safe_load((TEMPLATE / "context.yml").read_text())
    config["generators"]["default"] = ["generators/__init__.py"]
    if args.storage == "file":
        config["storage"]["default"]["params"]["path"] = "./inventory.yml"
    else:
        url = args.netbox_url or "https://netbox.example.test"
        token = os.environ.get("NETBOX_TOKEN", "REPLACE_ME")
        if interactive:
            url = args.netbox_url or input(f"NetBox URL ({url}): ").strip() or url
            token = getpass.getpass("NetBox token (empty to configure later): ") or "REPLACE_ME"
        config["storage"]["default"] = {"adapter": "netbox", "params": {"url": url, "token": token}}

    # Exclusive creation also protects against files appearing after the check.
    Path("generators").mkdir()
    with Path("generators/__init__.py").open("x") as stream:
        stream.write((TEMPLATE / "generators/__init__.py").read_text())
    if args.storage == "file":
        with Path("inventory.yml").open("x") as stream:
            stream.write((TEMPLATE / "inventory.yml").read_text())
    fd = os.open("context.yml", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        yaml.safe_dump(config, stream, sort_keys=False)
    print("Created context.yml and generators/__init__.py" + (" and inventory.yml" if args.storage == "file" else ""))
    print("Edit the placeholders and generator before using your devices. The example targets Cisco IOS.")
    print("Next: annet-docker gen " + ("switch.example.test" if args.storage == "file" else "DEVICE"))
    return 0


def main() -> int:
    argv = sys.argv[1:] or ["--help"]
    if argv[0] == "init":
        try:
            return init_project(argv[1:])
        except (OSError, EOFError) as error:
            print(f"init failed: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nInitialization cancelled", file=sys.stderr)
            return 130
    os.execvp("annet", ["annet", *argv])
    return 0


if __name__ == "__main__":
    sys.exit(main())
