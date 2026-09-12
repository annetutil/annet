CLI Usage
================

Almost all annet calls expect hosts identifiers, like ``ann gen HOST1 HOST2``.
These host identifiers are resolved by the storage adapter. For example, NetBox adapter supports for globs: ``myhost tag:mytag site:mysite`` - will search
for a host with name ``myhost`` or hosts with tag ``mytag`` or hosts with site ``mysite``.

CLI command plugins
*******************

An installed Python package can add a top-level annet command through the
``annet.commands`` entry point group. The entry point name becomes the command
name, and its value must reference a callable decorated with
``annet.argparse.subcommand``.

For example, a separate ``annet-example`` package can declare this entry point in
``pyproject.toml``:

.. code-block:: toml

    [build-system]
    requires = ["setuptools>=61"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "annet-example"
    version = "0.1.0"
    dependencies = ["annet"]

    [project.entry-points."annet.commands"]
    hello = "annet_example.cli:hello"

The exported function uses the same ``Arg`` and ``ArgGroup`` interface as a
built-in command:

.. code-block:: python

    from annet.argparse import Arg, subcommand


    @subcommand(Arg("--name", default="world", help="Name to greet"))
    def hello(name: str) -> None:
        """Print a greeting."""
        print(f"Hello, {name}!")

After installing the package in the same Python environment as annet, the
command is available as:

.. code-block:: bash

    annet hello --name Alice

The command prints ``Hello, Alice!``.

Annet discovers command plugins whenever it builds the CLI. It imports every
entry point in the ``annet.commands`` group at that time. Keep expensive or
optional imports inside the command handler so they run only when the command
is invoked. Entry point import errors are propagated.
Duplicate command names are rejected by ``argparse``, and the top-level name
``help`` is reserved by annet.

Command discovery works for any separately installed package that publishes an
``annet.commands`` entry point; it does not depend on an annet extra. An extra
is only an installation shortcut. After ``annet-example`` is published and its
compatibility is verified, annet can add the following entry to its existing
``extras_require`` in ``setup.py``:

.. code-block:: python

    extras_require={
        "example": ["annet-example"],
    },

Users could then install both packages with:

.. code-block:: bash

    pip install 'annet[example]'

The ``example`` extra is an example of future packaging configuration and is not
currently declared by annet.

annet gen
******************

The annet_generators directory contains many files called generators.
A generator takes information about the switch as input and returns the configuration.
The part of the config that the generator is responsible for is specified in the generator's acl function. If a generator returns a configuration that does not fall under acl, an exception will be thrown.

Example generator:

.. code-block:: python

    from annet.generators import PartialGenerator

    class Mtu(PartialGenerator):
        TAGS = ["mtu"]
        def acl_cisco(self, _):
            return "system mtu jumbo"

        def run_cisco(self, device):
            yield "system mtu jumbo %d" % 9000



And an example of calling annet:

.. code-block:: bash

    annet gen -g mtu sw6-i1
    # -------------------- sw6-i1.cfg --------------------
    system mtu jumbo 9000


Method ``acl_cisco`` defines scope of the generator, which commands and block it controls.
The option ``-g mtu`` means that only generators with the mtu element in the TAGS variable should be called.
If no tag is specified, all generators will be executed.


annet diff
******************

If we were configuring the switch from scratch, these options would be enough, but in our reality we need to be able not only to generate the desired configuration, but also to be able to bring the current configuration to the desired one.
To do this, you need to be able to delete an outdated configuration and correctly add a new one. The **diff** module, which implements some tricky logic, is responsible for this work.
This logic is defined in the rulebook/texts/VENDOR folder.

Example diff:

.. code-block:: diff

    # -------------------- sw1-i38.cfg --------------------
      acl number 2610
    - rule 40 permit source 10.11.170.150 0
    + rule 12 permit source 10.11.133.81 0


annet patch
******************

Next, you need to create a list of commands from the resulting diff. The **patch** module is responsible for this.
It receives the diff, runs the logic specified in rulebook/texts/VENDOR and returns the list of commands.
Let's take the above diff. It says to remove the command ``rule 40 permit source 10.11.170.150 0`` and
add ``rule 12 permit source 10.11.133.81 0``.
Basic command delete logic for huawei is adding undo to the command.
So the undo command will look like this: ``undo rule 40 permit source 10.11.170.150 0``,
but this is an invalid command. In case of canceling acl rules, you need to execute ``undo rule N``.
So you need to write the undo logic for the ``rule`` command in the ``acl`` block.
Here is the part of rulebook/texts/huawei.rul responsible for this:

.. code-block::

    acl name *
        rule * %logic=annet.rulebook.huawei.misc.undo_redo

The asterisk here means that the key argument of the undo_redo function will contain the first word after rule,
namely the rule number.

Here, the ``undo_redo`` function from the file in rulebook/huawei/misc.py is used to generate the command to remove rules in acl.

.. code-block:: python

    def undo_redo(rule, key, diff, **_):
        ...

Now calling ``annet patch -g snmp sw1-i38`` returns the correct set of commands.

.. code-block::

    acl number 2610
      undo rule 40
      rule 12 permit source 10.11.133.81 0
      quit


annet deploy
******************

To apply these commands on a switch there is a **deploy** module.
Annet can apply changes (roll out) to multiple devices at the same time.

By default, the edits that annet proposes to roll out will be shown before the rollout.
The user must confirm that they agree to roll out the proposed diff to a given list of devices.
During the rollout, annet will display the overall progress of the task and the log of one of the devices.

Normal layout. The screen with patches will be shown and the process of laying out will be displayed.

.. code-block:: bash

    annet deploy -g snmp $HOST

Credentials will be used from the current user (username, ssh key, ssh agent).

annet context
******************

The **context** command manages connection contexts for different device groups with varying connection requirements.

Setting a context:

.. code-block:: bash

    # Set default SSH context
    annet context set-context default

    # Set telnet context for legacy devices
    annet context set-context telnet

    # Set custom SSH port context
    annet context set-context ssh-10022

Once a context is set, all subsequent annet commands will use that context's connection settings:

.. code-block:: bash

    # Using default SSH (port 22)
    annet context set-context default
    annet diff -g hostname router1.example.com
    # -------------------- router1.example.com.cfg --------------------
    - hostname Router1
    + hostname router1.example.com

    # Using telnet for legacy devices
    annet context set-context telnet
    annet diff -g hostname legacy-switch.example.com
    # -------------------- legacy-switch.example.com.cfg --------------------
    - hostname OldSwitch
    + hostname legacy-switch.example.com

    # Using custom SSH port
    annet context set-context ssh-10022
    annet diff -g hostname secure-device.example.com
    # -------------------- secure-device.example.com.cfg --------------------
    + system identity set name=secure-device.example.com

Connection Method Examples
**************************

SSH with Standard Port (22)
----------------------------

This is the default connection method:

.. code-block:: bash

    annet context set-context default
    annet gen router.example.com
    annet diff router.example.com
    annet patch router.example.com
    annet deploy router.example.com

SSH with Custom Port
--------------------

For devices using non-standard SSH ports:

.. code-block:: bash

    annet context set-context ssh-10022
    annet gen secure-router.example.com
    annet diff secure-router.example.com
    annet deploy secure-router.example.com

Telnet Connection
-----------------

For legacy devices that only support telnet:

.. code-block:: bash

    annet context set-context telnet
    annet gen legacy-switch.example.com
    annet diff legacy-switch.example.com
    annet deploy legacy-switch.example.com

.. warning::
   Telnet transmits credentials and configuration data in clear text. Use SSH whenever possible for security.
