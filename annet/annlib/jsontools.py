"""Support JSON patch (RFC 6902) and JSON Pointer (RFC 6901) with globs."""

from __future__ import annotations

import copy
import dataclasses
import fnmatch
import json
from collections.abc import Mapping, Sequence
from itertools import starmap
from operator import itemgetter
from typing import Any, Dict, Final, Iterable, List, Optional

import jsonpatch
import jsonpointer
from ordered_set import OrderedSet


@dataclasses.dataclass(frozen=True)
class JsonFragmentAcl:
    """ACL entry for a JSONFragment generator.

    `pointer` is a JSON Pointer glob (see `resolve_json_pointers`).
    `cant_delete` is a tuple of JSON Pointer glob patterns naming paths that
    must not be removed when applying this ACL, even if they would otherwise
    be resolved as `old_pointers` matching the main `pointer`. The intent is
    to express "I own only this leaf; do not touch the listed parent paths."
    """

    pointer: str
    cant_delete: tuple[str, ...] = ()


EVERYTHING_ACL: Final = JsonFragmentAcl("/*")


def _normalize_acl(
    acl: Sequence[str | JsonFragmentAcl] | None,
) -> list[JsonFragmentAcl] | None:
    if acl is None:
        return None
    result: list[JsonFragmentAcl] = []
    for item in acl:
        if isinstance(item, JsonFragmentAcl):
            result.append(item)
        else:
            result.append(JsonFragmentAcl(pointer=item))
    return result


def _path_matches_protected(path: str, protected_patterns: tuple[str, ...]) -> bool:
    if not protected_patterns:
        return False
    target_parts = jsonpointer.JsonPointer(path).parts
    for pattern in protected_patterns:
        pattern_parts = jsonpointer.JsonPointer(pattern).parts
        if len(pattern_parts) != len(target_parts):
            continue
        if all(starmap(fnmatch.fnmatchcase, zip(target_parts, pattern_parts))):
            return True
    return False


def format_json(data: Any, stable: bool = False) -> str:
    """Serialize to json."""
    return json.dumps(data, indent=4, ensure_ascii=False, sort_keys=not stable) + "\n"


def apply_json_fragment(
    old: Dict[str, Any],
    new_fragment: Dict[str, Any],
    *,
    acl: Sequence[str | JsonFragmentAcl] | None = None,
    filters: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """
    Replace parts of the old document with 'new_fragment'.
    If `acl` is not `None`, replacement will only be made within specified keys.
    If `filter` is not `None`, only those parts which also matches at least one filter
    from the list will be modified (updated or deleted).

    ACL entries may be plain strings (treated as `JsonFragmentAcl(pointer=...)`)
    or `JsonFragmentAcl` instances. The `cant_delete` attribute lists JSON
    Pointer glob patterns whose matching old pointers must be preserved when
    applying this ACL.
    """
    normalized_acl = _normalize_acl(acl)
    if normalized_acl is None:
        normalized_acl = [EVERYTHING_ACL]
    full_new_config = copy.deepcopy(old)
    for acl_item in normalized_acl:
        new_pointers = resolve_json_pointers(acl_item.pointer, new_fragment)
        if filters is not None:
            new_pointers = _apply_filters_to_json_pointers(new_pointers, filters, content=new_fragment)

        for pointer in new_pointers:
            new_value = pointer.get(new_fragment)
            _pointer_set(pointer, full_new_config, new_value)

        # An ACL pointer like /VLAN/Vlan*/vlanid expresses ownership of every
        # level on its path: the generator owns /VLAN, every /VLAN/Vlan*, and
        # the vlanid leaf. If a level's key is missing from new_fragment, the
        # whole subtree at that key is removed from full_new_config — even if
        # it contains other generators' data (which they will re-add later).
        # %cant_delete excludes a level from this ownership.
        pointer_parts = jsonpointer.JsonPointer(acl_item.pointer).parts
        for depth in range(1, len(pointer_parts) + 1):
            prefix_pattern = jsonpointer.JsonPointer.from_parts(pointer_parts[:depth]).path
            if _pattern_matches_protected(prefix_pattern, acl_item.cant_delete):
                continue
            level_new = resolve_json_pointers(prefix_pattern, new_fragment)
            level_old = resolve_json_pointers(prefix_pattern, full_new_config)
            if filters is not None and depth == len(pointer_parts):
                # Filters historically apply only at the deepest ACL level.
                level_new = _apply_filters_to_json_pointers(level_new, filters, content=new_fragment)
                level_old = _apply_filters_to_json_pointers(level_old, filters, content=full_new_config)
            new_paths = {p.path for p in level_new}
            for ptr in level_old:
                if ptr.path in new_paths:
                    continue
                if _path_matches_protected(ptr.path, acl_item.cant_delete):
                    continue
                container, last = ptr.to_last(full_new_config)
                if isinstance(container, dict) and isinstance(last, str):
                    container.pop(last, None)

    return full_new_config


def _pattern_matches_protected(pattern: str, protected_patterns: tuple[str, ...]) -> bool:
    """True if `pattern` itself appears (textually, after segment-normalisation)
    in `protected_patterns`. Used to skip an entire ACL prefix level."""
    if not protected_patterns:
        return False
    target_parts = jsonpointer.JsonPointer(pattern).parts
    for prot in protected_patterns:
        if jsonpointer.JsonPointer(prot).parts == target_parts:
            return True
    return False


def _pointer_set(pointer: jsonpointer.JsonPointer, doc: Any, value: Any) -> None:
    """
    Resolve `pointer` against the `doc`, creating new elements if neccessary,
    and set the target's value to `value`, all in place.

    If `pointer` in any it's part points to the non-existing key,
    or if value at this point is `None`, new object will be created.
    (See https://github.com/stefankoegl/python-json-pointer/issues/41)

    If `pointer` in any it's part points to the index of next to be appended
    element of the array, new document / `value` will be appended to that list.
    """
    if len(pointer.parts) == 0:
        raise jsonpointer.JsonPointerException("Cannot set root in place")
    *parts_expect_the_last, last_part = pointer.parts

    for part in parts_expect_the_last:
        key = pointer.get_part(doc, part)
        if isinstance(doc, dict):
            if doc.get(key, None) is None:
                doc[key] = {}
        elif isinstance(doc, list):
            if key == len(doc):
                doc.append({})
        doc = doc[key]

    key = pointer.get_part(doc, last_part)
    if isinstance(doc, list) and key == len(doc):
        doc.append(value)
    else:
        doc[key] = value


def make_patch(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate a JSON patch by comparing the old document with the new one."""
    # NOTE: changing order of the patch operations (e.g. sorting)
    #  may interfere with the `move` logic.
    #  E.g.:
    #  ```python
    #  old = [["a", "b"], ["c", "d"]]
    #  new = [["d", "c"], ["b", "a"]]
    #  ```
    #  produces the following patch:
    #  ```json
    #  [{"op": "move", "path": "/0/0", "from": "/1/0"},
    #   {"op": "move", "path": "/1/0", "from": "/0/2"},
    #   {"op": "move", "path": "/0/0", "from": "/1/1"},
    #   {"op": "move", "path": "/1/1", "from": "/0/2"}]
    #  ```
    #  which relies on proper ordering to be correctly applied.
    #  See https://github.com/annetutil/annet/pull/452 for details.
    return jsonpatch.make_patch(old, new).patch


def apply_patch(content: Optional[bytes], patch_bytes: bytes) -> bytes:
    """
    Apply JSON patch to file contents.

    If content is None it is considered that the file does not exist.
    """
    old_doc: Any
    if content is not None:
        old_doc = json.loads(content)
    else:
        old_doc = None

    patch_data = json.loads(patch_bytes)
    patch = jsonpatch.JsonPatch(patch_data)
    new_doc = patch.apply(old_doc)

    new_contents = format_json(new_doc, stable=True).encode()
    return new_contents


def resolve_json_pointers(pattern: str, content: dict[str, Any]) -> list[jsonpointer.JsonPointer]:
    """
    Resolve globbed json pointer pattern to a list of actual pointers, existing in the document.

    For example, given the following document:

    {
        "foo": {
            "bar": {
                "baz": [1, 2]
            },
            "qux": {
                "baz": [3, 4]
            },
        }
    }

    Pattern "/f*/*/baz" will resolve to:

    [
        "/foo/bar/baz"",
        "/foo/qux/baz",
    ]

    Pattern "/f*/q*/baz/*" will resolve to:

    [
        "/foo/qux/baz/0",
        "/foo/qux/baz/1",
    ]

    Pattern "/*" will resolve to:

    [
        "/foo"
    ]
    """
    parts = jsonpointer.JsonPointer(pattern).parts
    matched = [((), content)]
    for part in parts:
        new_matched = []
        for matched_parts, doc in matched:
            keys_and_docs = []
            if isinstance(doc, Mapping):
                keys_and_docs = [(key, doc[key]) for key in doc.keys() if fnmatch.fnmatchcase(key, part)]
            elif isinstance(doc, Sequence):
                keys_and_docs = [(str(i), doc[i]) for i in range(len(doc)) if fnmatch.fnmatchcase(str(i), part)]
            for key, sub_doc in keys_and_docs:
                new_matched.append((matched_parts + (key,), sub_doc))
        matched = new_matched

    ret: list[jsonpointer.JsonPointer] = []
    for matched_parts, _ in matched:
        ret.append(jsonpointer.JsonPointer.from_parts(matched_parts))
    return ret


def _apply_filters_to_json_pointers(
    pointers: Iterable[jsonpointer.JsonPointer],
    filters: Sequence[str],
    *,
    content: Any,
) -> Sequence[jsonpointer.JsonPointer]:
    """
    Takes a list of pointers, a list of filters and a document, and returns
    a list of pointers that match at least one of the filters, preserving order.

    For example, given:
    pointers=["/foo", "/lorem/ipsum", "/lorem/dolor"],
    filters=["/foo/b*/q*", "/lorem"],
    content={
        "foo": {
            "bar": {
                "baz": [1, 2],
                "qux": [3, 4]
            },
            "qux": {
                "baz": [5, 6]
            }
        },
        "lorem": {
            "ipsum": [7, 8],
            "dolor": "sit",
            "amet": "consectetur"
        }
    }
    The function will return:
    ["/foo/bar/qux", "/lorem/ipsum", "/lorem/dolor"]
    """

    ret = OrderedSet[jsonpointer.JsonPointer]()
    for filter_item in filters:
        filter_parts = jsonpointer.JsonPointer(filter_item).parts
        for pointer in pointers:
            pointer_parts = pointer.parts
            if not all(starmap(fnmatch.fnmatchcase, zip(pointer_parts, filter_parts))):
                continue  # common part not matched
            if len(filter_parts) > len(pointer_parts):
                # filter is deeper than data pointer
                deeper_doc = pointer.resolve(content)
                deeper_pattern = "".join(
                    (f"/{jsonpointer.escape(part)}" for part in filter_parts[len(pointer_parts) :])
                )
                ret.update(map(pointer.join, resolve_json_pointers(deeper_pattern, deeper_doc)))
            else:
                ret.add(pointer)
    return ret
