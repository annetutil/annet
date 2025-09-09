"""Support JSON patch (RFC 6902) and JSON Pointer (RFC 6901) with globs."""

import copy
import fnmatch
import json
from collections.abc import Mapping, Sequence
from itertools import starmap
from operator import itemgetter
from typing import Any, Dict, Iterable, List, Optional

import jsonpatch
import jsonpointer


def format_json(data: Any, stable: bool = False) -> str:
    """Serialize to json."""
    return json.dumps(data, indent=4, ensure_ascii=False, sort_keys=not stable) + "\n"


def apply_json_fragment(
        old: Dict[str, Any],
        new_fragment: Dict[str, Any], *,
        acl: Sequence[str],
        filters: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """
    Replace parts of the old document with 'new_fragment' using ACL restrictions.
    If `filter` is not `None`, only those parts which also matches at least one filter
    from the list will be modified (updated or deleted).
    """
    full_new_config = copy.deepcopy(old)
    for acl_item in acl:
        new_pointers = _resolve_json_pointers(acl_item, new_fragment)
        old_pointers = _resolve_json_pointers(acl_item, full_new_config)
        if filters is not None:
            new_pointers = _apply_filters_to_json_pointers(
                new_pointers, filters, content=new_fragment
            )
            old_pointers = _apply_filters_to_json_pointers(
                old_pointers, filters, content=full_new_config
            )

        for pointer in new_pointers:
            new_value = pointer.get(new_fragment)
            _ensure_pointer_exists(full_new_config, pointer)
            pointer.set(full_new_config, new_value)

        # delete matched parts in old config whicn are not present in the new
        paths = {p.path for p in new_pointers}
        to_delete = [p for p in old_pointers if p.path not in paths]
        for pointer in to_delete:
            doc, part = pointer.to_last(full_new_config)
            if isinstance(doc, dict) and isinstance(part, str):
                doc.pop(part, None)

    return full_new_config


def _ensure_pointer_exists(doc: Dict[str, Any], pointer: jsonpointer.JsonPointer) -> None:
    """
    Ensure that document has all pointer parts (if possible).

    This is workaround for errors of type:

    ```
    jsonpointer.JsonPointerException: member 'MY_PART' not found in {}
    ```

    See for details: https://github.com/stefankoegl/python-json-pointer/issues/41
    """
    parts_except_the_last = pointer.get_parts()[:-1]
    doc_pointer: Dict[str, Any] = doc
    for part in parts_except_the_last:
        if isinstance(doc_pointer, dict):
            if part not in doc_pointer or doc_pointer[part] is None:
                # create an empty object by the pointer part
                doc_pointer[part] = {}

            # follow the pointer to delve deeper
            doc_pointer = doc_pointer[part]
        else:
            # not a dict - cannot delve deeper
            break


def make_patch(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate a JSON patch by comparing the old document with the new one."""
    return sorted(jsonpatch.make_patch(old, new).patch, key=itemgetter("path"))


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


def _resolve_json_pointers(pattern: str, content: dict[str, Any]) -> list[jsonpointer.JsonPointer]:
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
                keys_and_docs = [
                    (key, doc[key]) for key in doc.keys()
                    if fnmatch.fnmatchcase(key, part)
                ]
            elif isinstance(doc, Sequence):
                keys_and_docs = [
                    (str(i), doc[i]) for i in range(len(doc))
                    if fnmatch.fnmatchcase(str(i), part)
                ]
            for key, sub_doc in keys_and_docs:
                new_matched.append((matched_parts + (key,), sub_doc))
        matched = new_matched

    ret: list[jsonpointer.JsonPointer] = []
    for matched_parts, _ in matched:
        ret.append(jsonpointer.JsonPointer.from_parts(matched_parts))
    return ret


def _apply_filters_to_json_pointers(
        pointers: Iterable[jsonpointer.JsonPointer],
        filters: Sequence[str], *,
        content: Any,
) -> list[jsonpointer.JsonPointer]:

    """
    Takes a list of pointers, a list of filters and a document
    and returns a list of pointers that match at least one of the filters
    (if necessary, pointers may be deeper than from the input).

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

    ret: set[jsonpointer.JsonPointer] = set()
    for filter_item in filters:
        filter_parts = jsonpointer.JsonPointer(filter_item).parts
        for pointer in pointers:
            pointer_parts = pointer.parts
            if not all(starmap(fnmatch.fnmatchcase, zip(pointer_parts, filter_parts))):
                continue  # common part not matched
            if len(filter_parts) > len(pointer_parts):
                # filter is deeper than data pointer
                deeper_doc = pointer.resolve(content)
                deeper_pattern = "".join((
                    f"/{jsonpointer.escape(part)}"
                    for part in filter_parts[len(pointer_parts):]
                ))
                ret.update(map(pointer.join, _resolve_json_pointers(deeper_pattern, deeper_doc)))
            else:
                ret.add(pointer)
    # sort return value by some stable key, to decrease the chance
    # that some bug may lead to unstable output being produced
    # (since `type(ret) is set`)
    return sorted(ret, key=str)
