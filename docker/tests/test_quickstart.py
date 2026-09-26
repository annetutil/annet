"""Run the documented flows against a stateful SSH device, locally or in Docker.

ANNET_TEST_IMAGE selects Docker mode. Otherwise installed annet/gnetcli binaries
are used, which validates behavior but does not validate the container image.
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import asyncssh
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
    key = asyncssh.generate_private_key("ssh-rsa", key_size=2048)
    key.write_private_key(secret_dir / "key")
    key.write_public_key(secret_dir / "key.pub")
    for path in secret_dir.iterdir():
        path.chmod(0o444)  # Ephemeral fixture secrets, not production advice.
    image = os.environ.get("ANNET_TEST_IMAGE")
    name = "annet-test-" + secrets.token_hex(5)
    process = None
    network = name
    try:
        if image:
            subprocess.run(["docker", "network", "create", network], check=True, capture_output=True)
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    name,
                    "--network",
                    network,
                    "--network-alias",
                    "switch.example.test",
                    "--mount",
                    f"type=bind,src={secret_dir},dst=/secrets,readonly",
                    os.environ["ANNET_TEST_DEVICE_IMAGE"],
                ],
                check=True,
                capture_output=True,
            )
            for _ in range(100):
                if (
                    subprocess.run(["docker", "exec", name, "test", "-f", "/tmp/ready"], capture_output=True).returncode
                    == 0
                ):
                    break
                time.sleep(0.1)
            else:
                pytest.fail("SSH fixture did not start")
            host, port = "switch.example.test", 2222
            config_work, config_secrets = "/work", "/run/secrets"
        else:
            ready = root / "ready"
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(HERE / "ssh_device.py"),
                    "--password-file",
                    str(secret_dir / "password"),
                    "--public-key",
                    str(secret_dir / "key.pub"),
                    "--ready",
                    str(ready),
                ]
            )
            for _ in range(100):
                if ready.exists():
                    break
                if process.poll() is not None:
                    pytest.fail("SSH fixture exited")
                time.sleep(0.1)
            else:
                pytest.fail("SSH fixture did not start")
            host, port = "127.0.0.1", int(ready.read_text())
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

        yield run, work, context, host, str(port), config_secrets, image, network
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
        if image:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)


def test_quickstart(lab):
    run, work, context, host, port, secret_dir, image, _ = lab
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
    base = ("-hostname", host, "-port", port, "-devtype", "arista", "-login", "annet", "-json")
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
        run("python", "-c", "import os; assert os.getuid() != 0")
        history = subprocess.check_output(["docker", "history", "--no-trunc", image], text=True)
        assert (work.parent / "secrets/password").read_text().strip() not in history
        run(
            "python",
            "-c",
            "import json; from pathlib import Path; assert json.loads(Path('/usr/local/share/annet/versions.json').read_text())['gnetcli']['revision']",
        )


def test_container_lifecycle(lab):
    run, work, _, host, _, _, image, network = lab
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
    (secret_dir / "hang").touch()
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
                f"type=bind,src={work},dst=/work,readonly",
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
        subprocess.run(["docker", "stop", "--time", "15", name], check=True, capture_output=True, timeout=25)
        state = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]["State"]
        assert not state["Running"]
        assert state["ExitCode"] != 137  # Must not require SIGKILL.
    finally:
        (secret_dir / "hang").unlink(missing_ok=True)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
