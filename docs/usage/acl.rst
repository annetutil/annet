> Genesis Test Bot:

ACL Language
============

In Annet, there is a special language used for searching and filtering parts of the configuration, called ACL. It is used for:
- Generators, to describe which part of the config they are responsible for (``acl_<vendor>`` and ``acl_safe_<vendor>`` methods);
- Additional config filtering if the ``--filer-acl`` argument is used;
- Rulebooks, to describe how to generate a patch from a diff;
- ``RefGenerator``, to specify which part of the configuration the generator refers to.

ACL consists of strings. For example, the ACL string:

.. code-block::

    mpls


will match both the line ``mpls`` and ``mpls ldp``, and any string fitting the regex ``^mpls(?:\s|$)``.

If you want to match only the string ``mpls``, you need to specify it explicitly:

.. code-block::

    mpls$


In ACL strings, placeholders can be used:
- ``*`` matches a single word (``[^\s]+`` in regex terms);
- ``~`` matches any non-zero number of words (``.+``).

Example:

.. code-block:: text

    dns domain *
    header login information ~
    info-center source * channel *


Placeholders can match by regular expressions:

.. code-block:: text

    */(ftp|FTP)/ server acl
    ip routing vrf ~/(?!MEth|MGMT)/


If you want a case-insensitive match, you can specify it with the ``(?i)`` prefix, for example:

.. code-block:: text

    (?i)interface */((LoopBack|Eth-Trunk|.*GE[^.]*|static|.*Ether[^.]*)[^.]\d*$)/


Strings can be combined into hierarchical blocks, such as:

.. code-block:: text

    system
        host-name


or


.. code-block:: text

    system
        configuration-database
            ~


Indentation defines nesting for all vendors, including JunOS. Both spaces and tabs can be used, but it is customary in Annet to use four spaces.

Only in ``--filer-acl`` mode can you use the ``!`` prefix, which indicates that a string should not be displayed.


.. code-block:: text

    interfaces
        *
            !description


Strings can have modifiers:

- ``%global`` (or ``%global=1``) indicates that the specified string and all nested blocks should be matched. For example, the following ACL:


.. code-block:: text

    system
        tacplus-server
            ~ %global


would match the following configuration:

.. code-block:: text

    system {
        tacplus-server {
            213.180.205.50 {
                routing-instance mgmt_junos;
                timeout 4;
            }
        }
    }


- ``%cant_delete`` (or ``%cant_delete=1``) indicates that delete commands should not be generated for these strings, even if they are not in the generation result. Let's take for example of JunOS BMP's generator with such an ``acl``:


.. code-block:: text

    routing-options
        bmp
            ~ %global


If the generator outputs nothing, ``ann patch`` would generate a delete command ``delete routing-options``. If we want to avoid this, we must use the ``%cant_delete`` modifier:


.. code-block:: text

    routing-options %cant_delete
        bmp
            ~ %global


This modifier is **enabled by default** for blocks starting with ``interface``, so if the generator should be allowed to delete interfaces, the modifier must be **explicitly disabled**, for example:


.. code-block:: text

    router
        isis
            interface * %cant_delete=0
                ~ %global


In rulebooks, other modifiers are available depending on the type of rulebook. In a diff rulebook (``<vendor>.rul``), you can use:
- ``%logic=`` - custom patch logic;
- ``%diff_logic=`` - custom diff logic;
- ``%comment=`` - adds special commands for injection when invoking ``patch`` with ``--add-comments``, for example:

.. code-block:: text

    stp enable %comment=!!question!![Y/N]!!answer!!Y!!


Custom patch logic function overrides ``def default()``. It is invoked for each command with a unique key and should return the generated patch text based on the provided diff. Furthermore, it may need to handle processing of child rules/data if necessary.

The first argument (``rule``) it accepts is a dictionary containing the rule:

.. code-block:: python

    {
        # Single-line command, not a block, has no children
        "logic": <function default at 0x7fe22ea83510>,  # Function for processing the rule
        "provides": [],  # Macros implemented by this rule
        "requires": [],  # Macros required for the rule

        # Regular expression for parsing the line
        "regexp": re.compile(r"^snmp-agent\s+sys-info\s+([^\s]+).*$"),

        # Template for command reversal (arguments should use the key)
        "reverse": "undo snmp-agent sys-info {}",
    }


The second argument (``key``) is a tuple consisting of the key parsed from the line using the regexp:

.. code-block:: python

    ("contact",)  # Example for parsing the line "snmp-agent sys-info contact"


The third argument is a dictionary containing the diff:

.. code-block:: python

    {
        # Commands/blocks added in the new configuration
        Op.ADDED: [{"children": None, "row": "undo snmp-agent sys-info version all"}],

        # Only occurs in blocks, contains changed children within blocks
        Op.AFFECTED: [],

        # Removed commands/blocks
        Op.REMOVED: [{"children": None, "row": "undo snmp-agent sys-info version v3"}],

        # Commands that remain unchanged (but may be needed for other commands)
        Op.UNCHANGED: [{"children": None, "row": "snmp all-interfaces"}]
    }

Example of custom patch function:

.. code-block:: python

    def vty_acl_undo(rule, key, diff, **_):
        if diff[Op.REMOVED]:
            chunks = key[0].split()
            result_chunks = ["undo acl"]
            if len(chunks) == 3 and chunks[0] == "ipv6":
                result_chunks.append("ipv6")
            result_chunks.append(chunks[-1])
            yield False, " ".join(result_chunks), None
        else:
            yield from common.default(rule, key, diff)


Custom diff logic function overrides ``def default_diff()``, where the ``old`` and ``new`` matched config parts (including subblocks) and the calculated diff are passed. It is invoked for each command with a unique key and should return the generated patch text based on the provided diff. Furthermore, it may need to handle processing of child rules/data if necessary.

Example of custom diff function:

.. code-block:: python

    def vlan_diff(old, new, diff_pre, _pops):
        batch_new = set()  # vlan batch ... vlan ids
        for row in new:
            prefix, vlans = _parse_vlancfg(row)
            if prefix == "vlan batch":
                batch_new.update(vlans)
        ret = []
        for item in common.default_diff(old, new, diff_pre, _pops):
            prefix, vlan_ids = _parse_vlancfg(item.row)

            # if the vlan was declared globally and remains in the batch
            # the command undo vlan ... will attempt to completely remove it from the device
            # and from the batch too. At the same time, doing undo vlan ... ; vlan batch ... is not a solution
            # because to delete cli requires to remove all vlanif's and so on
            if prefix == "vlan" and item.op == Op.REMOVED and batch_new.intersection(vlan_ids):
                result_item = common.DiffItem(Op.AFFECTED, item.row, item.children, item.diff_pre)

            # if the vlan is declared globally and simultaneously in the batch
            # and there are no options in the global declaration block
            # do not add it as it will just hang unnecessarily - this way we will preserve
            # symmetry with the previous logic, both invariants will yield an empty patch
            elif prefix == "vlan" and batch_new.intersection(vlan_ids) and not item.children:
                result_item = None

            # vlan batch and everything else we do not touch
            else:
                result_item = item
            if result_item:
                ret.append(result_item)
        return ret


If a command in a diff rulebook is specified without placeholders, an undo command will not be generated for it. For example, if in the rulebook it is written:

.. code-block:: text

    syslog-server


and the diff is:


.. code-block:: diff

    - syslog-server 192.168.18.1
    + syslog-server 192.168.18.2


then the patch will be:

.. code-block:: text

    syslog-server 192.168.18.2


But if the rulebook contains:

.. code-block:: text

    syslog-server *


then the patch will be:

.. code-block:: text

    undo syslog-server 192.168.18.1
    syslog-server 192.168.18.2


In an order rulebook (``<vendor>.order``), you can use the ``%order_reverse`` modifier. It is necessary when you want the undo command to be executed in the reverse order specified in the rulebook. For example, the rulebook may state:

.. code-block:: text

    tacacs-server
    aaa


This means that we first describe the tacacs server and then reference it in ``aaa``. But deletion should occur in reverse order, for which we can use ``%order_reverse``:

.. code-block:: text

    tacacs-server
    aaa
    no tacacs-server %order_reverse


As a result, ``no server ...`` will occur inside the ``aaa`` block first, followed by ``no tacacs-server ...``.

If you are describing custom logic (``%logic=`` or ``%diff_logic=``), it is advisable to describe these commands in the order rulebook.

In the deploy rulebook (``<vendor>.deploy``), you can use:
- ``%timeout=`` - command execution timeout in seconds (default is ``30``);
- ``%send_nl`` - whether to send a newline after the response (default is ``true``).

Additionally, rulebooks can use `Mako template <https://www.makotemplates.org>`_ expressions, where the ``hw`` object is available. For example:

.. code-block:: text

    %if hw.Huawei.Quidway:
    snmp-agent protocol source-interface %logic=huawei.misc.undo_redo
    %else:
    snmp-agent protocol source-interface *
    %endif
