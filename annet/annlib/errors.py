class ExecError(Exception):
    """The handler of this exception must log the error and exit with exit_code 1"""

    pass


class DeployCancelled(Exception):
    """Deploy to the device has been cancelled"""

    pass
