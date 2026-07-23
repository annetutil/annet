from logging import getLogger

from annet.cli_args import GenSelectOptions
from annet.generators import Entire
from annet.generators import Generators
from annet.generators import JSONFragment
from annet.generators import PartialGenerator
from annet.generators import build_generators
from annet.generators.common.initial import InitialConfig
from annet.storage import Device
from annet.storage import Storage

from annet.runner.protocols import DeviceID
from annet.runner.protocols import GeneratorSource

logger = getLogger(__name__)


def make_applicable_generators(
    device: Device,
    storage: Storage,
    args: GenSelectOptions,
) -> Generators:
    gens = build_generators(storage=storage, gens=args, device=device)
    return Generators(
        partial=[g for g in gens.partial if partial_gen_applicable(g, device)],
        entire=[g for g in gens.entire if entire_gen_applicable(g, device)],
        json_fragment=[g for g in gens.json_fragment if json_fragment_gen_applicable(g, device)],
        ref=gens.ref,
    )


class InitialGeneratorSource(GeneratorSource):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def _initial_gens(self, storage: Storage) -> list[PartialGenerator]:
        return [InitialConfig(storage=storage, do_run=True)]

    def get_generators(self, devices: list[Device]) -> dict[DeviceID, Generators]:
        return {
            d.id: Generators(
                partial=[gen for gen in self._initial_gens(storage=self._storage) if partial_gen_applicable(gen, d)],
            )
            for d in devices
        }

    def get_all_generators(self) -> Generators:
        return Generators(
            partial=self._initial_gens(storage=self._storage),
        )


class GeneratorsSourceImpl(GeneratorSource):
    def __init__(
        self,
        storage: Storage,
        gen_select_options: GenSelectOptions,
    ) -> None:
        self._storage = storage
        self._gen_select_options = gen_select_options

    def get_generators(self, devices: list[Device]) -> dict[DeviceID, Generators]:
        return {
            device.id: make_applicable_generators(
                storage=self._storage,
                args=self._gen_select_options,
                device=device,
            )
            for device in devices
        }

    def get_all_generators(self) -> Generators:
        return build_generators(storage=self._storage, gens=self._gen_select_options, device=None)


def partial_gen_applicable(
    gen: PartialGenerator,
    device: Device,
) -> bool:
    try:
        return gen.supports_device(device) and gen.acl(device)
    except Exception:
        gen_name = gen.__class__.__name__
        msg = f"Partial generator {gen_name} is broken for {device.fqdn}"
        logger.exception(msg)
        return False


def entire_gen_applicable(
    gen: Entire,
    device: Device,
) -> bool:
    try:
        return gen.supports_device(device) and gen.path(device)
    except Exception:
        gen_name = gen.__class__.__name__
        msg = f"Entire generator {gen_name} is broken for {device.fqdn}"
        logger.exception(msg)
        return False


def json_fragment_gen_applicable(
    gen: JSONFragment,
    device: Device,
) -> bool:
    try:
        return gen.supports_device(device) and gen.path(device) and gen.acl(device)
    except Exception:
        gen_name = gen.__class__.__name__
        msg = f"JSONFragment generator {gen_name} is broken for {device.fqdn}"
        logger.exception(msg)
        return False
