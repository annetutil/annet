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
    pip install "annet[netbox]" gnetcli_adapter

    # Requires Go; alternatively download gnetcli_server from its releases.
    go install github.com/annetutil/gnetcli/cmd/gnetcli_server@latest
    export PATH="$(go env GOPATH)/bin:$PATH"
    mkdir -p ~/.annet

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
        default:
            adapter: netbox
            params:
                url: http://127.0.0.1:8000
                token: 1234567890abcdef01234567890abcdef0123456
    context:
        default:
            fetcher: default
            deployer: default
            generators: default
            storage: default
    selected_context: default
    EOF

    # write generators
    vim /path/to/myproject/my_generators/__init__.py

    annet deploy mydevice
