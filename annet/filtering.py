from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Type

from annet.connectors import Connector


if TYPE_CHECKING:
    from annet.storage import Device


class _FiltererConnector(Connector["Filterer"]):
    name = "Filterer"
    ep_name = "filterer"
    ep_by_group_only = "annet.connectors.filterer"

    def _get_default(self) -> Type["Filterer"]:
        return NopFilterer


filterer_connector = _FiltererConnector()


class Filterer(abc.ABC):
    @abc.abstractmethod
    def for_ifaces(self, device: Device, ifnames: list[str]) -> str:
        pass

    @abc.abstractmethod
    def for_peers(self, device: Device, peers_allowed: list[str]) -> str:
        pass

    @abc.abstractmethod
    def for_policies(self, device: Device, policies_allowed: list[str]) -> str:
        pass


class NopFilterer(Filterer):
    def for_ifaces(self, device: Device, ifnames: list[str]) -> str:
        return ""

    def for_peers(self, device: Device, peers_allowed: list[str]) -> str:
        return ""

    def for_policies(self, device: Device, policies_allowed: list[str]) -> str:
        return ""
