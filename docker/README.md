# Annet container

The runtime includes Annet, `annetbox[sync]`, `gnetcli_adapter`, `gnetclisdk`,
`gnetcli_server`, and the `gnetcli` CLI. NetBox and network devices are external.
The adapter starts and stops its own local server; do not expose a gRPC port.

## Create a project with the image

`init` is an Annet CLI command, also available through the container.
Published images must contain an Annet release that includes this command;
rebuilding with an older PyPI release does not add it. PR CI separately installs
a wheel from the checkout to test unreleased changes.
With the `annet-docker` wrapper installed (see below), start in an empty directory:

```sh
mkdir my-network
cd my-network
annet-docker init
```

It asks whether to use `file` or `netbox`. For NetBox, it also asks for the URL
and a token (hidden input; leave empty to configure later). It creates:

- `context.yml` with permissions `0600`;
- `generators/__init__.py`, a minimal Cisco IOS interface-description generator;
- `inventory.yml` with a sample device, only for file storage.

Existing target files or a `generators` directory are never overwritten.
Paths in the generated context are relative to the project working directory.
Edit the example generator for your devices and replace credential placeholders
before fetching or deploying. Initialization never connects to NetBox or devices.

For non-interactive use:

```sh
annet-docker init --storage file
# Or create a NetBox context; edit its token afterwards:
annet-docker init --storage netbox --netbox-url https://netbox.example.org
```

Run these alternatives in separate empty directories. After file initialization,
you can immediately try `annet-docker gen switch.example.test` without a device.
For NetBox, configure a valid URL and token before running `gen DEVICE`.

Without installing the wrapper, run the published image directly:

```sh
docker run --rm --init -it --network host \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD,dst=/work" \
  ghcr.io/annetutil/annet:latest init
```

For automation omit `-it` and add `--storage file` or `--storage netbox` after
`init`. Non-interactive NetBox initialization accepts `NETBOX_TOKEN` inside the
container; pass it via Docker's `--env-file` if needed, not as a command argument.
The wrapper does not forward that variable. The token is saved in `context.yml`;
keep that file private and out of version control. The image runs Annet directly, including `init`.

## Quick start: one device, no NetBox

Requires Docker and network access from the container to a Cisco IOS device.
The example only manages the description of GigabitEthernet0/1; it does not replace the
whole configuration. Use a lab device first.

For a local build using the latest published packages, follow the steps below.
For automatically published images using the latest Gnetcli release, see
[CI images](#ci-images).
From the Annet checkout, build it with Docker only; no local Python or Go
installation is needed:

```sh
docker build --pull --no-cache -t annet:local docker
export ANNET_IMAGE=annet:local
mkdir -p "$HOME/.local/bin"
install -m 755 docker/annet-docker "$HOME/.local/bin/annet-docker"
export PATH="$HOME/.local/bin:$PATH"
```

Copy the example into a private working directory. Only Docker is required to
run the built image; device credentials and generators stay outside it.

```sh
workdir=$(mktemp -d)
cp -R docker/examples/quickstart "$workdir/quickstart"
cd "$workdir/quickstart"
# Edit inventory.yml: replace switch.example.test with the device's reachable
# DNS name or IP. Set the actual interface name and desired description.
# Edit context.yml: set dev_login and dev_password; optionally dev_port.
chmod 600 context.yml
annet-docker gen switch.example.test
```

Replace `switch.example.test` in every command with the inventory FQDN. Preview
changes before deploying:

```sh
annet-docker diff switch.example.test
annet-docker patch switch.example.test
annet-docker deploy switch.example.test
```

Run `diff` again: no configuration changes should remain. `--no-ask-deploy`
explicitly disables confirmation for automation; the default quick start does
not use it. `annet-docker --help` shows the available Annet commands.

The wrapper mounts the current directory read-write at `/work`, so generators,
configuration and output paths should live inside that directory. It runs as
your UID/GID with a temporary home and removes the container after exit. It
forwards arguments and exit status unchanged, and allocates a TTY only when
both stdin and stdout are terminals, preserving interactive deploy confirmation.

By default it uses `ghcr.io/annetutil/annet:latest`. Set `ANNET_IMAGE` to use a
local image or a specific published tag. To update a cached image explicitly:

```sh
docker pull "${ANNET_IMAGE:-ghcr.io/annetutil/annet:latest}"
```

**Host networking is enabled by default.** To disable it, select the standard
Docker bridge network (or supply the name of another existing Docker network):

```sh
ANNET_DOCKER_NETWORK=bridge annet-docker diff switch.example.test
```

Unset or empty `ANNET_DOCKER_NETWORK` means `host`. Host networking shares the
Docker host's network namespace on Linux; Docker Desktop requires its host
networking feature to be enabled. See [Docker's host networking documentation](https://docs.docker.com/engine/network/drivers/host/).
With bridge networking, `127.0.0.1` is the container itself, not the host. Use a
device address reachable from the selected network.

The wrapper deliberately does not forward arbitrary host environment variables
or mount SSH keys outside the current directory. For additional secret mounts
or `--env-file`, use `docker run` directly as described below. Those examples
use `IMAGE` to select the image:

```sh
export IMAGE="${ANNET_IMAGE:-ghcr.io/annetutil/annet:latest}"
```

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

Use `docker run` directly to mount the external key read-only, still running
with your UID/GID. Replace `diff` with `gen`, `patch` or `deploy` as needed
(add `-it` for interactive deploy confirmation):

```sh
docker run --rm --init --network host --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$PWD,dst=/work,readonly" \
  --mount "type=bind,src=$HOME/.ssh/device_key,dst=/run/secrets/device_key,readonly" \
  "$IMAGE" diff switch.example.test
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
  -hostname switch.example.test -devtype cisco -login annet \
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

From the Annet repository (Docker, Python and OpenSSH `ssh-keygen` are required
to run the tests):

```sh
docker build --pull --no-cache -t annet:local docker
GNETCLI_VERSION=$(docker run --rm --entrypoint python annet:local -c \
  'import json; print(json.load(open("/usr/local/share/annet/versions.json"))["gnetcli"]["revision"])')
docker build --target test-device --build-arg "GNETCLI_VERSION=$GNETCLI_VERSION" \
  -t annet-device:test docker
python3 -m venv /tmp/annet-smoke
/tmp/annet-smoke/bin/pip install -r docker/tests/requirements.in
ANNET_TEST_IMAGE=annet:local ANNET_TEST_DEVICE_IMAGE=annet-device:test \
  /tmp/annet-smoke/bin/python -m pytest -o addopts='' docker/tests
```

`docker/` is the build context. Its `.dockerignore` allows only the Dockerfile,
requirements and source-download scripts. Local configurations, examples and
tests are not sent to the image build. Initialization templates are shipped
inside the installed Annet package. The `test-device` target builds `gswitch`
from the same Gnetcli revision as the runtime; no Python SSH emulator or
`asyncssh` dependency is used. `gswitch` is not included in the runtime image.

The Docker smoke scenario starts with `init --storage file`, then uses the
generated project for `gen`, `diff`, `patch`, `deploy` and an empty final `diff`.
Other initialization variants are covered by the regular Annet CLI tests.
Tests create an isolated Docker network, generate disposable credentials with
`ssh-keygen`, and start `gswitch` with `-config-file`, `-authorized-keys` and
`-ready-file`. Its shared Cisco configuration survives reconnects, allowing
`deploy` followed by an empty `diff`. The lifecycle test starts another instance
with `-command-delay 30s` and stops Annet while a command is in flight. All test
containers and networks are removed afterwards; no real device is contacted.
Gnetcli v1.3.17 or newer is required for these fixture options.

Without `ANNET_TEST_IMAGE`, Docker integration tests are skipped; resolver and
wrapper unit tests still run. There is no local-binary smoke mode. CI validates
the workflow with actionlint rather than tests inspecting YAML or shell text.

The image supports `linux/amd64` and `linux/arm64`. Add the corresponding
`--platform` flag to `docker build` to select an architecture. A non-native image
requires emulation; CI uses native runners.

## Package versions

`requirements.in` contains only:

```text
annet[netbox]
gnetcli_adapter
```

Annet's `netbox` extra installs the NetBox client (`annetbox[sync]`), not a
NetBox server. The Gnetcli adapter pulls in `gnetclisdk`. Pip resolves their
transitive dependencies; no Python lockfiles or package hashes are stored in
Git. The Python SDK is installed from PyPI, not built from the Go checkout.

With no build argument, pip installs the latest compatible Annet release from
PyPI. To install a particular published version:

```sh
ANNET_VERSION=4.6.1 docker build --pull --no-cache \
  --build-arg ANNET_VERSION -t annet:4.6.1 docker
```

An unknown or incompatible version fails the build; it never falls back to
latest. Unreleased changes in the current checkout are not installed by the normal
image build. PR CI uses a separate test-only wheel overlay (see below). Use `--no-cache` when rebuilding locally to refresh pip packages; Docker
would otherwise reuse the installation layer. `--pull` refreshes the Python
3.12 and Go 1.25 base images.

Gnetcli binaries default to the latest published stable GitHub release.
`GNETCLI_VERSION` accepts `latest`, a published stable release tag, or a full
commit SHA. CI selects the release once and passes its exact commit to both
architecture builds. Source manifests are generated inside the build, not
checked into Git.
Installed Python versions and the Gnetcli revision are recorded in
`/usr/local/share/annet/versions.json` for diagnostics.


## CI images

The `Annet container` workflow builds on pull requests, pushes to Annet `main`,
published stable Annet releases, and manual runs. It resolves GitHub's latest published
stable **Gnetcli release**, not `main`, once per run. Both architectures use the
same commit, passed as `GNETCLI_VERSION`. The Go binaries come from that revision.
Python packages are installed from PyPI: Annet is latest by default, or the exact release version passed by CI
through `ANNET_VERSION`. Pip selects the adapter, SDK, NetBox client and their
dependencies.

For pull requests only, CI builds an Annet wheel from the checked-out revision
and installs it using the `pr-test` target of `docker/Dockerfile`, passing the
wheel directory as the separate `pr-wheel` build context. The default `runtime`
target uses only published packages and does not require that context. The wheel uses
the base image's Annet version with a `+pr.COMMIT` local suffix, preserving adapter
version constraints. Its dependencies and NetBox extra are resolved, `pip check`
is run, and the image's version manifest is refreshed with the checkout revision.
The complete smoke suite, including `init`, runs against that image. PR images
are never published. Push, release and manual builds continue to use PyPI only.
Until a feature is released, those PyPI builds cannot pass tests requiring it.

After both architecture smoke suites pass, the tested images are published
without rebuilding to `ghcr.io/annetutil/annet`:

- `latest`: successful pushes to `main` and manual runs on `main`;
- `vMAJOR.MINOR.PATCH`: a published stable Annet release;
- `build-RUN_ID-ATTEMPT`: the exact successful CI run, including its Gnetcli revision.

Pull requests and manual runs on other branches do not publish. Publication is
restricted to the `annetutil/annet` repository. An organization maintainer must
make the GHCR package public to allow unauthenticated pulls.

```sh
docker pull ghcr.io/annetutil/annet:latest
docker run --rm ghcr.io/annetutil/annet:latest --help
```

These tags become available only after a successful workflow run. A failed API
lookup, incompatible release, build failure or failed smoke test stops the run;
there is no silent fallback to an older pin, `main`, or a source patch.

A Gnetcli release alone does **not** trigger an Annet build. Start the Annet
workflow manually to pick it up without changing Annet code. No scheduled jobs,
cross-repository workflows or dependency-update PRs are created.

Local builds also resolve the latest Gnetcli release by default. To select
specific versions explicitly:

```sh
docker build --pull --no-cache \
  --build-arg GNETCLI_VERSION=v1.3.15 \
  --build-arg ANNET_VERSION=4.6.1 \
  -t annet:selected docker
```

For a CI rebuild, use the full Gnetcli commit SHA from its `selected-sources`
artifact as `GNETCLI_VERSION`. That fixes the Go source selection, not the
Python dependency resolution. No generated files or preparation commands are
needed on the build host. The image records its own source manifest and Python
package versions in `/usr/local/share/annet/versions.json`.

For an Annet release, CI passes the release tag without `v` as `ANNET_VERSION`
and waits up to five minutes for that version to become available on PyPI. If
PyPI publication fails or is delayed longer, the image build fails and can be
rerun once the package is published.
