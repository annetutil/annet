import os
from unittest import mock

import pytest
from annet import rulebook

from annet import deploy, implicit, lib, patching
from annet.vendors import registry_connector

from .. import make_hw_stub
from . import patch_data


@pytest.mark.parametrize(
    "name, sample",
    patch_data.get_samples(dirname="annet/test_patch")
)
def test_patch(name, sample, ann_connectors):
    vendor = sample.get("vendor", "huawei").lower()

    hw = make_hw_stub(vendor)
    if soft := sample.get("soft"):
        hw.soft = soft

    rb = rulebook.get_rulebook(hw)
    formatter = registry_connector.get().match(hw).make_formatter(indent="")

    old, new, expected_patch = patch_data.get_configs(hw, sample)

    assert old != new

    implicit_rules = implicit.compile_rules(mock.Mock(hw=hw))
    old = lib.merge_dicts(old, implicit.config(old, implicit_rules))
    new = lib.merge_dicts(new, implicit.config(new, implicit_rules))

    diff = patching.make_diff(old, new, rb, [])
    pre = patching.make_pre(diff)

    fake_environ = os.environ.copy()
    with mock.patch.object(os, "environ", new=fake_environ):
        if sample_environ := sample.get("env"):
            fake_environ.update(sample_environ)

        patch_tree = patching.make_patch(pre=pre, rb=rb, hw=hw, add_comments=False)
        cmd_paths = formatter.cmd_paths(patch_tree)
        cmds = deploy.apply_deploy_rulebook(hw, cmd_paths)

    generated = []
    for cmd in cmds:
        generated.append("%s%s\n" % ("  " * cmd.level, str(cmd)))

    assert expected_patch == "".join(generated), ("Wrong patch in %s" % name)
