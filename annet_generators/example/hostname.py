from collections.abc import Iterator
from typing import Any, List

from annet.generators import BaseGenerator, PartialGenerator
from annet.storage import Storage


class Hostname(PartialGenerator):
    TAGS = ["hostname"]

    def acl_huawei(self, _: Any) -> str:
        return """
        sysname
        header
        """

    def acl_safe_huawei(self, _: Any) -> str:
        return """
        sysname
        header
        """

    def run_huawei(self, device: Any) -> Iterator[str | tuple[str, str]]:
        yield "sysname", device.hostname
        yield 'header login information "%s"' % device.hostname

    def acl_cisco(self, _: Any) -> str:
        return """
            hostname
            banner login
        """

    def acl_safe_cisco(self, _: Any) -> str:
        return """
            hostname
            banner login
        """

    def run_cisco(self, device: Any) -> Iterator[str | tuple[str, str]]:
        if device.hw.Cisco.AIR and device.tags["Lightweight WiFi точка"]:
            return
        elif device.hw.Catalyst:
            yield "banner login ^C%s^C" % device.hostname
        yield "hostname", device.hostname

    def acl_arista(self, _: Any) -> str:
        return """
            hostname
        """

    def acl_safe_arista(self, _: Any) -> str:
        return """
            hostname
        """

    def run_arista(self, device: Any) -> Iterator[str | tuple[str, str]]:
        yield "hostname", device.hostname

    acl_nexus = acl_arista
    run_nexus = run_arista

    def acl_juniper(self, _: Any) -> str:
        return """
            system  %cant_delete
                host-name
        """

    def acl_safe_juniper(self, _: Any) -> str:
        return """
            system  %cant_delete
                host-name
        """

    def run_juniper(self, device: Any) -> Iterator[str | tuple[str, str]]:
        with self.block("system"):
            yield "host-name", device.hostname

    acl_ribbon = acl_juniper
    acl_safe_ribbon = acl_safe_juniper
    run_ribbon = run_juniper

    def acl_nokia(self, _: Any) -> str:
        return """
            system
                name
        """

    def acl_safe_nokia(self, _: Any) -> str:
        return """
            system
                name
        """

    def run_nokia(self, device: Any) -> Iterator[str | tuple[str, str]]:
        with self.block("system"):
            yield "name", self.literal(device.hostname)

    def acl_routeros(self, _: Any) -> str:
        return """
        system              %cant_delete
            identity        %cant_delete
                set ~       %cant_delete
        """

    def run_routeros(self, device: Any) -> Iterator[str]:
        with self.block("system"):
            with self.block("identity"):
                yield f"set name={device.hostname}"


def get_generators(store: Storage) -> List[BaseGenerator]:
    return [
        Hostname(store),
    ]
