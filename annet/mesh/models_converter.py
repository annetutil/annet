from ipaddress import ip_interface

from adaptix import Retort, loader, Chain, name_mapping

from .basemodel import Special
from .peer_models import PeerDTO
from ..bgp_models import GlobalOptions, VrfOptions, FamilyOptions, Peer, PeerGroup, ASN
from ..storage import Device


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
        loader(ASN, ASN),
        loader(GlobalOptions, ObjMapping, Chain.FIRST),
        loader(VrfOptions, ObjMapping, Chain.FIRST),
        loader(FamilyOptions, ObjMapping, Chain.FIRST),
    ]
)

to_bgp_global_options = retort.get_loader(GlobalOptions)


def drop_unset(data: dict):
    return {
        k: v
        for k, v in data.items()
        if v is not Special.NOT_SET
    }



def to_bgp_peer(local: PeerDTO, connected: PeerDTO, connected_device: Device) -> Peer:
    result = Peer(
        addr=str(ip_interface(connected.addr).ip),
        remote_as=ASN(connected.asnum),
        name=connected.name,
        families = connected.families,
    )
    #connected
    result.vrf_name = getattr(connected, "vrf", result.vrf_name)
    result.description = getattr(connected, "description", result.description)
    #local
    result.import_policy = getattr(connected, "import_policy", result.import_policy)
    result.export_policy = getattr(connected, "export_policy", result.export_policy)

    if hasattr(local, "group"):
        result.group=PeerGroup(
            name=local.group.name,
            internal_name="",
            update_source="",
            remote_as=ASN(local.group.remote_as),
            description="",
            connect_retry=False,
        )
    return result
