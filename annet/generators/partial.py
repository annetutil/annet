from __future__ import annotations

import re
from typing import (
    Iterable,
    List,
    Set,
    Union,
)

from annet.lib import (
    add_annotation,
    flatten,
)
from .base import TreeGenerator, _filter_str
from .exceptions import NotSupportedDevice


class PartialGenerator(TreeGenerator):
    TYPE = "PARTIAL"
    TAGS: List[str] = []

    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        self._annotate = False
        self._running_gen = None
        self._annotations = []
        self._annotation_module = self.__class__.__module__ or ""

    def supports_vendor(self, vendor: str) -> bool:
        if self.__class__.run is PartialGenerator.run:
            return hasattr(self, f"run_{vendor}")
        else:
            return True

    def acl(self, device):
        if hasattr(self, "acl_" + device.hw.vendor):
            return getattr(self, "acl_" + device.hw.vendor)(device)

    def acl_safe(self, device):
        if hasattr(self, "acl_safe_" + device.hw.vendor):
            return getattr(self, "acl_safe_" + device.hw.vendor)(device)

    def run(self, device) -> Iterable[Union[str, tuple]]:
        if hasattr(self, "run_" + device.hw.vendor):
            return getattr(self, "run_" + device.hw.vendor)(device)
        return iter(())

    def get_user_runner(self, device):
        if self.__class__.run is not PartialGenerator.run:
            return self.run
        elif hasattr(self, "run_" + device.hw.vendor):
            return getattr(self, "run_" + device.hw.vendor)
        return None

    # =====

    @classmethod
    def get_aliases(cls) -> Set[str]:
        return {cls.__name__, *cls.TAGS}

    def __call__(self, device, annotate=False):
        self._indents = []
        self._rows = []
        self._running_gen = self.run(device)
        self._annotate = annotate

        if annotate and self.__class__.__module__:
            self._annotation_module = ".".join(
                self.__class__.__module__.split(".")[-2:])

        for text in self._running_gen:
            if isinstance(text, tuple):
                text = " ".join(map(_filter_str, flatten(text)))
            else:
                text = _filter_str(text)
            self._append_text(text)

        for row in self._rows:
            assert re.search(r"\bNone\b", row) is None, \
                "Found 'None' in yield result: %s" % (row)
        if annotate:
            generated_rows = (
                add_annotation(x, y)
                for (x, y) in zip(self._rows, self._annotations)
            )
        else:
            generated_rows = self._rows
        return "\n".join(generated_rows) + "\n"

    def _append_text(self, text):
        def annotation_cb(row):
            annotation = "%s:%d" % self.get_running_line()
            self._annotations.append(annotation)
            return row

        self._append_text_cb(
            text,
            annotation_cb if self._annotate else None
        )

    def get_running_line(self):
        if not self._running_gen or not self._running_gen.gi_frame:
            return (repr(self._running_gen), -1)
        return self._annotation_module, self._running_gen.gi_frame.f_lineno

    @classmethod
    def literal(cls, item):
        return '"{}"'.format(item)

    def __repr__(self):
        return "<%s>" % self.__class__.__name__
