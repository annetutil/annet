from annet.annlib.netdev.views import hardware


class MockDevice:
    def __init__(self, hw_model, sw_version, breed):
        self.hw = hardware.HardwareView(hw_model, sw_version)
        self.breed = breed
