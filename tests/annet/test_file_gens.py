from unittest import mock

from annet import gen
from annet.generators import NotSupportedDevice


class _Gen:
    def __init__(self, supported, path="/etc/x"):
        self._supported = supported
        self._path = path

    def supports_device(self, device):
        if isinstance(self._supported, Exception):
            raise self._supported
        return self._supported

    def path(self, device):
        return self._path


def test_file_gens_skips_unsupported_generators():
    device = mock.Mock()
    ok, no, raises, json_ok, json_no = (
        _Gen(True),
        _Gen(False),
        _Gen(NotSupportedDevice()),
        _Gen(True),
        _Gen(False),
    )
    gens = gen.DeviceGenerators(entire={device: [ok, no, raises]}, json_fragment={device: [json_ok, json_no]})

    assert list(gens.file_gens(device)) == [ok, json_ok]


def test_get_files_to_download_ignores_unsupported_generators():
    device = mock.Mock()
    gens = gen.DeviceGenerators(
        entire={device: [_Gen(True, "/etc/enabled"), _Gen(False, "/etc/ann-dhcrelay6nb@.service")]},
    )

    assert gen._get_files_to_download([device], gens) == {device: ["/etc/enabled"]}
