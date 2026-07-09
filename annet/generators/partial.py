from __future__ import annotations

from collections.abc import Callable
from types import GeneratorType
from typing import Any, Iterable, cast

from annet.lib import add_annotation, flatten
from annet.storage import Device, Storage

from .annotate import AbstractAnnotateFormatter, annotate_formatter_connector
from .base import NONE_SEARCHER, TreeGenerator, _filter_str
from .exceptions import InvalidValueFromGenerator


class PartialGenerator(TreeGenerator):
    TYPE = "PARTIAL"

    def __init__(self, storage: Storage) -> None:
        super().__init__()
        self.storage = storage
        self._running_gen: GeneratorType[str | tuple[Any, ...], None, None] | None = None
        self._annotate: AbstractAnnotateFormatter = annotate_formatter_connector.get(self)
        self._annotations: list[str] = []

    def supports_device(self, device: Device) -> bool:
        if self.__class__.run is PartialGenerator.run:
            return bool(self._get_vendor_func(device.hw.vendor, "run"))
        else:
            return True

    def acl(self, device: Device) -> str | None:
        if acl_func := self._get_vendor_func(device.hw.vendor, "acl"):
            return cast("str | None", acl_func(device))
        return None

    def acl_safe(self, device: Device) -> str | None:
        if acl_func := self._get_vendor_func(device.hw.vendor, "acl_safe"):
            return cast("str | None", acl_func(device))
        return None

    def run(self, device: Device) -> Iterable[str | tuple[Any, ...]] | None:
        if run_func := self._get_vendor_func(device.hw.vendor, "run"):
            return cast("Iterable[str | tuple[Any, ...]] | None", run_func(device))
        return None

    def get_user_runner(self, device: Device) -> Callable[[Device], Iterable[str | tuple[Any, ...]] | None] | None:
        if self.__class__.run is not PartialGenerator.run:
            return self.run
        return self._get_vendor_func(device.hw.vendor, "run")

    def _get_vendor_func(self, vendor: str | None, func_name: str) -> Callable[..., Any] | None:
        attr_name = f"{func_name}_{vendor}"
        return getattr(self, attr_name, None)

    # =====

    def __call__(self, device: Device, annotate: bool = False) -> str:
        self._indents = []
        self._rows = []

        running_gen = self.run(device)
        if running_gen is None:
            raise InvalidValueFromGenerator("%s.run() returned None" % type(self).__name__)
        self._running_gen = cast("GeneratorType[str | tuple[Any, ...], None, None]", running_gen)
        for text in self._running_gen:
            if isinstance(text, tuple):
                text = " ".join(map(_filter_str, flatten(text)))
            else:
                text = _filter_str(text)
            self._append_text(text)

        if not self.ALLOW_NONE:
            for row, annotation in zip(self._rows, self._annotations):
                if NONE_SEARCHER.search(row):
                    raise InvalidValueFromGenerator(
                        "Found 'None' in yield result: %s" % add_annotation(row, annotation)
                    )

        generated_rows: Iterable[str]
        if annotate:
            generated_rows = (add_annotation(x, y) for (x, y) in zip(self._rows, self._annotations))
        else:
            generated_rows = self._rows

        return "\n".join((*generated_rows, ""))

    def _append_text(self, text: str) -> None:
        def annotation_cb(row: str) -> str:
            assert self._running_gen is not None  # set in __call__ before generation runs
            self._annotations.append(self._annotate.make_annotation(self._running_gen))
            return row

        self._append_text_cb(text, row_cb=annotation_cb)

    def get_running_line(self) -> tuple[str, int]:
        assert self._running_gen is not None
        return self._annotate.get_running_line(self._running_gen)

    @classmethod
    def literal(cls, item: object) -> str:
        return '"{}"'.format(item)

    def __repr__(self) -> str:
        return "<%s>" % self.__class__.__name__
