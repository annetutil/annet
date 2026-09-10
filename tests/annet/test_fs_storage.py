import platform
import sys
import tempfile

from annet.adapters.file.provider import FS, Device, StorageOpts


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


def test_inventory_interfaces(tmp_path):
    path = tmp_path / "inventory.yml"
    path.write_text("""devices:
  - fqdn: switch.example.test
    vendor: arista
    interfaces:
      - name: Ethernet1
        description: Managed by Annet
  - fqdn: empty.example.test
    vendor: arista
""")
    storage = FS(StorageOpts(path=str(path)))
    device = storage.make_devices(["switch.example.test"])[0]
    assert device.interfaces[0].name == "Ethernet1"
    assert device.interfaces[0].description == "Managed by Annet"
    assert storage.make_devices(["empty.example.test"])[0].interfaces == []
