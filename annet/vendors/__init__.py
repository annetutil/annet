from annet.connectors import Connector
from annet.vendors.base import AbstractVendor

from .library import (
    arista,
    aruba,
    b4com,
    cisco,
    h3c,
    huawei,
    iosxr,
    juniper,
    nexus,
    nokia,
    optixtrans,
    pc,
    ribbon,
    routeros,
    sitonica,
    snr,
)
from .registry import Registry, registry


class _DefaultRegistry(Registry):
    """Registry variant that shares state with the module-level populated singleton.

    Connector._get_default must return a ``type[Registry]`` that is instantiated by
    ``Connector.get()``. The vendors are registered on the module-level ``registry``
    singleton at import time, so instances of this class reuse that populated state.
    """

    def __init__(self) -> None:
        self.vendors = registry.vendors
        self._matchers = registry._matchers


class _RegistryConnector(Connector[Registry]):
    name = "Registry"
    ep_name = "vendors"

    def _get_default(self) -> type[Registry]:
        return _DefaultRegistry


registry_connector = _RegistryConnector()
