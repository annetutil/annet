Configuration
==========================

The path to the configuration file is searched in following order:

* ``ANN_CONTEXT_CONFIG_PATH`` env.
* ``~/.annet/context.yml``.
* ``~/.annet/context.yaml``.
* ``annet/configs/context.yml``.

.. warning:: The simultaneous existence of ``~/.annet/context.yml`` and ``~/.annet/context.yaml`` is considered an error.

Config example:

.. code-block:: yaml

    generators:
      default:
        - my_annet_generators.example

    storage:
      default:
        adapter: file
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

Storages
************************

Storages provide information about devices like FQDN, interface and so on.

Netbox storage
----------------------

Uses `NetBox <https://netboxlabs.com/docs/netbox/en/stable/>`_ as storage.

.. code-block:: yaml

    storage:
      default:
        adapter: netbox
        params:
          url: http://127.0.0.1:8000
          token: 1234567890abcdef01234567890abcdef0123456
          insecure: true # skip SSL verification
          exact_host_filter: true # for setup where hostname used instead of fqdn


URL and token may be provided using ``NETBOX_URL``, ``NETBOX_TOKEN``, ``NETBOX_EXACT_HOST_FILTER`` and ``NETBOX_INSECURE`` environment variable.

.. code-block:: shell

    export NETBOX_URL="https://demo.netbox.dev"
    export NETBOX_TOKEN="1234567890abcdef01234567890abcdef0123456"

File storage
----------------------

Uses local file as storage.

.. code-block:: yaml

    storage:
      default:
        adapter: file
        params:
          path: /path/to/file


``cat /path/to/file``:

.. code-block:: yaml

    devices:
      - fqdn: myhost.yndx.net
        vendor: mikrotik
        interfaces:
          - name: eth0
            description: test

Fetcher Configuration
************************

The fetcher is responsible for connecting to devices and retrieving their configurations. Annet supports multiple connection methods including SSH (default), SSH on custom ports, and Telnet.

SSH with default port
----------------------

Default SSH connection on port 22:

.. code-block:: yaml

    fetcher:
      default:
        adapter: gnetcli
        params:
          dev_login: username
          dev_password: password

SSH with custom port
----------------------

To connect to devices using a non-standard SSH port:

.. code-block:: yaml

    fetcher:
      ssh-custom:
        adapter: gnetcli
        params:
          dev_login: username
          dev_password: password
          dev_port: 10022
          streamer_type: ssh

Telnet support
----------------------

To connect to legacy devices using Telnet:

.. code-block:: yaml

    fetcher:
      telnet:
        adapter: gnetcli
        params:
          dev_login: username
          dev_password: password
          dev_port: 23
          streamer_type: telnet

.. warning::
   Telnet transmits data in clear text. Use SSH whenever possible for security reasons.

Multiple Contexts
************************

You can define multiple contexts to work with different device groups that require different connection methods:

.. code-block:: yaml

    context:
      default:
        fetcher: default
        deployer: default
        generators: default
        storage: default

      ssh-10022:
        fetcher: ssh-custom
        deployer: default
        generators: default
        storage: default

      telnet:
        fetcher: telnet
        deployer: default
        generators: default
        storage: default

    selected_context: default

Switching between contexts:

.. code-block:: bash

    # Use default SSH context
    annet context set-context default
    annet diff -g hostname mydevice.example.com

    # Switch to telnet context for legacy devices
    annet context set-context telnet
    annet diff -g hostname legacy-switch.example.com

    # Use custom SSH port context
    annet context set-context ssh-10022
    annet diff -g hostname custom-ssh-device.example.com
