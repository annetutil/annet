from .partial import PartialGenerator


class RefGenerator(PartialGenerator):
    def __init__(self, storage, groups=None):
        super().__init__(storage)
        self.groups = groups

    def _is_device_supported(self, device):
        return True

    def ref(self, device):
        if not self._is_device_supported(device):
            return ""
        if hasattr(self, "ref_" + device.hw.vendor):
            return getattr(self, "ref_" + device.hw.vendor)(device)
        return ""

    def with_groups(self, groups):
        return type(self)(self.storage, groups)
