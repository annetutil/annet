Mesh and BGP
==================

With ``annet`` you can configure device BGP session and interfaces based on common rules and connections with other devices.

Configuring mesh
**********************

To setup configuration you need create an instance of ``MeshRulesRegistry`` and attach handlers of 3 types:

* ``.device`` handlers setup device global configuration
* ``.direct`` handlers can be used to setup relation between directly connected devices
* ``.indirect`` handlers can be used to setup configuration related to devices which do not have direct connection

The naming ``.indirect`` reflects the uses cases, it doesn't control to connection of devices: neither they are rechable or connected directly.

.. code-block:: python

    from annet.mesh import (
        MeshRulesRegistry, GlobalOptions, MeshSession, DirectPeer, IndirectPeer,
    )

    registry = MeshRulesRegistry()
    @registry.device("{name:.*}")
    def foo(global_opts: GlobalOptions):
        ...

    @registry.direct("{name:.*}.left.example.com", "{name:.*}.right.example.com")
    def bar(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
        ...

    @registry.indirect("{name:.*}.left.example.com", "{name:.*}.other.example.com")
    def baz(device: IndirectPeer, neighbor: IndirectPeer, session: MeshSession):
        ...


Filtering devices
------------------------

To select handler you set the device filters. They consist of two parts: name mask and filter expression.

**name mask** is a string which describes device FQDN, optionally containing placeholders for captured variables.
Place holders can be of two forms:

* ``{var}`` means a variable containing any positive integer number. You will be abel to access it in your handler as an integer attribute.
* ``{var:regex}`` means a string matching regular expression. You will be abel to access it in your handler as an string attribute.

Additionally, you can set a **filter expression** based on captured variables using *magic* filters.
Use ``Match`` for device handler, and ``Left`` and ``Right`` for direct/indirect handlers.

For example, here

* ``foo`` function will be applied to any device with number from 0 to 100 after ``host-`` prefix in subdomain.
* ``bar`` will be applied to the pair of hosts with same top level domain and where the left number is less than right one

.. code-block:: python

    from annet.mesh import Match, Left, Right

    @registry.device("host-{num}.{domain:.*}", Match.num<100)
    def foo(global_opts: GlobalOptions):
        ...

    @registry.direct(
        "host-{num}.{domain:.*}", "host-{num}.{domain:.*}",
        Left.num < Right.num,
        Left.domain == Right.domain,
    )
    def bar(global_opts: GlobalOptions):
        ...


If you need more complex filters or check not only the FQDN, you should do the check inside handler and return from it without any modifications.

Short name filters
--------------------

Devices are normally filtered based on FQDN, but can set registry to use only short name (subdomain). This is done setting ``match_short_name`` in the registry constructor.
Note, that is only applied for specific registry and does not affect others, even included.

.. code-block:: python

    registry = MeshRulesRegistry(match_short_name=True)

Accessing captured variables
------------------------------

Variables captured from hostname are available via ``.match`` attribute for ``GlobalOptions``, ``DirectPeer`` and ``IndirectPeer`` objects.

.. code-block:: python

    @registry.device("host-{num}.{domain:.*}", Match.num<100)
    def foo(global_opts: GlobalOptions):
        print(global_opts.match.num)


Accessing mesh data from generators
****************************************

