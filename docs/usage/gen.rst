Generator - generates configuration
===============================================

Generators are the cornerstone of Annet. Each generator is responsible for generating part of the configuration.
A part must be as small as possible. This will reduce the complexity of a generator and increase the granularity of deployment.

Partial
----------------------

Useful for CLI-based configuration. Must inherit from PartialGenerator.

**acl** function filters out part of the configuration that this generator is responsible for. Also **acl** may filter more precise using Device object.
**run** returns configuration.
**acl** and **run** function are prefixed with device.hw.vendor. For example device with vendor huawei will have acl_huawei and run_huawei functions respectively.

.. code-block:: python

    class Ntp(PartialGenerator):
        def acl_huawei(self, _) -> str:
            return """
            ntp
            """

        def run_huawei(self, device):
            yield "ntp server disable"

Entire
----------------------

For file-based generator. Useful for Linux-based configuration. Must inherit from Entire.
**path** returns the path to the file, if the return value is an empty string, then the generator is not applicable for the device.
**reload** returns a command to reload the configuration. It is not applied if nothing has been changed.

.. code-block:: python

    class Ntp(Entire):
        def path(self, device: Device) -> str:
            if device.hw.vendor == "PC":
                return "/etc/ntp.conf"

        def run(self, device: Device) -> Iterator[str]:
            return """
        restrict 127.0.0.1
        restrict ::1
        server 0.ru.pool.ntp.org iburst
        """

        def reload(self, _) -> str:
            return "systemctl restart ntpd"



JSON-fragment
----------------------

For cases where one file contains configurations for many services. Must inherit from JSONFragment.

.. code-block:: python

    class Dns(JSONFragment):
        def path(self, device: Device) -> str:
            if device.breed == "sonic":
                return "/etc/sonic/config_db.json"

        def acl(self, _) -> str:
            return "/DNS_NAMESERVER"

        def reload(self, device: Device) -> str:
            return "sudo config load -y && sudo config save -y"

        def run(self, device: Device):
            with self.block("DNS_NAMESERVER"):
                for ip in device.ifaces.ips:
                    with self.block(dns_ip):
                        yield {}
