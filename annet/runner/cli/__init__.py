from .cmd_handlers import deploy
from .cmd_handlers import diff
from .cmd_handlers import gen
from .cmd_handlers import gen_diff
from .cmd_handlers import patch
from .cmd_handlers import show_current
from .cmd_handlers import show
from .cmd_handlers import show_device_dump
from .cmd_handlers import show_gen
from .cmd_handlers import show_rollback

commands = [
    gen,
    deploy,
    show,
    show_gen,
    show_current,
    show_device_dump,
    diff,
    patch,
    gen_diff,
    show_rollback,
]
