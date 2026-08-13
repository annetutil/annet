import os

import colorama


# disable colorama.init if the env variable is set. Needed in tests
if os.environ.get("ANN_FORCE_COLOR", None) not in [None, "", "0", "no"]:
    colorama.init = lambda *_, **__: None
