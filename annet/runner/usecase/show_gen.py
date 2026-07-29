import itertools
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from logging import getLogger
from typing import Any

from annet.generators import BaseGenerator
from annet.generators import Generators
from annet.generators import get_description
from annet.storage import Storage

from annet.runner.protocols import DeviceID
from annet.runner.protocols import GeneratorSource
from annet.runner.protocols import HandlerError
from annet.runner.protocols import ShowGenInfo

logger = getLogger(__name__)


def render_gen(generator: BaseGenerator) -> ShowGenInfo:
    return ShowGenInfo(
        name=generator.__class__.__name__,
        type=generator.TYPE,
        tags=generator.TAGS,
        module=generator.__class__.__module__,
        description=get_description(generator.__class__),
    )


def collect_gens(device_gens: Mapping[DeviceID | None, Generators]) -> list[ShowGenInfo]:
    processed_gens: set[BaseGenerator] = set()
    res: list[ShowGenInfo] = []
    for generators in device_gens.values():
        all_device_gens: Iterable[BaseGenerator] = itertools.chain(
            generators.partial,
            generators.entire,
            generators.json_fragment,
        )
        for gen in all_device_gens:
            if gen not in processed_gens:
                processed_gens.add(gen)
                res.append(render_gen(gen))
    return res


class CliShowGenerators:
    def __init__(
        self,
        storage: Storage,
        gen_src: GeneratorSource,
        output: Callable[[list[ShowGenInfo]], None],
    ) -> None:
        self._storage = storage
        self._gen_src = gen_src
        self._output = output

    def handle(self, query: Any) -> HandlerError | None:
        if query:
            devices = self._storage.make_devices(query)
            if not devices:
                logger.error("No devices found for query: %s", query)
                return HandlerError("No devices found")
            generators = self._gen_src.get_generators(devices)
        else:
            generators = {None: self._gen_src.get_all_generators()}

        rendered_generators = collect_gens(generators)
        self._output(rendered_generators)
        return None
