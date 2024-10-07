import pytest
import annet

from os import path
from unittest import mock

from annet.api import DeployerJob, Device
from annet.gen import OldNewResult
from annet.deploy import CommandList, DeployDriver, Fetcher
from annet.output import OutputDriver
from annet.rulebook import DefaultRulebookProvider

from .. import MockDevice


class MockDefaultRulebookProvider(DefaultRulebookProvider):
    def __init__(self):
        super().__init__(
            root_dir = (path.dirname(__file__),),
            root_modules = ("tests.annet.test_pc_deploy",),
        )


@pytest.fixture
def mocks():
    orig_fetcher_connector_classes = annet.deploy.fetcher_connector._classes
    orig_driver_connector_classes = annet.deploy.driver_connector._classes
    orig_output_driver_connector_classes = annet.output.output_driver_connector._classes
    orig_storage_connector_classes = annet.storage.storage_connector._classes
    orig_rulebook_provider_classes = annet.rulebook.rulebook_provider_connector._classes
    orig_rulebook_provider_cache = annet.rulebook.rulebook_provider_connector._cache

    ret = mock.Mock(
        deploy_fetcher=mock.MagicMock(spec=Fetcher),
        deploy_driver=mock.MagicMock(spec=DeployDriver),
        output_driver=mock.MagicMock(spec=OutputDriver),
        storage_provider=mock.MagicMock(spec=annet.storage.StorageProvider),
    )
    ret.deploy_driver().build_configuration_cmdlist.return_value=(CommandList(), CommandList())

    annet.deploy.fetcher_connector._classes = [ret.deploy_fetcher]
    annet.deploy.driver_connector._classes = [ret.deploy_driver]
    annet.output.output_driver_connector._classes = [ret.output_driver]
    annet.storage.storage_connector._classes = [ret.storage_provider]
    annet.rulebook.rulebook_provider_connector._classes = [MockDefaultRulebookProvider]
    annet.rulebook.rulebook_provider_connector._cache = None

    yield ret

    annet.deploy.fetcher_connector._classes = orig_fetcher_connector_classes
    annet.deploy.driver_connector._classes = orig_driver_connector_classes
    annet.output.output_driver_connector._classes = orig_output_driver_connector_classes
    annet.storage.storage_connector._classes = orig_storage_connector_classes
    annet.rulebook.rulebook_provider_connector._classes = orig_rulebook_provider_classes
    annet.rulebook.rulebook_provider_connector._cache = orig_rulebook_provider_cache


@pytest.fixture
def device():
    return MockDevice("Edge-Core AS9736-64D", "SONiC ec_20240426_080601_ec202111_hsdk_6.5.23_701", "sonic")


def test_pc_deployer_rulebooks(device: Device, mocks):
    opts = mock.Mock()
    path = "/etc/sonic/config_db.json"
    commands = "commands"

    new_files: dict[str, tuple[str, str]] = {path: ('{"key": "value"}', commands)}

    before = "cmd before deploy"
    after = "cmd after deploy"
    setattr(device.hw, "__before", before)
    setattr(device.hw, "__after", after)

    res = OldNewResult(
        device=device,
        safe_new_files=new_files,
    )
    job = DeployerJob.from_device(res.device, opts)
    job.parse_result(res)

    assert mocks.deploy_driver().build_configuration_cmdlist.call_args_list == [mock.call(device.hw)]
    assert job.deploy_cmds[device]["cmds_pre_files"][path] == before.encode()
    assert job.deploy_cmds[device]["cmds"][path] == "\n".join((commands, after)).encode()
