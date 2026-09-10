import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "missing_modules",
    [("requests",), ("requests_cache",), ("annetbox",), ("requests", "requests_cache", "annetbox")],
)
def test_file_storage_without_netbox_dependencies(tmp_path: Path, missing_modules: tuple[str, ...]) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text("devices: []\n")
    # A fresh interpreter prevents imports from other tests from masking missing dependencies.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                from unittest.mock import patch

                for module in sys.argv[2:]:
                    sys.modules[module] = None

                from annet.storage import get_storage, storage_connector

                providers = storage_connector.get_all()
                assert "netbox" in [provider.name() for provider in providers]
                assert "file" in [provider.name() for provider in providers]

                with patch("annet.connectors.get_context", return_value={
                    "storage": {"adapter": "file", "params": {"path": sys.argv[1]}}
                }):
                    provider, params = get_storage()
                assert provider.name() == "file"
                opts = provider.opts().parse_params(params, None)
                with provider.storage()(opts) as storage:
                    assert storage.resolve_all_fdnds() == []
                    assert storage.make_devices(provider.query().new(["huawei-1"])) == []

                from annet.adapters.netbox.provider import NetboxProvider

                provider = NetboxProvider()
                opts = provider.opts()(url="http://localhost", token="")
                try:
                    provider.storage()(opts)
                except ModuleNotFoundError as error:
                    assert error.name in sys.argv[2:], str(error)
                else:
                    raise AssertionError("NetBox storage must require its optional dependencies")
                """),
            str(inventory),
            *missing_modules,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
