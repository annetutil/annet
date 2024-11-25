from typing import List

from annet.generators import BaseGenerator
from annet.storage import Storage
from .policy_generator import RoutingPolicyGenerator
from .community_generator import CommunityGenerator

def get_generators(store: Storage) -> list[BaseGenerator]:
    return [
        RoutingPolicyGenerator(store),
        CommunityGenerator(store),
    ]
