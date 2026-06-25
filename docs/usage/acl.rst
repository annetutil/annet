ACL Language
============

The ACL language is a small, indentation-based language for **selecting lines of a device
configuration**. You write a list of patterns, Annet matches them against the config, and the
lines that match are the ones Annet works with.

You will meet ACLs in a few places:

- in generators, where the ``acl_<vendor>`` and ``acl_safe_<vendor>`` methods declare which
  part of the config a generator is responsible for;
- when you pass ``--filter-acl`` to limit a command to part of the config;
- in rulebooks, to describe how to turn a diff into a patch;
- in a ``RefGenerator``, to point at the part of the config it refers to.

You do not need to know any of those places to learn the language. This page starts from the
very basics and adds the advanced features at the end.


The basics
----------

Your first rule
~~~~~~~~~~~~~~~

An ACL is just text. Each non-empty line is one **rule** — a pattern that Annet tries to match
against a line of the device config.

The simplest rule is a plain word:

.. code-block:: text

    mpls

A rule matches a config line if the line **starts with the rule, on a word boundary**. So the
rule ``mpls`` above matches all of these config lines:

.. code-block:: text

    mpls
    mpls ldp
    mpls te

…but it does **not** match this one, because ``mplsx`` is a different word:

.. code-block:: text

    mplsx

Think of a bare rule as saying *"this word, and anything that comes after it"*.

.. note::

   Under the hood every rule is turned into a regular expression. ``mpls`` becomes
   ``^mpls(?:\s|$)`` — "starts with ``mpls``, followed by whitespace or the end of the line".
   You never have to write this yourself, but it explains the word-boundary behaviour.


Matching the whole line only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes you want to match a line *exactly* and nothing longer. Add a ``$`` at the end:

.. code-block:: text

    mpls$

Now:

- ``mpls`` → matches
- ``mpls ldp`` → does **not** match


Wildcards
~~~~~~~~~

Most real rules need to match a value that changes — an interface name, an IP address, a VRF.
Two wildcards cover almost everything:

``*`` — match **one word**
    .. code-block:: text

        dns domain *

    matches ``dns domain example.com`` and ``dns domain corp.local``, but not ``dns domain``
    (there is no word) and not ``dns domain a b`` (that is two words).

``~`` — match **the rest of the line** (one or more words)
    .. code-block:: text

        header login information ~

    matches ``header login information Welcome to the router!`` — everything after
    ``information``.

You can use several ``*`` in one rule:

.. code-block:: text

    info-center source * channel *

matches ``info-center source NTP channel 5``.

Because ``~`` swallows everything to the end of the line, it only makes sense as the **last**
token of a rule.


Grouping lines into blocks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Network configs are nested: an interface has settings underneath it, a routing protocol has
sub-settings, and so on. ACLs mirror that nesting with **indentation**.

.. code-block:: text

    system
        host-name

This reads as: *match a ``system`` block, and inside it match the ``host-name`` line.* A child
rule is only considered after its parent has matched, so the structure follows the config:

.. code-block:: text

    system
        host-name router1
        domain-name corp.local

You can nest as deep as you like, and combine blocks with wildcards:

.. code-block:: text

    system
        configuration-database
            ~

Indentation defines nesting for **all** vendors, including JunOS (even though JunOS configs use
braces). Spaces and tabs both work, but the convention in Annet is **four spaces**.


Comments
~~~~~~~~

Anything after a ``#`` is a comment and is ignored:

.. code-block:: text

    system
        host-name      # the device hostname
        # this whole line is a comment too

Extra spaces and tabs inside a rule do not matter — they are collapsed — so you can align
things for readability.


Putting it together
~~~~~~~~~~~~~~~~~~~

A small but complete ACL might look like this:

.. code-block:: text

    # everything this generator manages
    interfaces
        *                       # any interface
            description ~
            mtu *
    routing-options
        static
            route *

Read top to bottom: it selects every interface's ``description`` and ``mtu`` lines, plus every
static route under ``routing-options``.

That is enough to write useful ACLs. The rest of this page covers features you will reach for
less often.


Advanced features
-----------------

Capturing a word by name
~~~~~~~~~~~~~~~~~~~~~~~~

``<name>`` works like ``*`` (it matches one word), but it also remembers the matched word under
that name so other parts of Annet can read it back:

.. code-block:: text

    interface <ifname>

This matches ``interface Eth0`` and captures ``Eth0`` as ``ifname``.

.. note::

   Capturing only matters in :doc:`rulebooks <rulebooks>`, where the captured values are passed
   to the patch and diff logic. In all other uses of ACL (generator ACLs, ``--filter-acl``,
   references) a captured word behaves exactly like a plain ``*`` wildcard, so there is no
   reason to capture. The same applies to the capturing regex forms below (``*/{regex}/`` and
   ``~/{regex}/``).


Regular-expression placeholders
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When plain ``*`` is not precise enough, you can drop a real regular expression into a rule.
There are three forms.

``*/{regex}/`` — match **one word** against a regex, and capture it
    .. code-block:: text

        */(ftp|FTP)/ server acl

    The first word must be ``ftp`` or ``FTP``.

``~/{regex}/`` — match against a regex **without** capturing
    .. code-block:: text

        ip routing vrf ~/(?!MEth|MGMT)/

    Here ``(?!MEth|MGMT)`` is a negative look-ahead: match any VRF *except* ones named
    ``MEth`` or ``MGMT``.

``?/{regex}/`` — like ``~/`` but it can be combined with a trailing ``~``
    .. code-block:: text

        ?/(.*)/permit ~

    This matches a line such as ``0 permit udp any 10.212.32.224 0.0.0.31``: ``?/(.*)/`` eats
    the leading ``0 `` and then ``permit ~`` matches the rest. Inside a ``?/.../`` the ``*``
    and ``(...)`` stay part of the regex instead of being treated as wildcards.

A few rules of thumb for the regex forms:

- The ``?`` in ``?/`` is attached to the ``/``, so it does **not** clash with literal slashes
  in things like interface names (``Eth0/0/1``).
- A ``?/`` or ``~/`` regex matches **greedily up to the last** ``/`` on the line, so it can
  contain anything — slashes, spaces, groups. Because of that, a single rule may contain **at
  most one** ``?/`` or ``~/`` placeholder. Put everything into one regex rather than chaining
  several. (The ``*``, ``*/{regex}/`` and ``<name>`` forms have no such limit and may repeat,
  e.g. ``* * something ~``.)
- Any capturing groups you write inside a ``~/`` or ``?/`` regex are quietly turned into
  non-capturing groups, so only the placeholder itself captures.


Case-insensitive matching
~~~~~~~~~~~~~~~~~~~~~~~~~

Put ``(?i)`` anywhere in a rule to make the whole rule case-insensitive:

.. code-block:: text

    (?i)interface */((LoopBack|Eth-Trunk|.*GE[^.]*|static|.*Ether[^.]*)[^.]\d*$)/

Now ``loopback0`` and ``LoopBack0`` match the same way.


Hiding lines with ``!`` (filter-acl only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In ``--filter-acl`` mode you can prefix a rule with ``!`` to say *"match this, but do not
display it"*:

.. code-block:: text

    interfaces
        *
            !description

This shows every interface but hides its ``description``. The ``!`` prefix only works in
``--filter-acl``; elsewhere it is rejected, because ACLs from different generators get merged
and a hide rule could unpredictably swallow another generator's output.


Modifiers
~~~~~~~~~

A rule can carry **modifiers**, written after it as ``%name`` or ``%name=value``. They tweak how
the rule behaves.

``%global`` — match a whole sub-tree at once
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Normally Annet walks into a block and checks each child line against the child rules. ``%global``
(or ``%global=1``) says *"once this line matches, accept everything underneath it without looking
further"*. This is handy when a whole sub-tree belongs to one generator:

.. code-block:: text

    system
        tacplus-server
            ~ %global

matches the whole block, no matter what is inside it:

.. code-block:: text

    system {
        tacplus-server {
            213.180.205.50 {
                routing-instance mgmt_junos;
                timeout 4;
            }
        }
    }

A ``%global`` rule has no children of its own — the sub-tree is taken as-is.

``%cant_delete`` — keep a line even when the generator stops producing it
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, if a generator's ACL covers a line but the generator stops emitting it, Annet
generates a command to **delete** it. Sometimes that is wrong. Take a JunOS BMP generator with
this ACL:

.. code-block:: text

    routing-options
        bmp
            ~ %global

If the generator outputs nothing, ``ann patch`` would emit ``delete routing-options`` — far too
much. ``%cant_delete`` (or ``%cant_delete=1``) tells Annet *"never generate a delete for these
lines"*:

.. code-block:: text

    routing-options %cant_delete
        bmp
            ~ %global

This modifier is **on by default for any block starting with ``interface``** — Annet will not
delete interfaces unless you opt in. To allow deletion, turn it off explicitly:

.. code-block:: text

    router
        isis
            interface * %cant_delete=0
                ~ %global

When ACLs from several generators are merged, a line is protected only if **every** generator
that matched it asked to protect it. If even one matching generator left ``%cant_delete`` off,
the line stays deletable.

``%prio`` — break ties between overlapping rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When two rules both match the same line, Annet picks a winner by ranking them on
``(prio, specificity)`` — highest ``%prio`` first, and on a tie the rule that shares more
characters with the line (the more specific one). ``%prio`` defaults to ``0``; raise it to force
a rule to win:

.. code-block:: text

    (?i)interface */({iface_match})/ %cant_delete={cant_delete} %prio=100


Reverse (delete) commands
~~~~~~~~~~~~~~~~~~~~~~~~~

Every ACL is compiled **for a single vendor** — that is why a generator has a separate
``acl_huawei``, ``acl_cisco``, ``acl_juniper`` and so on. Each rule then matches in **two**
ways: the line as written, and that vendor's way of **removing** the line (``undo …`` on Huawei,
``no …`` on Cisco, ``delete …`` on Juniper — Annet knows the right prefix for each vendor). So in
a Huawei ACL the rule ``shutdown`` also matches ``undo shutdown``, and in a Juniper ACL the rule
``protocols`` also matches ``delete protocols``.

This mostly matters for :doc:`rulebooks <rulebooks>`, which turn a diff into the actual
``undo`` / ``no`` / ``delete`` commands. In a generator ACL you can rely on it too — you may write
a rule directly against the removal form, e.g. ``undo shutdown`` in a Huawei ACL — but you must
use the prefix that belongs to that ACL's vendor.


Generator ACLs must not overlap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A core principle of Annet is that **exactly one generator is responsible for each section of the
config**. Two generators' ACLs should therefore never select the same line: if they do,
generation stops with an error telling you which generators collide. This keeps responsibility
clear — there is always a single place that owns (and may delete) a given piece of config.

The way to avoid collisions is to **scope your ACL precisely to the part you own**. Do not grab a
whole block when you only manage a piece of it. For example, a BGP generator should declare just
the ``bgp`` subtree, not all of ``protocols``:

.. code-block:: text

    protocols
        bgp
            ~                  %global=1

Here ``protocols`` is only a path to the part this generator owns. Other generators are free to
manage ``protocols ospf``, ``protocols isis`` and so on under the very same parent, and Annet
will not delete the ``protocols`` section just because this generator produced no ``bgp`` — it
never claimed ``protocols`` as a whole. (If you ever *do* need to keep a shared parent line from
being deleted when your part is empty, that is what ``%cant_delete`` above is for.)

.. note::

   This check can be turned off with ``--no-acl-exclusive``, but that flag exists only for
   debugging. Relying on overlapping ACLs goes against Annet's design, so you should never use
   it in production.
