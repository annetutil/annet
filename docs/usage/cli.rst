CLI Usage
================

Almost all annet calls expect hosts identifiers, like ``ann gen HOST1 HOST2``.
These host identifiers are resolved by the storage adapter. For example, NetBox adapter supports for globs: ``myhost tag:mytag site:mysite`` - will search
for a host with name ``myhost`` or hosts with tag ``mytag`` or hosts with site ``mysite``.

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
        rule * %logic=huawei.misc.undo_redo

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
