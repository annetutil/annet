from typing import Any

from annet.rpl_generators.community_generator import CommunityListGenerator
from annet.rpl_generators.entities import CommunityList, CommunityType, CommunityLogic


class CommunityGenerator(CommunityListGenerator):
    def get_community_lists(self, device: Any) -> list[CommunityList]:
        return [
            CommunityList(
                name="name",
                type=CommunityType.BASIC,
                logic=CommunityLogic.OR,
                use_regex=False,
                members=["12345:1234"],
            )
        ]