from annet.adapters.file.provider import FS, Query, StorageOpts, Device
from annet.storage import StorageProvider, Storage
import typing
import tempfile

def test_fs():
    Device
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"""
devices:
  - hostname: hostname
    fqdn: hostname.domain
    vendor: vendor
    interfaces:
      - name: eth0
        description: description
""")
        f.flush()
        fs = FS(StorageOpts(path=f.name))
    print(fs)
