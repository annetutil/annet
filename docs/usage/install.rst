Installation
================

Install Annet from pypi with `gnetcli <https://annetutil.github.io/gnetcli/>`_ as a deploy driver
and NetBox as a storage.

******************

.. code-block:: bash

    mkdir myproject
    cd myproject
    python3 -m venv venv
    source venv/bin/activate
    pip install annet gnetcli_adapter

    cat > ~/.annet/context.yml<<EOF
    fetcher:
    default:
        adapter: gnetcli
    deployer:
    default:
        adapter: gnetcli
    generators:
    default:
        - /path/to/myproject/my_generators/__init__.py
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

    # write generators
    vim /path/to/myproject/my_generators/__init__.py

    annet deploy mydevice
