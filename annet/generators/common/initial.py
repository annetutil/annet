from collections.abc import Iterator

from annet.generators import PartialGenerator
from annet.storage import Device, Storage


class InitialConfig(PartialGenerator):
    """
    The configs of fresh devices (ones that have never been configured yet)
    are in fact NOT empty. This generator captures that set of
    commands, at least the ones that may change during the
    initial configuration.

    This generator does not need an acl; it generates the whole
    config.
    """

    def __init__(self, storage: Storage, do_run: bool = False) -> None:
        super().__init__(storage=storage)
        self._do_run = do_run

    def run_huawei(self, device: Device) -> Iterator[str]:
        if not self._do_run:
            return
        if device.hw.Huawei.CE:
            yield """
            telnet server disable
            telnet ipv6 server disable
            diffserv domain default
            aaa
                authentication-scheme default
                authorization-scheme default
                accounting-scheme default
                domain default
                domain default_admin
            """
