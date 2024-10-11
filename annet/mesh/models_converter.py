from dataclasses import dataclass
from ipaddress import ip_interface

from adaptix import Retort, loader, Chain, name_mapping

from .peer_models import PeerDTO
from ..bgp_models import GlobalOptions, VrfOptions, FamilyOptions, Peer, PeerGroup, ASN, PeerOptions
from ..storage import Device


@dataclass
class InterfaceChanges:
    addr: str
    lag: int | None = None
    lag_links_min: int | None = None
    svi: int | None = None
    subif: int | None = None
    vrf: str | None = None

    def __post_init__(self):
        if self.lag is not None and self.svi is not None:
            raise ValueError("Cannot use LAG and SVI together")
        if self.svi is not None and self.subif is not None:
            raise ValueError("Cannot use Subif and SVI together")


class ObjMapping:
    def __init__(self, obj):
        self.obj = obj

    def __contains__(self, item):
        return hasattr(self.obj, item)

    def __getitem__(self, name):
        return getattr(self.obj, name)

    def get(self, name, default=None):
        return getattr(self.obj, name, default)


retort = Retort(
    recipe=[
        loader(InterfaceChanges, ObjMapping, Chain.FIRST),
        loader(ASN, ASN),
        loader(GlobalOptions, ObjMapping, Chain.FIRST),
        loader(VrfOptions, ObjMapping, Chain.FIRST),
        loader(FamilyOptions, ObjMapping, Chain.FIRST),
        loader(PeerOptions, ObjMapping, Chain.FIRST),
        name_mapping(PeerOptions, map={
            "local_as": "asnum",
        }),
        loader(PeerGroup, ObjMapping, Chain.FIRST),
        name_mapping(PeerGroup, map={
            "local_as": "asnum",
        }),
    ]
)

to_bgp_global_options = retort.get_loader(GlobalOptions)
to_interface_changes = retort.get_loader(InterfaceChanges)


def to_bgp_peer(local: PeerDTO, connected: PeerDTO, connected_device: Device) -> Peer:
    options = retort.load(local, PeerOptions)
    # TODO validate `lagg_links` before conversion
    result = Peer(
        addr=str(ip_interface(connected.addr).ip),
        remote_as=ASN(connected.asnum),
        name=connected.name,
        families=connected.families,
        hostname=connected_device.hostname,
        options=options,
        # TODO update_source
    )
    # connected
    result.vrf_name = getattr(connected, "vrf", result.vrf_name)
    result.group_name = getattr(connected, "group_name", result.group_name)
    result.description = getattr(connected, "description", result.description)
    # local
    result.import_policy = getattr(connected, "import_policy", result.import_policy)
    result.export_policy = getattr(connected, "export_policy", result.export_policy)

    if hasattr(local, "group"):
        result.group = PeerGroup(
            name=local.group.name,
            internal_name="",
            update_source="",
            remote_as=ASN(local.group.remote_as),
            description="",
            connect_retry=False,
        )
    return result