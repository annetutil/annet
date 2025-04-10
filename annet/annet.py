#!/usr/bin/env python3
import logging
import sys

import annet
from annet import argparse, cli, generators, hardware, lib, rulebook, diff


# =====
@lib.catch_ctrl_c
def main():
    annet.assert_python_version()
    parser = argparse.ArgParser()
    cli.fill_base_args(parser, annet.__name__, "configs/logging.yaml")
    rulebook.rulebook_provider_connector.set(rulebook.DefaultRulebookProvider)
    hardware.hardware_connector.set(hardware.AnnetHardwareProvider)
    diff.file_differ_connector.set(diff.UnifiedFileDiffer)

    parser.add_commands(parser.find_subcommands(cli.list_subcommands()))
    try:
        return parser.dispatch(pre_call=annet.init, add_help_command=True)
    except (generators.GeneratorError, annet.ExecError) as e:
        logging.error(e)
        return 1
    except BaseException as e:
        if formatted_output := getattr(e, "formatted_output", None):
            logging.error(formatted_output)
            return 1
        raise e


if __name__ == "__main__":
    sys.exit(main())
