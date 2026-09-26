# Annet container

The runtime includes Annet, `annetbox[sync]`, `gnetcli_adapter`, `gnetclisdk`,
`gnetcli_server`, and the `gnetcli` CLI. NetBox and network devices are external.
The adapter starts and stops its own local server; do not expose a gRPC port.

## Quick start: one device, no NetBox

Requires Docker and network access from the container to an Arista EOS device.
The example only manages the description of Ethernet1; it does not replace the
whole configuration. Use a lab device first.

This directory provides a locally built image; registry publication is separate.
From the Annet checkout, build it once with Docker and Python 3 (used only to
prepare the build context; no Python packages or Go installation are needed):

```sh
context=$(mktemp -d)/context
python3 docker/prepare.py "$context"
docker build -t annet:local "$context"
export IMAGE=annet:local
```

Copy the example into a private working directory. Only Docker is required to
run the built image; device credentials and generators stay outside it.

```sh
workdir=$(mktemp -d)
cp -R docker/examples/quickstart "$workdir/quickstart"
cd "$workdir"
# Edit inventory.yml: replace switch.example.test with the device's reachable
# DNS name or IP. Set the actual interface name and desired description.
# Edit context.yml: set dev_login and dev_password; optionally dev_port.
chmod 600 quickstart/context.yml
# Run as your UID/GID so the container can read your private config.
# A temporary writable home is used for caches; /work stays read-only.
docker run --rm --init --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD/quickstart,dst=/work,readonly" "$IMAGE" gen switch.example.test
```

Replace `switch.example.test` in every command with the inventory FQDN. Preview
changes before deploying:

```sh
docker run --rm --init --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD/quickstart,dst=/work,readonly" "$IMAGE" diff switch.example.test
docker run --rm --init --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD/quickstart,dst=/work,readonly" "$IMAGE" patch switch.example.test
docker run --rm --init -it --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD/quickstart,dst=/work,readonly" "$IMAGE" deploy switch.example.test
```

Run `diff` again: no configuration changes should remain. `--no-ask-deploy`
explicitly disables confirmation for automation; the default quick start does
not use it. `docker run IMAGE --help` shows the available Annet commands.

These commands target a reachable DNS name/IP, not a Docker host's loopback.
Inside a container `127.0.0.1` is the container itself. On Docker Desktop use
`host.docker.internal` for host services; on Linux configure routing or an
explicit host-gateway mapping. Do not assume `--network host` is portable.

## SSH key instead of a password

In both fetcher and deployer params remove **both** `dev_login` and
`dev_password`: explicit per-device credentials override server key defaults. Add the following
under their shared `server_conf` (keep JSON logging and loopback port settings):

```yaml
dev_auth:
  login: annet
  private_key: /run/secrets/device_key
  use_agent: false
```

Add a read-only mount to each command, still running with your UID/GID:

```sh
--mount "type=bind,src=$HOME/.ssh/device_key,dst=/run/secrets/device_key,readonly"
```

This basic example uses a dedicated unencrypted key with limited device access.
Protect it with host file permissions. SSH agent, encrypted keys and ProxyJump
are advanced scenarios and are not covered by this quick start's acceptance tests.

## Execute an arbitrary command

The direct CLI is separate from Annet: it does not read `context.yml` or run
generators. Store the password in a private UTF-8 file (mode 600), not in shell
history. One final LF/CRLF is removed; other whitespace is preserved.

```sh
docker run --rm --init --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD/device-password,dst=/run/secrets/password,readonly" \
  --entrypoint gnetcli "$IMAGE" \
  -hostname switch.example.test -devtype arista -login annet \
  -password-file /run/secrets/password -command 'show clock' -json
```

For key authentication use the supplied `ssh_config`, updating its Host and
User entries. Mount it at `/etc/ssh/ssh_config`, mount the key at
`/run/secrets/device_key`, pass `-use-ssh-config` and omit `-password-file`.
No password and key contents are baked into the image. Do not enable debug
logging when handling sensitive device output.

Device command errors retain the existing CLI behavior: the process exits
with code 0 and the JSON results contain each command's individual status.
Inspect those statuses to detect device command failures. Multiline commands
still execute in order; transport failures stop execution unsuccessfully.

**Security limitation:** Gnetcli currently ignores SSH host keys by default.
Mounting `known_hosts` does not enable verification. Use trusted network paths;
this image does not provide protection against SSH server impersonation.

## NetBox

Keep fetcher/deployer configuration, but replace storage with:

```yaml
storage:
  default:
    adapter: netbox
```

Supply `NETBOX_URL` and `NETBOX_TOKEN` in a private env file mounted through
Docker's `--env-file` option. Docker administrators can inspect container
environment variables. Do not put secrets in image build arguments or layers.
The image includes the synchronous NetBox client; no extra installation is
required. See the [configuration reference](../docs/usage/config.rst) for
accepted versions and the [lab tutorial](../docs/usage/tutorial.rst) for richer
generators. The file example does not need a NetBox server.

## Build and verification

From the Annet repository:

```sh
context=$(mktemp -d)/context
python3 docker/prepare.py "$context"
docker build -t annet:local "$context"
docker build -t annet-device:test docker/tests
python3 -m venv /tmp/annet-smoke
/tmp/annet-smoke/bin/pip install --require-hashes -r docker/tests/requirements.lock
ANNET_TEST_IMAGE=annet:local ANNET_TEST_DEVICE_IMAGE=annet-device:test \
  /tmp/annet-smoke/bin/python -m pytest -o addopts='' docker/tests
```

Do not use the repository root as a Docker context: `prepare.py` copies only
tracked package files plus the explicit build assets, excluding local keys,
configs, virtualenvs, and untracked package experiments. Other Dockerfiles in
the checkout are not used. Test credentials are generated at test runtime.

The image supports `linux/amd64` and `linux/arm64`. To check a particular
architecture, add `--platform linux/amd64` or `--platform linux/arm64` to
`docker build` and use a distinct image tag. Running a non-native image requires
Docker emulation; native runners are preferable for release verification.
Publishing images and the GitHub Actions release workflow are not part of this
local-build setup.

`requirements.lock` and `build.lock` pin Python dependencies and hashes; base
images have immutable digests. `sources.json` pins Go/SDK and adapter archives.
`annetbox==1.1.2` is a locked PyPI dependency. The pinned Gnetcli revision includes
`-password-file`; the build applies no local source patches. Both architecture
smoke tests must pass after updating the pinned revision.

Update lockfiles using `uv pip compile --python-version 3.12 --universal
--generate-hashes --no-emit-index-url`, with the corresponding `.in` and `-o`
`.lock` files. Dependency sources and base-image digests are reviewed updates,
not resolved from floating branches during release. The installed provenance
is available at `/usr/local/share/annet/versions.json`.
Local builds use the explicitly recorded development package version.
Set `--build-arg ANNET_VERSION=<version>` to override the Annet wheel version.
