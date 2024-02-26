from unittest.mock import MagicMock

from annet.argparse import Arg, ArgGroup, ArgParser, _reset_meta, subcommand


def test_argparse_check():
    p = MockParser()
    name = "cmd1"
    p.add_commands([name])
    cmd = p.cmds[name]
    p.dispatch([name])
    assert cmd.call_count == 1


def test_argparse_undersore():
    p = MockParser()
    name = "some_cmd"
    p.add_commands([name])
    cmd = p.cmds[name]
    p.dispatch([name.replace("_", "-")])
    assert cmd.call_count == 1


def test_argparse_check_arg():
    name = "cmd"
    param = "--param"
    paramval = "2"

    cmd = CmdBuilder(name).with_param(param).build()

    p = MockParser()
    p.add_mock_command(cmd)
    p.dispatch([name, param, paramval])

    assert cmd.call_args[0]
    assert cmd.call_count == 1
    assert cmd.call_args[0][0].opt_param == paramval


def test_argparse_check_child():
    cmdline = ["subcommand", "submode", "--param", "1"]
    cmdtext, modtext, param, paramval = cmdline

    cmd = CmdBuilder(cmdtext).build()
    mod = CmdBuilder(modtext, parent=cmd).with_param(param).build()
    mod_extra = CmdBuilder(modtext + "_extra", parent=cmd).with_param(param).build()

    p = MockParser()
    p.add_mock_commands([mod, cmd, mod_extra])

    p.dispatch(cmdline)

    assert mod.call_args
    assert mod.call_count == 1
    assert mod.call_args[0][0].opt_param == paramval


class MockParser:
    def __init__(self):
        self.parser = ArgParser()
        self.cmds = {}

    def add_commands(self, names):
        cmds = []
        for name in names:
            cmd = CmdBuilder(name).build()
            cmds.append(cmd)
        self.add_mock_commands(cmds)

    def add_mock_command(self, cmd_mock):
        self.add_mock_commands([cmd_mock])

    def add_mock_commands(self, cmd_mocks):
        for cmd_mock in cmd_mocks:
            self.cmds[cmd_mock.__name__] = cmd_mock
        self.parser.add_commands(cmd_mocks)

    def dispatch(self, argv=None):
        if argv is None:
            argv = []
        self.parser.argv = MagicMock(return_value=argv)
        self.parser.dispatch()


class CmdBuilder:
    def __init__(self, name, parent=None):
        class Group(ArgGroup):
            pass
        self.cls = Group
        self.name = name
        self.parent = parent

    def with_param(self, param):
        arg = Arg(param)
        attr_name = "opt_" + param.strip("-").replace("-", "_")
        setattr(self.cls, attr_name, arg)
        return self

    def build(self):
        cmd = MagicMock()
        _reset_meta(cmd)
        cmd.__name__ = self.name
        if self.parent:
            cmd.__name__ = self.parent.__name__ + "_" + cmd.__name__
            cmd = subcommand(self.cls, parent=self.parent)(cmd)
        else:
            cmd = subcommand(self.cls)(cmd)
        return cmd
