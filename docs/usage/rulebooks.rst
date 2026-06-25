Rulebooks
=========

A **rulebook** tells Annet *how to turn a diff into device commands, in what order to send
them, and how to deploy them*. Where a generator decides **what** the configuration should look
like, a rulebook decides **how to get the device there**.

Remember the Annet pipeline:

#. ``annet gen`` builds the target config.
#. ``annet diff`` compares it with the current config and produces a **diff**.
#. ``annet patch`` turns that diff into a **patch** — the actual ``undo`` / ``no`` / ``delete``
   and configuration commands.
#. ``annet deploy`` sends the patch to the device.

Steps 3 and 4 are where rulebooks mostly act — though the ordering rulebook also tidies the
generated config back at steps 1–2 (more on that below). Most of the time the built-in rulebooks
already do the right thing and you never touch them. You reach for a rulebook when a vendor needs
something special — a command that must be removed in an unusual way, a block that must be sent
before another, or a device that asks ``Are you sure? [Y/N]`` and waits for an answer.

This page assumes you already know the :doc:`ACL language <acl>`: rulebooks reuse the same
matching syntax (indentation, ``*`` and ``~``). It starts simple and adds the advanced parts at
the end.


The three kinds of rulebook
---------------------------

There are three rulebook types, each a plain-text file with its own extension:

.. list-table::
   :header-rows: 1
   :widths: 15 20 65

   * - Extension
     - Type
     - Answers the question…
   * - ``.rul``
     - patching
     - *How do I build the commands from the diff?*
   * - ``.order``
     - ordering
     - *In what order do I send the commands?*
   * - ``.deploy``
     - deploying
     - *How do I send each command and answer prompts?*

Rulebooks are **per vendor**. They live in a Python package (the default one is
``annet.rulebook.texts``) and are named after the device vendor:

.. code-block:: text

    annet/rulebook/texts/
        huawei.rul      huawei.order      huawei.deploy
        cisco.rul       cisco.order       cisco.deploy
        juniper.rul     juniper.order
        ...

Only the patching file (``<vendor>.rul``) is required, and it must be named **exactly** after
the device's vendor. The ordering and deploying files are optional — if a vendor has no
``.order`` or ``.deploy`` file, Annet simply uses sensible defaults.

A minimal set of rulebooks for an imaginary vendor ``acme`` might be:

``acme.rul``

.. code-block:: text

    hostname *
    interface *
        description ~
        mtu *

``acme.order``

.. code-block:: text

    hostname
    interface

``acme.deploy``

.. code-block:: text

    reload
        dialog: Proceed with reload? [confirm] ::: y


Patching rulebooks (``.rul``)
-----------------------------

A patching rulebook is a list of rules, one per line, using the same matching syntax as ACLs.
Each rule matches a configuration line and describes how to produce commands for it.

The simplest possible rule is just the command:

.. code-block:: text

    hostname *

Read this as: *"a line that starts with ``hostname`` followed by one word is a hostname
command."*


``*`` and ``~``, and why they matter for removal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You already know ``*`` (one word) and ``~`` (the rest of the line) from ACLs. In a patching
rulebook they do one extra job: **the values they match are remembered and reused to build the
removal command.**

Suppose the diff changes a syslog server:

.. code-block:: diff

    - syslog-server 192.168.18.1
    + syslog-server 192.168.18.2

If the rulebook rule has a placeholder:

.. code-block:: text

    syslog-server *

then Annet knows the old value and can remove it explicitly, producing:

.. code-block:: text

    undo syslog-server 192.168.18.1
    syslog-server 192.168.18.2

But if the rule has **no** placeholder:

.. code-block:: text

    syslog-server

then Annet treats the command as a simple toggle and does **not** generate a removal — it just
sets the new value:

.. code-block:: text

    syslog-server 192.168.18.2

This is the single most important thing to understand about ``.rul`` files: **a placeholder
makes a command removable; no placeholder means "just overwrite, never undo".** The exact
removal keyword (``undo`` for Huawei, ``no`` for Cisco, ``delete`` for Juniper, …) is chosen
automatically from the file's vendor — you never write it in a plain rule.

.. note::

   This is the rulebook side of the "capturing only matters for rulebooks" note in the
   :doc:`ACL docs <acl>`. You do **not** need any special capture syntax here — plain ``*`` and
   ``~`` are all you use. The values they matched are passed to custom logic as the ``key`` (see
   below).


Nested blocks
~~~~~~~~~~~~~

Just like ACLs, indentation builds blocks:

.. code-block:: text

    interface *
        description ~
        ip address * *

A child rule is only used inside a matched parent. Removing a whole ``interface`` block, or just
one setting inside it, follows naturally from the structure.


Excluding lines with ``!``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Prefix a rule with ``!`` to tell Annet to **leave matching lines completely alone** — never
generate an add or a remove for them:

.. code-block:: text

    !vrf context management

This is useful for config that exists on the device but is managed out of band.


Custom patch logic: ``%logic``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default every rule is processed by a built-in function called ``default`` that implements the
"add it, or undo it" behaviour described above. When a vendor needs something cleverer, point the
rule at your own function with ``%logic=``:

.. code-block:: text

    ip ssh version 2 %logic=annet.rulebook.cisco.misc.ssh_key

``%logic`` lets you generate *extra* commands, *suppress* commands, or *rewrite* them. Here is a
real example — enabling SSH on Cisco also needs a key to be generated, which the running config
never shows, so the logic emits an additional command:

.. code-block:: python

    def ssh_key(rule, key, diff, **_):
        """Enabling ssh also requires generating a key, which the config never shows."""
        if diff[Op.ADDED]:
            added = sorted(x["row"] for x in diff[Op.ADDED])
            if added == ["ip ssh version 2"]:
                yield (False, "crypto key generate rsa general-keys modulus 2048", None)
        yield from common.default(rule, key, diff)

To write your own logic function you need to understand its arguments and what it yields. A
logic function always has the signature ``def fn(rule, key, diff, **_)``. To make the three
positional arguments concrete, we'll follow one sample rule through — ``snmp-agent sys-info *``
(Huawei: sets the SNMP contact, location, etc.):

.. code-block:: text

    snmp-agent sys-info * %logic=mycompany.rulebook.huawei.snmp.sys_info

**Argument 1 — ``rule``**: a dict describing the matched rule. The fields you will use most are:

.. code-block:: python

    {
        # compiled regexp used to parse the config line
        "regexp": re.compile(r"^snmp-agent\s+sys-info\s+([^\s]+).*$"),
        # template for the removal command; {} placeholders are filled from `key`
        "reverse": "undo snmp-agent sys-info {}",
        # ... plus the rule's params (comment, multiline, context, …)
    }

**Argument 2 — ``key``**: a tuple of the values that ``*`` / ``~`` matched on the line. For the
line ``snmp-agent sys-info contact`` matched by ``snmp-agent sys-info *`` the key is
``("contact",)``. This is what you pass to ``rule["reverse"].format(*key)`` to build a removal
command.

**Argument 3 — ``diff``**: a dict that groups what changed for this command, keyed by operation:

.. code-block:: python

    {
        Op.ADDED:     [{"row": "...", "children": None}],  # present only in the new config
        Op.REMOVED:   [{"row": "...", "children": None}],  # present only in the old config
        Op.AFFECTED:  [],                                  # a block whose children changed
        Op.MOVED:     [],                                  # same line, different position
        Op.UNCHANGED: [{"row": "...", "children": None}],  # unchanged (sometimes needed for context)
    }

Each entry is ``{"row": <text>, "children": <subtree or None>}``.

**The ``**_`` (extra keyword arguments)**: besides those three, Annet always passes a few more
keyword arguments. Most functions don't need them and swallow them with ``**_`` (or ``**kwargs``
if they want to forward them to ``common.default``). They are:

- ``hw`` — the device's ``HardwareView``, so the logic can branch on the exact model
  (``if hw.Huawei.CE: ...``).
- ``rule_pre`` — the full pre-computed data for *this* rule: ``{"rule": <text>, "attrs": ...,
  "items": {key: diff, ...}}``. ``rule`` (argument 1) is just its ``attrs``; ``rule_pre`` also
  lets you see the rule's *other* keys and their diffs, not only the one you were called for.
- ``root_pre`` — the same structure for the **whole** patch, keyed by rule text. Use it to peek
  at sibling commands elsewhere in the config when one command's patch depends on another.

You only reach for these in advanced cases; the vast majority of logic functions use just
``rule``, ``key`` and ``diff``.

**What you yield**: tuples of ``(is_forward, command, children)``.

The first element flags whether ``command`` is a **forward** (configuration) command or a
**removal** command — i.e. is this a ``hostname foo`` or a ``no hostname foo``? Annet can't tell
from the text alone (vendors differ), so you say so explicitly. It affects two things:

- **Ordering.** The flag is passed to the ordering rulebook as the command's direction. In
  particular, ``%order_reverse`` rules only act on removal commands, and removals are grouped/
  sorted separately from forward commands.
- **Block nesting.** A *forward* command on a block rule opens a nested block that Annet
  descends into (via ``children``); a *removal* command is always emitted as a single flat line
  (you delete the whole block in one ``no …`` / ``undo …``, you don't descend into it).

So:

- ``(True, row, children)`` — emit ``row`` as a forward command. If ``children`` is not ``None``
  it is a block and Annet recurses into it.
- ``(False, row, None)`` — emit ``row`` as a removal command (usually built from
  ``rule["reverse"].format(*key)``).
- yielding nothing emits no command for this rule.

The built-in ``default`` does exactly this: ``True`` for an added/changed line, and ``False``
for the ``reverse`` command it builds when a line is removed.

In practice most custom functions handle their one special case and then delegate everything
else to the built-in default:

.. code-block:: python

    yield from common.default(rule, key, diff)

There are several ready-made logic functions in ``annet.rulebook.common`` you can point
``%logic`` at directly, without writing any Python:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Function
     - Behaviour
   * - ``default``
     - the standard add / undo behaviour (used when ``%logic`` is omitted)
   * - ``permanent``
     - never delete this command, even when it leaves the config
   * - ``rewrite``
     - re-create the block from scratch instead of diffing it
   * - ``ignore_changes``
     - add or remove lines, but never replace one value with another
   * - ``undo_redo``
     - remove the old command first, then add the new one (two steps)
   * - ``default_instead_undo``
     - return to the default state with ``default …`` instead of ``no …``


Custom diff logic: ``%diff_logic``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``%logic`` works on a single command. ``%diff_logic`` works one level up: it controls **how the
diff of a whole block is computed** before the patch logic runs. Use it when "what changed" needs
massaging — for example, when a vendor reorders arguments and you want to treat two differently
written lines as equal.

.. code-block:: text

    ntp server * %diff_logic=annet.rulebook.cisco.misc.case_insensitive_diff

A diff-logic function receives the old and new subtrees and returns a list of ``DiffItem``\ s:

.. code-block:: python

    def case_insensitive_diff(old, new, diff_pre, _pops=(Op.AFFECTED,)):
        old = _change_keys(old, str.lower)
        new = _change_keys(new, str.lower)
        diff_pre = _change_keys(diff_pre, str.lower)
        return common.default_diff(old, new, diff_pre, _pops)

The arguments are:

- ``old`` / ``new`` — ordered dicts of the block's children in the old and new config (each value
  is itself a subtree of children).
- ``diff_pre`` — Annet's internal pre-computed diff metadata for these rows (pass it straight
  through to ``common.default_diff``).
- ``_pops`` — the chain of parent operations, used internally; forward it unchanged.

A ``DiffItem`` is a named tuple ``(op, row, children, diff_pre)``. The usual pattern is to call
``common.default_diff(...)`` to get the normal list and then filter or tweak it, as the real
``vlan_diff`` and ``local_user_diff`` helpers do. As with ``%logic``, ``annet.rulebook.common``
ships ready-made diff functions: ``default_diff``, ``ordered_diff``, ``rewrite_diff`` and
``multiline_diff``.


Other patching params
~~~~~~~~~~~~~~~~~~~~~

These flags cover the most common special cases, so you rarely need to write Python at all:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Param
     - Effect
   * - ``%global``
     - the rule (and its behaviour) applies at **any** depth below, not just here
   * - ``%ordered``
     - the block's children are order-sensitive; reordering them re-creates the block
   * - ``%rewrite``
     - replace the whole block from scratch instead of diffing it line by line
   * - ``%multiline``
     - treat a multi-line value (e.g. an RSA key) as one indivisible command
   * - ``%ignore_case``
     - match and compare this command case-insensitively
   * - ``%force_commit``
     - the resulting command only makes sense after a commit; skip it in no-commit mode
   * - ``%context``
     - tag the rule with a named context (paired with ``%ifcontext`` in deploy)

``%ordered``, ``%rewrite`` and ``%multiline`` are shortcuts that set matching ``%logic`` /
``%diff_logic`` for you, so you cannot combine them with an explicit ``%logic`` / ``%diff_logic``
on the same rule.


Ordering rulebooks (``.order``)
-------------------------------

Some commands only work if they are sent in the right order — you must create a ``tacacs-server``
before an ``aaa`` block can reference it, and you must delete them the other way around. An
ordering rulebook is simply the list of commands **in the order they should be applied**:

.. code-block:: text

    tacacs-server
    aaa

Commands are sent following this top-to-bottom order. **If the order of a command does not
matter, leave it out** — only list what needs to be constrained.

Like patching rules, ordering rules can nest, and they automatically understand the vendor's
removal form (``undo …`` / ``no …`` / ``delete …``).


Reversing the order of removals: ``%order_reverse``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default a removal sits in the same slot as the command it removes. But dependencies run
backwards when you tear things down: you must remove the reference in ``aaa`` *before* removing
the ``tacacs-server`` it points at. ``%order_reverse`` lets you place the removal command at its
own position:

.. code-block:: text

    tacacs-server
    aaa
    no tacacs-server %order_reverse

Now additions go ``tacacs-server`` → ``aaa`` (top to bottom), but the removal ``no
tacacs-server`` is emitted **after** the ``aaa`` changes, at the position written here.

``%order_reverse`` only affects **removal** commands (``undo`` / ``no`` / ``delete``). For a
forward command it does nothing — so you write it on a rule whose text is the removal form
itself, as in ``no tacacs-server %order_reverse`` above.

.. tip::

   If a rule uses custom ``%logic`` or ``%diff_logic`` in the patching rulebook, it is good
   practice to also list it in the ordering rulebook so its position is well defined.


Other ordering params
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Param
     - Effect
   * - ``%global``
     - the ordering rule applies at any nesting level
   * - ``%split``
     - the rule may appear **several times**, splitting a block into ordered phases
       (e.g. ``remove`` all members, then ``add`` the new ones)
   * - ``%scope=patch``
     - restrict the rule to the patch-ordering pass (see below)

Annet orders things in **two** situations: it orders the **generated config** (to produce a
stable, canonical representation for ``gen`` and ``diff``), and it orders the **patch** (the
command sequence that is actually sent to the device). The same ordering rulebook drives both.
By default a rule applies to both passes; ``%scope=patch`` limits it to the patch pass only, so
it changes the order commands are sent in without disturbing how the config itself is laid out.

``%split`` is what lets you express "remove first, then add" within one block:

.. code-block:: text

    interface
        bridge
            vlan %split
                remove
            vlan %split
                add


Deploy rulebooks (``.deploy``)
------------------------------

A deploy rulebook controls *how each command is actually pushed to the device*: how long to wait,
whether the device asks an interactive question, and what to answer.

The most common use is **answering prompts**. Many devices ask for confirmation before a
dangerous command. A ``dialog:`` line says "when you see this question, send this answer":

.. code-block:: text

    undo bgp
        dialog: Warning: The BGP process will be deleted. Continue? [Y/N]: ::: Y

The format is ``dialog: <question> ::: <answer>``. The question is matched as a **substring** of
the device's output (whitespace and case are ignored). To match with a regular expression
instead, wrap the question in slashes:

.. code-block:: text

    undo rsa peer-public-key
        dialog: /Do you want to remove the public key named .*\? \[Y/N\]:/ ::: Y

A deploy rule is matched against the command being sent (hierarchically, like the other
rulebooks); if nothing matches, sensible defaults are used.


Deploy params
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Param
     - Effect
   * - ``%timeout=``
     - how long to wait for the command to finish, in seconds (default ``30``)
   * - ``%send_nl``
     - whether to send a newline after the answer (default ``true``; set on a ``dialog:`` line)
   * - ``%suppress_errors``
     - do not treat an error from this command as a failure
   * - ``%ifcontext=``
     - only apply this rule in a named context (paired with ``%context`` from the patching
       rulebook)
   * - ``%apply_logic=``
     - custom Python that returns extra commands to run before/after (e.g. a ``write memory``
       after commit)

Example putting several of these together:

.. code-block:: text

    commit %timeout=180
    no snmp-server sysobjectid type stack-oid %suppress_errors
    port mode 200GE interface * %timeout=40 %suppress_errors

An ``%apply_logic`` function returns two command lists — commands to run *before* and *after* the
patch:

.. code-block:: python

    def apply(hw, do_commit, do_finalize, **_):
        before, after = CommandList(), CommandList()
        if do_commit:
            after.add_cmd(Command("write memory"))
        return before, after

It is called as ``apply(hw, do_commit=..., do_finalize=..., path=...)``, so the arguments are:

- ``hw`` — the device's ``HardwareView`` (branch on model if needed).
- ``do_commit`` — whether this deploy will commit the changes.
- ``do_finalize`` — whether this deploy will run the finalizing steps.
- ``path`` — the device/config path being deployed, or ``None``.

Just like ``%logic``, most functions only need a couple of these and swallow the rest with
``**_`` — the example above ignores ``path`` entirely.


Mako templates
--------------

Before a rulebook is parsed, its text is rendered with `Mako <https://www.makotemplates.org>`_,
and the device's hardware object ``hw`` is available. This lets one rulebook adapt to different
models of the same vendor:

.. code-block:: text

    %if hw.Huawei.CE or hw.Huawei.Quidway:
    stp edged-port
    %else:    # other models take an argument
    stp edged-port *
    %endif

You can use ``${...}`` substitutions and ``%for`` loops too. Two things to keep in mind:

- A line starting with ``%`` that is **not** a Mako keyword (``%if``, ``%else``, ``%elif``,
  ``%endif``, ``%for``, ``%endfor``) is treated as a normal rulebook param, so ``%global``,
  ``%logic`` and friends are safe to write at the start of a line.
- Lines starting with ``#`` are comments and are stripped out.


Writing your own rulebooks
--------------------------

When you need to customise behaviour for your fleet, **do not copy a whole built-in rulebook and
edit it** — you would then have to re-merge every upstream change by hand. Instead, create your
own rulebook package and **inherit** from the built-in one, overriding only what you need.


Inheriting with ``%inherit_from``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Put ``%inherit_from=`` on the **very first line** of your file, pointing at the parent rulebook
(``module.vendor``, without the extension):

.. code-block:: text

    %inherit_from=annet.rulebook.texts.huawei

    # only the rules below differ from the built-in Huawei rulebook
    bgp %logic=mycompany.rulebook.huawei.bgp.special

Annet loads the parent, loads your file, and **merges** them. A rule with the same text as one in
the parent is merged into it (your params win, and child blocks merge recursively); a rule that
does not exist in the parent is added. Only one ``%inherit_from`` is allowed per file, and it must
be the first line.

To **remove** an inherited rule rather than override it, mark it with ``%not_inherit``:

.. code-block:: text

    %inherit_from=annet.rulebook.texts.huawei

    stp disable %not_inherit

The merge rules differ slightly per type:

- **Patching** — rules merge by their text; child params and child sub-blocks override/merge
  with the parent's.
- **Ordering** — works by *anchoring*; this one is worth a closer look, see the next section.
- **Deploy** — both rules and their ``dialog:`` answers are merged; ``%not_inherit`` drops an
  inherited rule or dialog.


How ordering inheritance works
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An ordering rulebook is fundamentally **a sequence**, so "merging" two sequences needs a rule for
*where* the child's lines land. The mechanism is **anchoring**, and once you see it, it stops
being mysterious.

Your child file does **not** restate the whole order. Instead, Annet reads it like this:

- Rules are matched between parent and child **by their exact command text** (params such as
  ``%order_reverse`` don't affect matching). A rule that exists in **both** files is an
  **anchor** — a fixed point that pins the child to the parent.
- A rule that exists only in the child is a **new** rule. It is inserted relative to the nearest
  anchor **above it** in your child file: by default, right *after* that anchor.
- The anchors you mention must appear in the **same relative order** as in the parent. You cannot
  reorder existing rules from a child — the parent owns the order. Listing anchors out of order
  raises *"The relative order of rules must stay the same in both parent and child rulebooks."*

A worked example. Say the built-in ``acme.order`` is:

.. code-block:: text

    hostname
    ntp
    logging
    snmp
    interface

and your child rulebook is:

.. code-block:: text

    %inherit_from=annet.rulebook.texts.acme

    hostname
    my-banner
    interface

``hostname`` and ``interface`` exist in both files, so they are **anchors**. ``my-banner`` is
new, and it sits after the ``hostname`` anchor, so the merged order becomes:

.. code-block:: text

    hostname
    my-banner       ← inserted right after its anchor
    ntp
    logging
    snmp
    interface

Notice you only had to name the two anchors around your insertion point — you never repeated
``ntp``, ``logging`` or ``snmp``.


Pushing a rule to the end of a group: ``%insert_to_end_group``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The span between two of *your* anchors is a **group**. By default a new rule goes to the **top**
of its group (right after the opening anchor). Add ``%insert_to_end_group`` to send it to the
**bottom** of the group instead — right before the next anchor, after all the parent rules in
between:

.. code-block:: text

    %inherit_from=annet.rulebook.texts.acme

    hostname
    my-banner
    my-cleanup %insert_to_end_group
    interface

Both ``my-banner`` and ``my-cleanup`` are anchored to ``hostname`` (the group runs from
``hostname`` to ``interface``), but they land at opposite ends of it:

.. code-block:: text

    hostname
    my-banner            ← top of the group (right after the anchor)
    ntp
    logging
    snmp
    my-cleanup           ← bottom of the group (right before the next anchor)
    interface


Repeating a rule: ``%split``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Normally a command may appear only **once** in an ordering rulebook (listing it twice is an
error, because its position would be ambiguous). Some blocks genuinely need a command in two
places — e.g. remove all VLANs, then later add the new ones. Mark such a rule with ``%split`` in
**both** the parent and the child so it is allowed to repeat, and each occurrence acts as its own
anchor:

.. code-block:: text

    interface
        bridge
            vlan %split
                remove
            vlan %split
                add


Pointing Annet at your rulebooks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tell Annet which package holds your rulebooks via the ``rulebook.module`` setting in your context
config (``context.yml``):

.. code-block:: yaml

    rulebook:
      default:
        module: mycompany.rulebook.texts

    context:
      default:
        rulebook: default
        # ... your other context settings

The default, if you do not set this, is ``annet.rulebook.texts``.

Two requirements for the package to be discoverable:

#. It is loaded with ``importlib.resources``, so every directory in the path must be a real
   Python package — **don't forget the** ``__init__.py`` in your rulebook folder (and in the
   packages holding any ``%logic`` / ``%diff_logic`` / ``%apply_logic`` modules).
#. The patching file must be named exactly ``<vendor>.rul`` to match the device's vendor;
   ``<vendor>.order`` and ``<vendor>.deploy`` are optional.


Reference
---------

Patching (``.rul``) params
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Param
     - Meaning
   * - ``%global``
     - apply the rule at any nesting depth below this point
   * - ``%logic=``
     - custom function to build commands for a single matched rule
   * - ``%diff_logic=``
     - custom function to compute the diff of a whole block
   * - ``%ordered``
     - the block's children are order-sensitive
   * - ``%rewrite``
     - re-create the block from scratch instead of diffing it
   * - ``%multiline``
     - treat a multi-line value as one indivisible command
   * - ``%ignore_case``
     - match and compare case-insensitively
   * - ``%force_commit``
     - skip the produced command when running without a commit
   * - ``%context=``
     - tag the rule with a named context
   * - ``%not_inherit``
     - when inheriting, drop this rule from the parent
   * - ``%inherit_from=``
     - (first line only) inherit from another rulebook
   * - ``!`` prefix
     - exclude matching lines from patching entirely

Ordering (``.order``) params
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Param
     - Meaning
   * - ``%order_reverse``
     - place the command at this position, but only for its **removal** form (no-op for forward
       commands)
   * - ``%global``
     - apply the ordering rule at any nesting level
   * - ``%split``
     - allow the rule to appear several times, splitting a block into phases
   * - ``%insert_to_end_group``
     - when inheriting, place this new rule at the end of its group (before the next anchor)
       instead of right after the preceding anchor
   * - ``%scope=patch``
     - restrict the rule to the patch-ordering pass (not the config-ordering pass)
   * - ``%not_inherit``
     - when inheriting, drop this rule from the parent
   * - ``%inherit_from=``
     - (first line only) inherit from another rulebook

Deploy (``.deploy``) params
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Param
     - Meaning
   * - ``dialog: q ::: a``
     - answer the device prompt ``q`` with ``a`` (``/regex/`` for a regex question)
   * - ``%timeout=``
     - seconds to wait for the command (default ``30``)
   * - ``%send_nl``
     - send a trailing newline with the answer (default ``true``)
   * - ``%suppress_errors``
     - do not treat an error from this command as a failure
   * - ``%ifcontext=``
     - only apply in the named context
   * - ``%apply_logic=``
     - custom function returning before/after command lists
   * - ``%not_inherit``
     - when inheriting, drop this rule or dialog from the parent
   * - ``%inherit_from=``
     - (first line only) inherit from another rulebook

Built-in ``%logic`` functions (``annet.rulebook.common``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``default``, ``permanent``, ``rewrite``, ``ordered``, ``ignore_changes``, ``undo_redo``,
``default_instead_undo``.

Built-in ``%diff_logic`` functions (``annet.rulebook.common``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``default_diff``, ``ordered_diff``, ``rewrite_diff``, ``multiline_diff``.
