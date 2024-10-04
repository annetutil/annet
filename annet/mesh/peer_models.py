from typing import Literal, Annotated

from .basemodel import BaseMeshModel, Merge
from ..bgp_models import BFDTimers

FamilyName = Literal["ipv4_unicast", "ipv6_unicast", "ipv4_labeled", "ipv6_labeled"]


class MeshPeerGroup(BaseMeshModel):
    name: str
    remote_as: int = 0
    internal_name: str = ""
    update_source: str | None
    connect_retry: bool | None
    description: str | None

    @classmethod
    def default(cls):
        return cls(
            name="",
            remote_as=0,
            internal_name="",
            update_source=None,
            connect_retry=None,
            description=None,
        )


class SessionDTO(BaseMeshModel):
    asnum: str
    vrf: str
    name: str
    families: Annotated[list[FamilyName], Merge()]
    group: MeshPeerGroup

    subif: str  # TODO: ????
    bmp_monitor: bool
    add_path: bool
    multipath: bool
    advertise_irb: bool
    send_labeled: bool
    send_community: bool
    lagg_links: int  # used to validate lagg members

    import_policy: str
    export_policy: str

    bfd: bool
    bfd_timers: BFDTimers


class PeerDTO(SessionDTO):
    pod: int
    addr: str
    description: str

    # for lagg validation
    peers_min: int
    parallel: int  # ????

    # for peer options
    unnumbered: bool
    rr_client: bool
    next_hop_self: bool
    extended_next_hop: bool
    send_lcommunity: bool
    send_extcommunity: bool
    import_limit: bool
    teardown_timeout: bool
    redistribute: bool
    passive: bool
    mtu_discovery: bool
    advertise_inactive: bool
    advertise_bgp_static: bool
    allowas_in: bool
    auth_key: bool
    multihop: bool
    multihop_no_nexthop_change: bool
    af_no_install: bool
    rib: bool
    resolve_vpn: bool
    af_rib_group: str | None
    af_loops: int
    hold_time: int
    listen_network: bool
    remove_private: bool
    as_override: bool
    aigp: bool
    no_prepend: bool
    no_explicit_null: bool
    uniq_iface: bool
    advertise_peer_as: bool
    connect_retry: bool
    advertise_external: bool
    listen_only: bool
    soft_reconfiguration_inbound: bool
    not_active: bool
    mtu: int
