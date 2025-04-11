from annet.adapters.file.provider import FS, Query, StorageOpts, Device
from annet.storage import StorageProvider, Storage
import typing
import tempfile
import sys
import platform

kwargs = dict()
if platform.system() == "Windows":
    if sys.version_info < (3, 12):
        kwargs = {"delete": False}
    else:
        kwargs = {"delete": True, "delete_on_close": False}

def test_fs():
    Device
    with tempfile.NamedTemporaryFile(**kwargs) as f:
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
