from annet.mesh.executor import Device


class DeviceImpl(Device):
    def __init__(self, name: str, neigbors: list[str]):
        self._name = name
        self._neigbors = neigbors

    @property
    def fqdn(self) -> str:
        return self._name

    @property
    def neighbors(self) -> list[str]:
        return self._neigbors
