import functools
import inspect
import json
import os
import pickle
import subprocess
import sys

import yaml

import annet.api  # NOQA
from annet.annlib.netdev.views.hardware import HardwareView


try:
    import jsonpickle
except ImportError:
    jsonpickle = None


_data_formats = {
    "yml": {
        "reader": functools.partial(yaml.load, Loader=yaml.Loader),
        "writer": functools.partial(yaml.dump, default_flow_style=False, allow_unicode=True, sort_keys=False),
    },
    "pk": {
        "reader": pickle.loads,
        "writer": pickle.dumps,
        "read_mode": "rb",
        "write_mode": "wb",
    },
}
_data_formats["yaml"] = _data_formats["yml"]
if jsonpickle:
    _data_formats["json"] = {
        "reader": jsonpickle.loads,
        "writer": lambda x: json.dumps(json.loads(jsonpickle.encode(x)), indent=4, ensure_ascii=False),
    }


# ======
def make_hw_stub(vendor):
    return HardwareView(
        {
            "cisco": "Cisco Catalyst",
            "nexus": "Cisco Nexus",
            "asr": "Cisco ASR",
            "iosxr": "Cisco XR",
            "huawei": "Huawei",
            "huawei ce": "Huawei CE0000",
            "juniper": "Juniper",
            "routeros": "RouterOS",
            "aruba": "Aruba",
            "arista": "Arista",
            "nokia": "Nokia",
            "pc": "PC",
            "ribbon": "Ribbon",
            "optixtrans": "Huawei DC",
            "b4com": "B4com",
            "h3c": "H3C",
        }[vendor],
        None,
    )


def get_test_data_path(path):
    return os.path.join(os.path.dirname(inspect.getfile(sys.modules[__name__])), path)


def get_test_data(path, mode="r"):
    with open(get_test_data_path(path), mode, encoding="utf-8") as data_file:
        return data_file.read()


def save_test_data(path, data, mode="w"):
    with open(get_test_data_path(path), mode, encoding="utf-8") as data_file:
        data_file.write(data)


def get_test_data_list(path):
    return sorted(os.listdir(get_test_data_path(path)))


@functools.lru_cache()
def get_file_format(path):
    data_format = path.split(".")[-1]
    if data_format not in _data_formats:
        raise Exception(
            "file %s has unknown extension %s. Should be one of these: %s"
            % (path, data_format, ", ".join(_data_formats.keys()))
        )
    return data_format


def get_formatted_test_data(path):
    data_format = get_file_format(path)
    saved_test_data = get_test_data(path, _data_formats[data_format].get("read_mode", "r"))
    return _data_formats[data_format]["reader"](saved_test_data)


def save_formatted_test_data(path, data):
    data_format = get_file_format(path)
    save_test_data(
        path,
        _data_formats[data_format]["writer"](data),
        _data_formats[data_format].get("write_mode", "w"),
    )


def cached_test_data(path, key):
    def decorator(func):
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            recache = False
            try:
                saved = get_formatted_test_data(path)
                if saved["key"] != key:
                    recache = True
                retval = saved["retval"]
            except FileNotFoundError:
                recache = True

            if recache:
                retval = func(*args, **kwargs)
                save_formatted_test_data(
                    path,
                    {
                        "key": key,
                        "retval": retval,
                    },
                )
            return retval

        return wrap

    return decorator


def ann_py(args, force_color=True):
    path = os.path.normpath(
        os.path.join(
            os.path.dirname(inspect.getfile(sys.modules[__name__])),
            "../ann.py",
        )
    )
    kwargs = {}
    if force_color:
        kwargs["env"] = os.environ.copy()
        kwargs["env"]["ANN_FORCE_COLOR"] = "1"
    return subprocess.check_output([path] + list(args), **kwargs).decode()
