# Annet - configuration generation and deploying utility for network equipment

Annet is a configuration generator that can translate differences between old and new configurations into sequence of commands. This feature is vital for CLI-based devices, such as Huawei, Cisco IOS, Cisco NX-OS, Juniper. Devices configured via separate config files, Linux, FreeBSD and Cumulus are also supported.

It works this way. Annet `gen`erates configuration for a device by running Python code, which usually goes to the Network Source of Truth, like NetBox. Annet then gets the `diff`erence by getting the configuration from the device and comparing it. Finally, Annet translates the difference into a sequence of commands, called a `patch`. After `deploy`ing these commands, the diff will be empty.

Annet has a number of modes (subcommands):

- ```annet gen``` - generates the entire config for the specified devices or specified parts of it
- ```annet diff``` - first does gen and then builds diff with current config version
- ```annet patch``` - first does diff and then generates a list of commands to apply diff on the device
- ```annet deploy``` - first does patch and then deploys it to the device

Usage help can be obtained by calling ```annet -h``` or for a specific command, such as ```annet gen -h```.

<img src="https://github.com/annetutil/annet/blob/main/docs/_static/annet_demo.gif?raw=true" width="800" />

## Configuration

The path to the configuration file is searched in following order:
- `ANN_CONTEXT_CONFIG_PATH` env.
- `~/.annet/context.yml`.
- `annet/configs/context.yml`.

Config example:

```yaml
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
    generators: default
    storage: default

selected_context: default
```

Environment variable `ANN_SELECTED_CONTEXT` can be used to override `selected_context` parameter.

## Building doc

1. Install dependencies:

```shell
pip install -r requirements-doc.txt
```

2. Build

```shell
sphinx-build -M html docs docs-build
```

3. Open rendered html in browser docs-build/html/index.html
