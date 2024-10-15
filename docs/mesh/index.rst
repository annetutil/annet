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

* ``{var}`` means a variable containing any non-negative integer number. You will be abel to access it in your handler as an integer attribute.
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
    def bar(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
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

Variables captured from hostname are available via ``.match`` attribute of ``GlobalOptions``, ``DirectPeer`` and ``IndirectPeer`` objects.

.. code-block:: python

    @registry.device("host-{num}.{domain:.*}")
    def foo(global_opts: GlobalOptions):
        print(global_opts.match.num)

Accessing device data
------------------------------

Device instance is accessible via ``.device`` attribute of ``GlobalOptions``, ``DirectPeer`` and ``IndirectPeer`` objects.
``DirectPeer`` additionally has ``ports`` field with names of interfaces used for a connection between devices
(the order is preserved for both sides)

.. code-block:: python

    @registry.direct("host-{num}.{domain:.*}", "host-{num}.{domain:.*}")
    def bar(local: DirectPeer, neighbor: DirectPeer, session: MeshSession):
        print(local.device.fqdn)
        print(local.device.ports)



Filling mesh data
------------------------

Each handler can fill predefined attributes in ``GlobalOptions``, ``DirectPeer``, ``IndirectPeer`` and ``Session`` objects,
this includes peer groups, vrf, interfaces used for BGP session and various options.

Configuration, received from different handlers will be merged together.
You cannot set different values for the same option in different handlers, but complex objects are merged recursively.
``Session`` object contains data which is applied to both peers.

Minimum of data required to be filled is ``DirectPeer`` and ``IndirectPeer``

* ``addr``
* ``remote_as``
* ``families``


Bgp session is expected to be set on single interface and you can choose it from these options:

* *(default)* the single physical interface through which the connection is made (with validation if it is the only one)
* sub-interface in case it is the one interface available
* lag, containing all interfaces holding the connection between devices
* subif for the lag
* svi

The selection is done using ``lag``, ``svi`` or ``subif`` attributes correspondingly.


Accessing mesh data from generators
****************************************

Mesh is not processed automatically, to use it from generator you need:

* Import your ``MeshRulesRegistry`` instance. You can use ``registry.include`` to combine rules from multiple registries.
* Create executor: ``MeshExecutor(registry, device.storage)``
* Run it against the device ``res = executor.execute_for(device)``. Additionally to the result, the device can be modified to store additional interfaces
* Use the result or patched device to generate BGP configuration.