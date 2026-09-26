"""Tiny stateful EOS-like SSH fixture. Test-only; never exposes a real device."""

import argparse
import asyncio
from pathlib import Path

import asyncssh


async def serve(args):
    password = args.password_file.read_text().rstrip("\n")
    public_key = asyncssh.read_public_key(args.public_key)
    state = {"description": "before"}

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return True

        def password_auth_supported(self):
            return True

        def public_key_auth_supported(self):
            return True

        def validate_password(self, username, supplied):
            return username == "annet" and supplied == password

        def validate_public_key(self, username, supplied):
            return username == "annet" and supplied == public_key

    async def session(process):
        mode = ""
        pending = None
        process.stdout.write("switch#")
        async for line in process.stdin:
            command = line.strip()
            if (args.password_file.parent / "hang").exists():
                await asyncio.sleep(300)
            process.stdout.write(command + "\r\n")
            if command in {"show running-config", "show running-config | no-more"}:
                process.stdout.write(
                    "! Command: show running-config\r\ninterface Ethernet1\r\n   description "
                    + state["description"]
                    + "\r\n!\r\nend\r\n"
                )
            elif command == "show clock":
                process.stdout.write("12:00:00\r\n")
            elif command in {"configure terminal", "conf s"}:
                pending = dict(state)
                mode = "(config)"
            elif command == "interface Ethernet1":
                mode = "(config-if-Et1)"
            elif command.startswith("description "):
                (pending if pending is not None else state)["description"] = command.removeprefix("description ")
            elif command == "no description" or command.startswith("no description "):
                (pending if pending is not None else state)["description"] = ""
            elif command == "commit":
                if pending is not None:
                    state.update(pending)
                pending = None
                mode = ""
            elif command == "abort":
                pending = None
                mode = ""
            elif command in {"exit", "end"}:
                mode = ""
            elif command == "hang":
                await asyncio.sleep(300)
            elif command not in {
                "",
                "enable",
                "terminal length 0",
                "write memory",
                "commit",
                "abort",
                "copy running-config startup-config",
            }:
                print("Rejected test command:", repr(command), flush=True)
                process.stdout.write("% Invalid input\r\n")
            process.stdout.write("switch" + mode + "#")

    server = await asyncssh.create_server(
        Server,
        args.host,
        args.port,
        server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
        process_factory=session,
        line_editor=False,
    )
    if args.ready:
        args.ready.write_text(str(server.get_port()))
    await server.wait_closed()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--ready", type=Path)
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
