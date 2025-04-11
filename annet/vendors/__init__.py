import importlib
import logging
import os.path
from typing import Callable

from annet.connectors import Connector
from annet.vendors.base import AbstractVendor

from .registry import Registry, registry


def import_library():
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), "library")):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file.replace(".py", "").replace("/", ".")
                try:
                    importlib.import_module(f"{__name__}.library.{module_name}")
                except Exception as e:
                    logging.warning(f"Failed to import {module_name}: {e}")


import_library()


class _RegistryConnector(Connector[Registry]):
    name = "Registry"
    ep_name = "vendors"

    def _get_default(self) -> Callable[[], Registry]:
        return lambda: registry


registry_connector = _RegistryConnector()
