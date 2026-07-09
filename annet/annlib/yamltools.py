"""YAML 1.2 (de)serialization for vendor JSON-fragment configs.

PyYAML only implements YAML 1.1, whose implicit typing turns ``on``/``off``/
``yes``/``no`` into booleans and reads leading-zero numbers as octal. Network
configs (e.g. NVOS/NVUE) are YAML 1.2, where the only booleans are
``true``/``false`` and ``on`` is an ordinary string.

``ruamel.yaml`` implements YAML 1.2, so we use it here (in ``safe`` mode, which
loads/dumps plain ``dict``/``list`` rather than round-trip types) instead of
PyYAML. Key order is preserved on dump to keep order-significant configs stable.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

from ruamel.yaml import YAML


def _yaml() -> YAML:
    yaml = YAML(typ="safe", pure=True)
    # Block style everywhere; keep keys in insertion order (do not sort).
    yaml.default_flow_style = False
    yaml.representer.sort_base_mapping_type_on_output = False
    return yaml


def load(text: str) -> Any:
    """Parse YAML 1.2 text into plain Python objects."""
    return _yaml().load(text)


def dump(data: Any) -> str:
    """Render Python objects as YAML 1.2 text."""
    stream = StringIO()
    _yaml().dump(data, stream)
    return stream.getvalue()
