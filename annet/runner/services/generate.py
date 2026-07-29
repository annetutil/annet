import json
import textwrap
import traceback
from logging import getLogger

from annet import generators
from annet import patching
from annet.generators import Entire
from annet.generators import Generators
from annet.generators import JSONFragment
from annet.generators import PartialGenerator
from annet.patching import Orderer
from annet.rulebook import RulebookProvider
from annet.storage import Device
from annet.storage import Storage
from annet.vendors import Registry
from annet.vendors import tabparser
from annet.vendors.tabparser import CommonFormatter

from annet.runner.protocols import DeviceID
from annet.runner.protocols import GeneratedData
from annet.runner.protocols import GeneratedDataSource
from annet.runner.protocols import GenerationResult
from annet.runner.protocols import GeneratorSource

logger = getLogger(__name__)


def _run_partial(
    gen: PartialGenerator,
    device: Device,
    formatter: CommonFormatter,
    orderer: Orderer,
) -> GeneratedData:
    name = gen.__class__.__name__
    try:
        acl = textwrap.dedent(gen.acl(device) or "").strip()
        output = gen(device, False)

        config_tree = tabparser.parse_to_tree(text=output, splitter=formatter.split)
        config_tree = patching.apply_acl(
            config=config_tree,
            rules=generators.compile_acl_text(acl, device.hw.vendor),
            fatal_acl=True,
        )
        config_tree = orderer.order_config(config_tree)
        output = formatter.join(config_tree)

        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            acl=acl,
            output=output,
            before_cmds=None,
            after_cmds=None,
            path=None,
            priority=None,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Entire generator '%s' failed for dev '%s': %s", name, device.fqdn, exc)
        err = traceback.format_exc()
        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            acl=None,
            output=None,
            before_cmds=None,
            after_cmds=None,
            path=None,
            priority=None,
            error=err,
        )


def _run_entire(gen: Entire, device: Device) -> GeneratedData:
    name = gen.__class__.__name__
    try:
        path = gen.path(device)
        if not path:
            msg = "entire generator should return non-empty path"
            raise ValueError(msg)  # noqa: TRY301
        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            path=path,
            priority=gen.prio,
            output=gen(device),
            before_cmds=None,
            after_cmds=gen.get_reload_cmds(device),
            acl=None,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Entire generator '%s' failed for dev '%s': %s", name, device.fqdn, exc)
        err = traceback.format_exc()
        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            acl=None,
            output=None,
            before_cmds=None,
            after_cmds=None,
            path=None,
            priority=None,
            error=err,
        )


def _run_json_fragment_gen(gen: JSONFragment, device: Device) -> GeneratedData:
    name = gen.__class__.__name__
    try:
        dev_acl = gen.acl(device)
        if not dev_acl:
            acl = None
        elif isinstance(dev_acl, str):
            acl = json.dumps([dev_acl])
        else:
            acl = json.dumps(dev_acl)
        path = gen.path(device)
        if not path:
            msg = "json fragment generator should return non-empty path"
            raise ValueError(msg)  # noqa: TRY301
        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            path=path,
            priority=None,
            output=json.dumps(gen(device)),
            before_cmds=None,
            after_cmds=gen.get_reload_cmds(device),
            acl=acl,
            error=None,
            is_json=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("JSONFragment generator '%s' failed for dev '%s': %s", name, device.fqdn, exc)
        err = traceback.format_exc()
        return GeneratedData(
            name=name,
            tags=gen.TAGS,
            aliases=list(gen.get_aliases()),
            acl=None,
            output=None,
            before_cmds=None,
            after_cmds=None,
            path=None,
            priority=None,
            error=err,
            is_json=True,
        )


def run_all(
    device: Device,
    generators: Generators,
    vendor_registry: Registry,
    rulebook_provider: RulebookProvider,
) -> GenerationResult:
    res = []
    for partial_gen in generators.partial:
        if not partial_gen.supports_device(device):
            continue
        formatter = vendor_registry.match(device.hw).make_formatter()
        rb = rulebook_provider.get_rulebook(device.hw)
        orderer = Orderer(rb["ordering"], device.hw.vendor)
        res.append(_run_partial(partial_gen, device, formatter, orderer))
    for entire_gen in generators.entire:
        if not entire_gen.supports_device(device):
            continue
        res.append(_run_entire(entire_gen, device))
    for json_fragment_gen in generators.json_fragment:
        if not json_fragment_gen.supports_device(device):
            continue
        res.append(_run_json_fragment_gen(json_fragment_gen, device))

    return GenerationResult(data=res)


def list_files(
    device: Device,
    generators: Generators,
) -> set[str]:
    return {gen.path(device) for gen in generators.entire}


class GeneratingSource(GeneratedDataSource):
    def __init__(
        self,
        storage: Storage,
        generators_source: GeneratorSource,
        vendor_registry: Registry,
        rulebook_provider: RulebookProvider,
    ) -> None:
        self._storage = storage
        self._generators_source = generators_source
        self._vendor_registry = vendor_registry
        self._rulebook_provider = rulebook_provider

    def generate(self, devices: list[Device]) -> dict[DeviceID, GenerationResult]:
        generators = self._generators_source.get_generators(devices)
        return {
            device.id: run_all(
                generators=generators[device.id],
                device=device,
                vendor_registry=self._vendor_registry,
                rulebook_provider=self._rulebook_provider,
            )
            for device in devices
        }

    def list_files(self, devices: list[Device]) -> dict[DeviceID, list[str]]:
        generators = self._generators_source.get_generators(devices)
        res = {}
        for device in devices:
            device_files = {}  # store as dict to keep uniq and ordered
            for gen in generators[device.id].entire:
                device_files[gen.path(device)] = True
            for gen in generators[device.id].json_fragment:
                device_files[gen.path(device)] = True
            if device_files:
                res[device.id] = list(device_files)
        return res
