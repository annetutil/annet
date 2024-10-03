from adaptix import Retort, loader, Chain

from .peer_models import PeerDTO
from ..bgp_models import GlobalOptions, VrfOptions, FamilyOptions, Peer, PeerGroup, ASN


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


def to_bgp_peer(local: PeerDTO, connected: PeerDTO) -> Peer:
    return Peer(
        name=None,
        description="",
        family=None,
        options=None,
        hostname="",
        remote_as=None,
        vrf_name=None,
        export_policy=None,
        import_policy=None,
        update_source=None,
        addr=connected.addr,
        group=PeerGroup(
            name=local.group.name,
            internal_name="",
            update_source="",
            remote_as=ASN(local.group.remote_as),
            description="",
            connect_retry=False,
        ) if local.group else None,
    )
