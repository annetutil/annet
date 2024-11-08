# Annet - configuration generation and deploying utility for network equipment

Annet is a configuration generator that can translate differences between old and new configurations into sequnce of commands. This feature is vital for CLI-based devices, such as Huawei, Cisco IOS, Cisco NX-OS, Juniper. Devices configured via separate config files, Linux, FreeBSD and Cumulus are also supported.

It works this way. Annet `gen`erates configuration for a device by running Python code, which usually goes to the Network Source of Truth, like NetBox. Annet then gets the `diff`erence by getting the configuration from the device and comparing it. Finally, Annet translates the difference into a sequence of commands, called a `patch`. After `deploy`ing these commands, the diff will be empty.

Annet has a number of modes (subcommands):

- ```annet gen``` - generates the entire config for the specified devices or specified parts of it
- ```annet diff``` - first does gen and then builds diff with current config version
- ```annet patch``` - first does diff and then generates a list of commands to apply diff on the device
- ```annet deploy``` - first does patch and then deploys it to the device

Usage help can be obtained by calling ```annet -h``` or for a specific command, such as ```annet gen -h```.

## Overview

### annet gen

The annet_generators directory contains many files called generators.
A generator takes information about the switch as input and returns the configuration.
The part of the config that the generator is responsible for is specified in the generator's acl function. If a generator returns a configuration that does not fall under acl, an exception will be thrown.

Example generator:

```python
from annet.generators import PartialGenerator

class Mtu(PartialGenerator):
    TAGS = ["mtu"]
    def acl_cisco(self, _):
        return "system mtu jumbo"

    def run_cisco(self, device):
        yield "system mtu jumbo %d" % 9000
```


And an example of calling annet:
```bash
annet gen -g mtu sw6-i1
# -------------------- sw6-i1.cfg --------------------
system mtu jumbo 9000
```

Method `acl_cisco` defines scope of the generator, which commands and block it controls.
The option `-g mtu` means that only generators with the mtu element in the TAGS variable should be called. If no tag is specified, all generators will be executed.


### annet diff

If we were configuring the switch from scratch, these options would be enough, but in our reality we need to be able not only to generate the desired configuration, but also to be able to bring the current configuration to the desired one.
To do this, you need to be able to delete an outdated configuration and correctly add a new one. The **diff** module, which implements some tricky logic, is responsible for this work.
This logic is defined in the rulebook/texts/VENDOR folder.

Example diff:
```diff
# -------------------- sw1-i38.cfg --------------------
  acl number 2610
- rule 40 permit source 10.11.170.150 0
+ rule 12 permit source 10.11.133.81 0
```

### annet patch

Next, you need to create a list of commands from the resulting diff. The **patch** module is responsible for this. It receives the diff, runs the logic specified in rulebook/texts/VENDOR and returns the list of commands.
Let's take the above diff. It says to remove the command ``rule 40 permit source 10.11.170.150 0`` and add ``rule 12 permit source 10.11.133.81 0``.
Basic command delete logic for huawei is adding undo to the command. So the undo command will look like this: ``undo rule 40 permit source 10.11.170.150 0```, but this is an invalid command. In case of canceling acl rules, you need to execute ``undo rule N```.
So you need to write the undo logic for the ```rule ```` command in the ``acl ``` block.
Here is the part of rulebook/texts/huawei.rul responsible for this:
```
acl name *
  rule * %logic=huawei.misc.undo_redo
```
The asterisk here means that the key argument of the undo_redo function will contain the first word after rule, namely the rule number.

Here, the undo_redo function from the file in rulebook/huawei/misc.py is used to generate the command to remove rules in acl.
```python
def undo_redo(rule, key, diff, **_):
    ...
```
Now calling `annet patch -g snmp sw1-i38` returns the correct set of commands.
```
acl number 2610
  undo rule 40
  rule 12 permit source 10.11.133.81 0
  quit
```

### annet deploy

To apply these commands on a switch there is a **deploy** module.
Annet can apply changes (roll out) to multiple devices at the same time.

By default, the edits that annet proposes to roll out will be shown before the rollout.
The user must confirm that they agree to roll out the proposed diff to a given list of devices.
During the rollout, annet will display the overall progress of the task and the log of one of the devices.

Normal layout. The screen with patches will be shown and the process of laying out will be displayed.

```bash
annet deploy -g snmp $HOST
```

Credentials will be used from the current user (username, ssh key, ssh agent).

## Installation

```shell
mkdir myproject
cd myproject
python3 -m venv venv
source venv/bin/activate
pip install annet gnetcli_adapter

cat > ~/.annet/context.yml_tmp<<EOF
fetcher:
  default:
    adapter: gnetcli
deployer:
  default:
    adapter: gnetcli
generators:
  default:
    - my_generators
storage:
  netbox:
    adapter: netbox
    params:
      url: http://127.0.0.1:8000
      token: 1234567890abcdef01234567890abcdef0123456
context:
  default:
    fetcher: default
    deployer: default
    connection: default
    generators: default
    storage: default
selected_context: default
EOF

cp -r my_generators

annet deploy mydevice
```

## Configuration

The path to the configuration file is searched in following order:
- `ANN_CONTEXT_CONFIG_PATH` env.
- `~/.annet/context.yml`.
- `annet/configs/context.yml`.

Config example:

```yaml
connection:
  default:
    login: ~
    passwords: ~

generators:
  default:
    - my_annet_generators.example

storage:
  default:
    adapter: annet.adapters.file.provider
    params:
      path: /path/to/file

context:
  default:
    connection: default
    generators: default
    storage: default

selected_context: default
```

Environment variable `ANN_SELECTED_CONTEXT` can be used to override `selected_context` parameter.

### Storages

Storages provide information about devices like FQDN, interface and so on.

#### Netbox storage

Provide `NETBOX_URL` and `NETBOX_TOKEN` environment variable to setup data source.

```shell
export NETBOX_URL="https://demo.netbox.dev"
export NETBOX_TOKEN="1234567890abcdef01234567890abcdef0123456"
```

#### File storage
```yaml
storage:
  default:
    adapter: annet.adapters.file.provider
    params:
      path: /path/to/file
```

cat /path/to/file:

```yaml
devices:
  - fqdn: myhost.yndx.net
    vendor: mikrotik
    interfaces:
      - name: eth0
        description: test
```

## Extending

Annet uses [Entry Points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html) mechanism for customization.
For example, you can implement the Storage interface on top of your favorite inventory system.


## Building doc

1. Install dependencies:

```shell
pip install -r requirements-doc.txt
```

2. Build

```shell
sphinx-build -M html docs docs-build
```

3. Open rendered html in browser [docs-build/html/index.html](docs-build/html/index.html)