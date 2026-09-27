"""Run the documented flows against a stateful SSH device, locally or in Docker.

ANNET_TEST_IMAGE selects Docker mode. Otherwise installed annet/gnetcli/gswitch binaries
are used, which validates behavior but does not validate the container image.
"""

import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml


HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def lab(tmp_path_factory):
    root = tmp_path_factory.mktemp("quickstart")
    # Docker's non-root user must traverse the test paths.
    root.chmod(0o755)
    work = root / "work"
    shutil.copytree(HERE.parent / "examples/quickstart", work)
    secret_dir = root / "secrets"
    secret_dir.mkdir()
    password = secrets.token_hex(20)
    (secret_dir / "password").write_text(password + "\n")
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "gswitch-smoke", "-f", str(secret_dir / "key")],
        check=True,
        capture_output=True,
    )
    for path in secret_dir.iterdir():
        path.chmod(0o444)  # Ephemeral fixture secrets, not production advice.
    inventory = yaml.safe_load((work / "inventory.yml").read_text())
    initial_config = root / "initial.cfg"
    interface_name = inventory["devices"][0]["interfaces"][0]["name"]
    initial_config.write_text(f"interface {interface_name}\n description before\n!\n")
    image = os.environ.get("ANNET_TEST_IMAGE")
    name = "annet-test-" + secrets.token_hex(5)
    process = None
    process_log = None
    devices = set()
    network = name

    def device_args(host, port, config, ready, keys, delay="0"):
        # These are fresh test-only credentials, not credentials for real equipment.
        return [
            "-host",
            host,
            "-port",
            str(port),
            "-username",
            "annet",
            "-password",
            password,
            "-authorized-keys",
            keys,
            "-config-file",
            config,
            "-ready-file",
            ready,
            "-command-delay",
            delay,
            "-debug",
        ]

    def start_device(container_name, alias, delay="0"):
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--init",
                "--name",
                container_name,
                "--network",
                network,
                "--network-alias",
                alias,
                "--mount",
                f"type=bind,src={secret_dir},dst=/secrets,readonly",
                "--mount",
                f"type=bind,src={initial_config},dst=/initial.cfg,readonly",
                os.environ["ANNET_TEST_DEVICE_IMAGE"],
                *device_args("0.0.0.0", 2222, "/initial.cfg", "/tmp/ready.json", "/secrets/key.pub", delay),
            ],
            check=True,
            capture_output=True,
        )
        devices.add(container_name)
        for _ in range(100):
            ready = subprocess.run(
                ["docker", "exec", container_name, "cat", "/tmp/ready.json"], capture_output=True, text=True
            )
            if ready.returncode == 0:
                assert json.loads(ready.stdout)["ssh"].endswith(":2222")
                return
            time.sleep(0.1)
        logs = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
        pytest.fail("gswitch did not start: " + (logs.stdout + logs.stderr).replace(password, "[REDACTED]"))

    try:
        if image:

            def revision(image_name, path):
                data = subprocess.check_output(["docker", "run", "--rm", "--entrypoint", "cat", image_name, path])
                return json.loads(data)["gnetcli"]["revision"]

            assert revision(image, "/usr/local/share/annet/versions.json") == revision(
                os.environ["ANNET_TEST_DEVICE_IMAGE"], "/usr/local/share/gswitch/versions.json"
            ), "Runtime and gswitch fixture must use the same Gnetcli revision"
            subprocess.run(["docker", "network", "create", network], check=True, capture_output=True)
            start_device(name, "switch.example.test")
            host, port = "switch.example.test", 2222
            config_work, config_secrets = "/work", "/run/secrets"
        else:
            ready = root / "ready.json"
            process_log = (root / "gswitch.log").open("w")
            process = subprocess.Popen(
                [
                    os.environ.get("GSWITCH_BIN", "gswitch"),
                    *device_args("127.0.0.1", 0, str(initial_config), str(ready), str(secret_dir / "key.pub")),
                ],
                stdout=subprocess.DEVNULL,
                stderr=process_log,
            )
            for _ in range(100):
                if ready.exists():
                    break
                if process.poll() is not None:
                    pytest.fail("gswitch exited before becoming ready; see " + str(root / "gswitch.log"))
                time.sleep(0.1)
            else:
                pytest.fail("gswitch did not start")
            host, port = "127.0.0.1", int(json.loads(ready.read_text())["ssh"].rsplit(":", 1)[1])
            config_work, config_secrets = str(work), str(secret_dir)
        context = yaml.safe_load((work / "context.yml").read_text())
        params = context["fetcher"]["default"]["params"]
        params.update(dev_password=password, dev_port=port)
        context["deployer"]["default"]["params"] = params.copy()
        context["generators"]["default"] = [config_work + "/generators/__init__.py"]
        context["storage"]["default"]["params"]["path"] = config_work + "/inventory.yml"
        (work / "context.yml").write_text(yaml.safe_dump(context))
        inventory = yaml.safe_load((work / "inventory.yml").read_text())
        inventory["devices"][0]["fqdn"] = host
        (work / "inventory.yml").write_text(yaml.safe_dump(inventory))
        ssh = root / "ssh"
        ssh.mkdir()
        (ssh / "config").write_text(f"Host *\n    User annet\n    IdentityFile {config_secrets}/key\n")
        home = root / "home"
        home.mkdir()
        shutil.copytree(ssh, home / ".ssh")

        def run(binary, *args, expect=0):
            env = os.environ.copy()
            # Docker locates its active context under the host HOME.
            # Only local Annet processes should receive the isolated test HOME.
            if image:
                command = [
                    "docker",
                    "run",
                    "--rm",
                    "--init",
                    "--network",
                    network,
                    "--mount",
                    f"type=bind,src={work},dst=/work,readonly",
                    "--mount",
                    f"type=bind,src={secret_dir},dst=/run/secrets,readonly",
                    "--mount",
                    f"type=bind,src={ssh / 'config'},dst=/etc/ssh/ssh_config,readonly",
                    "--entrypoint",
                    binary,
                    image,
                    *args,
                ]
            else:
                env.update(HOME=str(home), ANN_CONTEXT_CONFIG_PATH=str(work / "context.yml"), SSH_AUTH_SOCK="")
                command = [binary, *args]
            result = subprocess.run(command, env=env, cwd=work, capture_output=True, text=True, timeout=90)
            assert password not in result.stdout + result.stderr
            if expect is not None:
                assert result.returncode == expect, result.stdout + result.stderr
            return result

        yield run, work, context, host, str(port), config_secrets, image, network, start_device
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
        if process_log:
            process_log.close()
        if image:
            for container_name in devices:
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)


def test_quickstart(lab):
    run, work, context, host, port, secret_dir, image, _, _ = lab
    run("annet", "--help")
    run("gnetcli", "--help")
    run("python", "-m", "pip", "check")
    if expected := os.environ.get("ANNET_TEST_VERSION"):
        run(
            "python",
            "-c",
            "import sys; from importlib.metadata import version; assert version('annet') == sys.argv[1]",
            expected,
        )
    generated = run("annet", "gen", host)
    assert "description Managed by Annet quick start" in generated.stdout
    assert "before" in run("annet", "show", "current", host).stdout
    assert "Managed by Annet" in run("annet", "diff", host).stdout
    assert "description Managed by Annet" in run("annet", "patch", host).stdout
    run("annet", "deploy", "--no-ask-deploy", host)
    assert "Managed by Annet quick start" in run("annet", "show", "current", host).stdout
    assert not run("annet", "diff", host).stdout.strip()
    base = ("-hostname", host, "-port", port, "-devtype", "cisco", "-login", "annet", "-json")
    password = ("-password-file", secret_dir + "/password")
    assert "12:00:00" in run("gnetcli", *base, *password, "-command", "show clock").stdout
    results = json.loads(run("gnetcli", *base, *password, "-command", "invalid\nshow clock", expect=0).stdout)
    assert [r["status"] for r in results] == [1, 0]
    # The CLI's ssh_config library uses the OS user's home, not HOME, on macOS.
    # Test its system-config mount in Docker without modifying the host's SSH config.
    if image:
        assert "12:00:00" in run("gnetcli", *base, "-use-ssh-config", "-command", "show clock").stdout
    assert run("gnetcli", *base, "-password", "incorrect", "-command", "show clock", expect=None).returncode != 0
    assert run("gnetcli", *base, "-password-file", "/nonexistent/password", "-command", "show clock", expect=2)
    # Key-only Annet path, not only direct CLI.
    for section in ("fetcher", "deployer"):
        params = context[section]["default"]["params"]
        params.pop("dev_password", None)
        params.pop("dev_login", None)
        params["server_conf"]["dev_auth"].update(private_key=secret_dir + "/key", login="annet")
    (work / "context.yml").write_text(yaml.safe_dump(context))
    assert "Managed by Annet" in run("annet", "show", "current", host).stdout
    if image:
        run("python", "-c", "import os, shutil; assert os.getuid() != 0; assert shutil.which('gswitch') is None")
        history = subprocess.check_output(["docker", "history", "--no-trunc", image], text=True)
        assert (work.parent / "secrets/password").read_text().strip() not in history
        run(
            "python",
            "-c",
            "import json; from pathlib import Path; assert json.loads(Path('/usr/local/share/annet/versions.json').read_text())['gnetcli']['revision']",
        )


def test_container_lifecycle(lab):
    run, work, _, _, _, _, image, network, start_device = lab
    if not image:
        pytest.skip("Container signal/child-process checks require Docker")
    run(
        "python",
        "-c",
        """
import asyncio
from pathlib import Path
from gnetclisdk.config import Config, LogConfig
from gnetclisdk.starter import GnetcliStarter
async def check():
    async with GnetcliStarter('gnetcli_server', Config(port='127.0.0.1:0', logging=LogConfig(json=True))):
        children = []
        for path in Path('/proc').glob('[0-9]*/comm'):
            try:
                if path.read_text().strip() == 'gnetcli_server':
                    children.append(path.parent)
            except FileNotFoundError:
                pass
        assert children
    assert all(not path.exists() for path in children)
asyncio.run(check())
""",
    )
    secret_dir = work.parent / "secrets"
    slow_work = work.parent / "slow-work"
    shutil.copytree(work, slow_work)
    host = "slow-switch.example.test"
    inventory = yaml.safe_load((slow_work / "inventory.yml").read_text())
    inventory["devices"][0]["fqdn"] = host
    (slow_work / "inventory.yml").write_text(yaml.safe_dump(inventory))
    slow_device = "gswitch-slow-" + secrets.token_hex(5)
    start_device(slow_device, host, delay="30s")
    name = "annet-stop-" + secrets.token_hex(5)
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--init",
                "--name",
                name,
                "--network",
                network,
                "--mount",
                f"type=bind,src={slow_work},dst=/work,readonly",
                "--mount",
                f"type=bind,src={secret_dir},dst=/run/secrets,readonly",
                image,
                "show",
                "current",
                host,
            ],
            check=True,
            capture_output=True,
        )
        for _ in range(100):
            top = subprocess.run(["docker", "top", name], capture_output=True, text=True)
            if "gnetcli_server" in top.stdout:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Annet did not start its child server")
        for _ in range(100):
            logs = subprocess.run(["docker", "logs", slow_device], capture_output=True, text=True)
            if "received command" in logs.stdout + logs.stderr:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Annet did not reach the delayed gswitch command")
        subprocess.run(["docker", "stop", "--time", "15", name], check=True, capture_output=True, timeout=25)
        state = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]["State"]
        assert not state["Running"]
        assert state["ExitCode"] != 137  # Must not require SIGKILL.
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
