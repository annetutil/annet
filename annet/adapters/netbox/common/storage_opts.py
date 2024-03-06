import os


class NetboxStorageOpts:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    @classmethod
    def from_cli_opts(cls, cli_opts):
        return cls(
            url=os.getenv("NETBOX_URL", "http://localhost"),
            token=os.getenv("NETBOX_TOKEN", "").strip(),
        )
