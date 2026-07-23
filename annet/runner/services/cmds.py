from copy import copy

from annet.runner.deploy_protocols import DeviceCommands


def unite_commands(
    first: DeviceCommands,
    second: DeviceCommands,
) -> DeviceCommands:
    before = copy(second.before_cmds)
    for cmd in first.before_cmds:
        before.add_cmd(cmd)

    after = copy(first.after_cmds)
    for cmd in second.after_cmds:
        after.add_cmd(cmd)

    if common_files := first.upload_files.keys() & second.upload_files.keys():
        msg = f"Files {common_files} retrieved from different generator groups, cannot merge"
        raise ValueError(msg)
    return DeviceCommands(
        before_cmds=before,
        after_cmds=after,
        upload_files=first.upload_files | second.upload_files,
        download_files=first.download_files + second.download_files,
    )
