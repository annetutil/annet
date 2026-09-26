from annet.generators import PartialGenerator


class Description(PartialGenerator):
    TAGS = ["description"]

    def acl_arista(self, device):
        return """
        interface
            description
        """

    def run_arista(self, device):
        for interface in device.interfaces:
            with self.block(f"interface {interface.name}"):
                yield f"description {interface.description}"


def get_generators(store):
    return [Description(store)]
