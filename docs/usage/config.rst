Configuration
==========================

The path to the configuration file is searched in following order:

* ``ANN_CONTEXT_CONFIG_PATH`` env.
* ``~/.annet/context.yml``.
* ``annet/configs/context.yml``.

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

generators
************************

See :ref:`generator reference`.

.. code-block:: yaml

    generators:
      default:
        - /path/to/my_annet_generators/__init__.py
        - my_annet_generators  # relative import from sys.path

storages
************************

Storages provide information about devices like FQDN, interface and so on.

Netbox storage
----------------------

Uses netbox as storage.

.. code-block:: yaml

    storage:
      default:
        adapter: netbox
        params:
          url: http://127.0.0.1:8000
          token: 1234567890abcdef01234567890abcdef0123456


URL and token may be provided using ``NETBOX_URL`` and ``NETBOX_TOKEN`` environment variable.

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
