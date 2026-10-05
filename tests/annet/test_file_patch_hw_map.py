import json
import multiprocessing
from pathlib import Path

import pytest

from annet import api, cli_args
from annet.hardware import AnnetHardwareProvider, hardware_connector


def write_inputs(tmp_path, configs, metadata):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    for name, (old, new) in configs.items():
        (old_dir / name).write_text(old)
        (new_dir / name).write_text(new)
    hw_map = tmp_path / "hardware.json"
    hw_map.write_text(json.dumps(metadata))
    return cli_args.FilePatchOptions(old=str(old_dir), new=str(new_dir), hw_map=str(hw_map), parallel=1, indent="  ")


@pytest.mark.parametrize("parallel", [1, 2])
def test_mixed_vendor_map_skips_guessing(tmp_path, monkeypatch, parallel):
    configs = {
        "huawei.cfg": ("sysname before\n", "sysname after\nport split dimension interface 100GE1/0/1\n"),
        "juniper.cfg": ("system {\n    host-name before;\n}\n", "system {\n    host-name after;\n}\n"),
    }
    metadata = {
        "huawei.cfg": {"hw_model": "Huawei NE8000-X4", "sw_version": "VRP V800R022C10SPC500"},
        "juniper.cfg": {"hw_model": "Juniper PTX10002-60C", "sw_version": "JUNOS 22.4R3-S2.11"},
    }
    args = write_inputs(tmp_path, configs, metadata)
    args.parallel = parallel
    if parallel > 1:
        if "fork" not in multiprocessing.get_all_start_methods():
            pytest.skip("This pool test needs inherited connector configuration")
        # Match Linux workers: the connector fixtures are initialized in the parent.
        ctx = multiprocessing.get_context("fork")
        monkeypatch.setattr("annet.parallel.mp.Process", ctx.Process)
        monkeypatch.setattr("annet.parallel.mp.Queue", ctx.Queue)

    def unexpected_guess(*_):
        raise AssertionError("Hardware is already known")

    monkeypatch.setattr(api, "guess_hw", unexpected_guess)
    success, fail = api.file_patch(args)
    assert not fail, fail
    assert len(success) == 2
    for pair, patch in success.items():
        name = pair[1].rsplit("/", 1)[-1]
        hw = hardware_connector.get().make_hw(**metadata[name])
        explicit_args = cli_args.FilePatchOptions(hw=hw, indent="  ")
        assert patch == list(api.file_patch_worker(pair, explicit_args))
        expected = {
            "huawei.cfg": "port split dimension interface 100GE1/0/1\nsysname after",
            "juniper.cfg": "delete system host-name before\nset system host-name after",
        }
        assert patch == [(name, expected[name], False)]


@pytest.mark.parametrize("partial_map", [False, True])
def test_missing_entry_falls_back_to_guessing(tmp_path, monkeypatch, partial_map):
    configs = {"router.cfg": ("sysname before\n", "sysname after\n")}
    metadata = {}
    if partial_map:
        configs["mapped.cfg"] = ("sysname mapped-before\n", "sysname mapped-after\n")
        metadata["mapped.cfg"] = {"hw_model": "Huawei NE8000-X4"}
    args = write_inputs(tmp_path, configs, metadata)
    guessed = []
    hw = hardware_connector.get().make_hw("Huawei NE8000-X4", "VRP V800R022C10SPC500")

    def guess(text):
        guessed.append(text)
        return hw, 1.0

    monkeypatch.setattr(api, "guess_hw", guess)
    success, fail = api.file_patch(args)
    assert not fail, fail
    assert len(success) == (2 if partial_map else 1)
    assert success[(str(Path(args.old) / "router.cfg"), str(Path(args.new) / "router.cfg"))] == [
        ("router.cfg", "sysname after", False),
    ]
    assert guessed == ["sysname before\n", "sysname after\n"]


@pytest.mark.parametrize(
    "metadata",
    [
        [],
        {"router.cfg": None},
        {"router.cfg": {}},
        {"router.cfg": {"hw_model": 42}},
        {"router.cfg": {"hw_model": ""}},
        {"router.cfg": {"hw_model": "unrecognized device"}},
        {"router.cfg": {"hw_model": "Huawei", "sw_version": []}},
    ],
)
def test_invalid_map_fails_before_processing(tmp_path, monkeypatch, metadata):
    args = write_inputs(tmp_path, {"router.cfg": ("sysname before\n", "sysname after\n")}, metadata)
    reads = []
    read_configs = api._read_old_new_configs

    def track_read(*args, **kwargs):
        reads.append(args)
        return read_configs(*args, **kwargs)

    monkeypatch.setattr(api, "_read_old_new_configs", track_read)
    with pytest.raises(ValueError, match="hardware|Hardware|hw_model|sw_version"):
        api.file_patch(args)
    assert reads == []


def test_explicit_vendor_conflicts_with_map(tmp_path):
    args = write_inputs(tmp_path, {}, {})
    args.hw = "Huawei"
    with pytest.raises(ValueError, match="--hw"):
        api.file_patch(args)


@pytest.mark.parametrize("sw_version", [None, "", "VRP V800R022C10SPC500"])
def test_single_file_uses_its_filename(tmp_path, monkeypatch, sw_version):
    args = write_inputs(
        tmp_path,
        {"router.cfg": ("sysname before\n", "sysname after\n")},
        {
            "router.cfg": {"hw_model": "Huawei NE8000-X4", "sw_version": sw_version},
        },
    )
    Path(args.old, "router.cfg").rename(Path(args.old, "previous.cfg"))
    args.old += "/previous.cfg"
    args.new += "/router.cfg"
    provider_inputs = []

    class RecordingProvider(AnnetHardwareProvider):
        def make_hw(self, hw_model, sw_version):
            provider_inputs.append((hw_model, sw_version))
            return super().make_hw(hw_model, sw_version)

    monkeypatch.setattr(hardware_connector, "get", RecordingProvider)
    monkeypatch.setattr(api, "guess_hw", lambda *_: pytest.fail("Unexpected autodetection"))
    success, fail = api.file_patch(args)
    assert not fail, fail
    assert success[(args.old, args.new)] == [("router.cfg", "sysname after", False)]
    assert provider_inputs == [("Huawei NE8000-X4", sw_version or "")]


def test_pc_directory_does_not_need_hardware(tmp_path, monkeypatch):
    args = write_inputs(tmp_path, {}, {})
    old = Path(args.old) / "pc.cfg"
    new = Path(args.new) / "pc.cfg"
    old.mkdir()
    new.mkdir()
    (new / "config.txt").write_text("new contents")
    monkeypatch.setattr(api, "guess_hw", lambda *_: pytest.fail("Unexpected autodetection"))
    success, fail = api.file_patch(args)
    assert not fail, fail
    assert success[(str(old), str(new))] == [("pc.cfg/config.txt", "new contents", False)]


def test_equal_files_do_not_need_autodetection(tmp_path, monkeypatch):
    args = write_inputs(tmp_path, {"router.cfg": ("sysname unchanged\n", "sysname unchanged\n")}, {})
    monkeypatch.setattr(api, "guess_hw", lambda *_: pytest.fail("Identical files need no autodetection"))
    success, fail = api.file_patch(args)
    assert not fail, fail
    assert list(success.values()) == [[]]
