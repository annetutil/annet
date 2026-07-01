from collections.abc import Iterator
from typing import Any, List

from annet.generators import BaseGenerator, PartialGenerator
from annet.storage import Storage


# ====
class Lldp(PartialGenerator):
    TAGS = ["mgmt", "lldp"]

    def acl_huawei(self, device: Any) -> str:
        return """
            lldp
        """

    def run_huawei(self, device: Any) -> Iterator[str]:
        yield "lldp enable"

        if device.hw.CE:
            yield "lldp transmit interval 10"

    def acl_nexus(self, device: Any) -> str:
        return """
            feature lldp
            lldp
        """

    def run_nexus(self, device: Any) -> Iterator[str]:
        yield "feature lldp"
        yield "lldp timer 10"

    def acl_juniper(self, _: Any) -> str:
        return """
        protocols    %cant_delete
            lldp
                *
        """

    def run_juniper(self, device: Any) -> Iterator[str]:
        with self.multiblock("protocols", "lldp"):
            yield """
                neighbour-port-info-display port-id
                port-description-type interface-alias
                port-id-subtype interface-name
                interface all
            """

    def acl_b4com(self, device: Any) -> str:
        return """
        lldp *
        interface *
         lldp-agent
            *
        """

    def run_b4com(self, device: Any) -> Iterator[str]:
        yield """
        lldp run
        lldp tlv-select basic-mgmt port-description
        lldp tlv-select basic-mgmt system-name
        lldp tlv-select basic-mgmt system-capabilities
        lldp tlv-select basic-mgmt system-description
        lldp tlv-select basic-mgmt management-address
        """
        for iface in device.interfaces:
            with self.multiblock(f"interface {iface.name}"):
                with self.multiblock("lldp-agent"):
                    yield """
                    set lldp enable txrx
                    set lldp chassis-id-tlv ip-address
                    set lldp port-id-tlv if-name
                    lldp tlv basic-mgmt system-name select
                    lldp tlv basic-mgmt system-description select
                    """


def get_generators(store: Storage) -> List[BaseGenerator]:
    return [
        Lldp(store),
    ]
