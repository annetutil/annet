Configuration
==========================

The path to the configuration file is searched in following order:
- ``ANN_CONTEXT_CONFIG_PATH`` env.
- ``~/.annet/context.yml``.
- ``annet/configs/context.yml``.

Config example:

.. code-block:: yaml

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
        fetcher: default
        deployer: default
        generators: default
        storage: default

    selected_context: default


Environment variable ``ANN_SELECTED_CONTEXT`` can be used to override ``selected_context`` parameter.

Storages
************************

Storages provide information about devices like FQDN, interface and so on.

Netbox storage
----------------------

Provide ``NETBOX_URL`` and ``NETBOX_TOKEN`` environment variable to setup data source.

.. code-block:: shell

    export NETBOX_URL="https://demo.netbox.dev"
    export NETBOX_TOKEN="1234567890abcdef01234567890abcdef0123456"

File storage
----------------------

.. code-block:: yaml

    storage:
      default:
        adapter: annet.adapters.file.provider
        params:
          path: /path/to/file


cat /path/to/file:

.. code-block:: yaml

    devices:
      - fqdn: myhost.yndx.net
        vendor: mikrotik
        interfaces:
          - name: eth0
            description: test
