import csv
import dataclasses
import operator
import os
import os.path
import pathlib
from typing import List

from annet.storage import Device, Storage, Query, StorageOpts, StorageProvider
from annet.annlib.netdev.views.hardware import HardwareView


class AnnetNbExportProvder(StorageProvider):
    def storage(self):
        return AnnetNbExportStorage

    def opts(self):
        return AnnetNbExportStorageOpts

    def query(self):
        return AnnetNbExportQuery


@dataclasses.dataclass
class AnnetNbExportQuery(Query):
    query: List[str]

    @classmethod
    def new(cls, query, hosts_range) -> "AnnetNbExportQuery":
        if hosts_range is not None:
            raise ValueError("host_range is not supported")
        return cls(query=query)

    @property
    def globs(self):
        # We process every query host as a glob
        return self.query


@dataclasses.dataclass
class AnnetNbExportStorageOpts(StorageOpts):
    @classmethod
    def from_cli_opts(cls, cli_opts) -> "AnnetNbExportQuery":
        return cls()


class DeviceNb(Device):
    def __init__(self, storage: "Storage", dto: "NetboxDTO", region: str):
        self.dto = dto
        self.storage = storage
        self.region = region

    def __hash__(self):
        return hash(self.id)

    def is_pc(self):
        return self.dto.manufacturer == "Mellanox"

    @property
    def hw(self):
        manufacturer = self.dto.manufacturer
        model_name = self.dto.model_name
        # по какой-то причине модели mellanox SN в нетбоксе называются MSN
        # чтобы использовать выгрузку as is и не править devdb.json патчим тут
        if manufacturer == "Mellanox" and model_name.startswith("MSN"):
            model_name = model_name.replace("MSN", "SN", 1)
        hw = _vendor_to_hw(manufacturer + " " + model_name)
        assert hw.vendor, "unsupported manufacturer %s" % self.dto.manufacturer
        return hw

    @property
    def id(self):
        return self.dto.name

    @property
    def fqdn(self):
        return self.dto.name

    @property
    def hostname(self):
        return self.dto.name

    @property
    def neighbours_ids(self):
        return set()

    @property
    def breed(self):
        if self.dto.manufacturer == "Huawei" and self.dto.model_name.startswith("CE"):
            return "vrp85"
        elif self.dto.manufacturer == "Huawei" and self.dto.model_name.startswith("NE"):
            return "vrp85"
        elif self.dto.manufacturer == "Huawei":
            return "vrp55"
        elif self.dto.manufacturer == "Mellanox":
            return "cuml2"
        elif self.dto.manufacturer == "Juniper":
            return "jun10"
        elif self.dto.manufacturer == "Cisco":
            return "ios12"
        elif self.dto.manufacturer == "Adva":
            return "adva8"
        elif self.dto.manufacturer == "Arista":
            return "eos4"
        assert False, "unknown manufacturer %s" % self.dto.manufacturer


@dataclasses.dataclass
class NetboxDTO:
    name: str
    device_role: str
    tenant: str
    manufacturer: str
    model_name: str
    platform: str
    serial: str
    asset_tag: str
    status: str
    site: str
    rack_group: str
    rack_name: str
    position: str
    face: str
    comments: str


class AnnetNbExportStorage(Storage):
    def __init__(self, opts: "Optional[StorageOpts]" = None):
        self._dump_dir = os.path.join(os.path.dirname(__file__))

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        pass

    def resolve_object_ids_by_query(self, query):
        ret = []
        for device_data in _read_dump(self._dump_dir):
            if _match_query(query, device_data):
                ret.append(device_data["name"])
        return ret

    def resolve_fdnds_by_query(self, query):
        return self.resolve_object_ids_by_query(query)

    def make_devices(
        self,
        query: "inventory.Query",
        preload_neighbors=False,
        use_mesh=None,
        preload_extra_fields=False,
        **kwargs,
    ):
        ret = []
        for file_path, device_data in _read_dump(self._dump_dir):
            if _match_query(query, device_data):
                ret.append(DeviceNb(self, NetboxDTO(**device_data), region=file_path.parent.name))
        return ret

    def get_device(self, obj_id, preload_neighbors=False, use_mesh=None, **kwargs) -> "DeviceView":
        for file_path, device_data in _read_dump(self._dump_dir):
            if device_data["name"] == obj_id:
                return DeviceNb(self, NetboxDTO(**device_data), region=file_path.parent.name)

    def flush_perf(self):
        pass


def _read_dump(dump_dir):
    for (dirpath, _dirnames, filenames) in  os.walk(dump_dir):
        for filename in filenames:
            if filename != "devices.csv":
                continue
            with open(os.path.join(dirpath, filename)) as fh:
                file_path = pathlib.Path(os.path.join(dirpath, filename))
                for device_data in csv.DictReader(fh):
                    yield file_path, device_data


def _match_query(query, device_data) -> bool:
    for subquery in query.globs:
        matches = []
        for field_filter in subquery.split("@"):
            if "=" in field_filter:
                field, value = field_filter.split("=")
                field = field.strip()
                value = value.strip()
                op = operator.eq
            else:
                field = "name"
                value = field_filter.strip()
                op = operator.contains
            if field in device_data and op(device_data[field], value):
                matches.append(True)
            else:
                matches.append(False)
        if all(matches):
            return True
    return False


def _vendor_to_hw(vendor):
    hw = HardwareView(
        {
            "cisco": "Cisco",
            "catalyst": "Cisco Catalyst",
            "nexus": "Cisco Nexus",
            "huawei": "Huawei",
            "juniper": "Juniper",
            "arista": "Arista",
            "pc": "PC",
            "nokia": "Nokia",
            "aruba": "Aruba",
            "routeros": "RouterOS",
            "ribbon": "Ribbon",
        }.get(vendor.lower(), vendor),
        None,
    )
    return hw
