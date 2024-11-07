Annet - network configuration utility
===============================================

The system contains network appliance config generators written in Python
with optional use of text preprocessors (Jinja2, Mako).

Huawei, Cisco IOS, Cisco NX-OS, Cisco IOS-XR, Juniper, as well as devices configured via separate config files
(Linux, FreeBSD, Cumulus) are supported.

``annet`` has a number of modes (subcommands):

* ``annet gen`` - generates the entire config for the specified devices or specified parts of it
* ``annet diff`` - first does gen and then builds diff with current config version
* ``annet patch`` - first does diff and then generates a list of commands to apply diff on the device

Usage help can be obtained by calling ``annet -h`` or for a specific command, such as ``annet gen -h``.



.. toctree::
   :hidden:
   :caption: Basic usage:

   usage/cli.rst
   usage/config.rst


.. toctree::
   :hidden:
   :caption: Extending:

   mesh/index.rst


.. toctree::
    :hidden:
    :caption: Project Links

    GitHub <https://github.com/annetutil/annet>
    PyPI <https://pypi.org/project/annet>