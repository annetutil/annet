"""Support JSON patch (RFC 6902) and JSON Pointer (RFC 6901) with globs."""

import copy
import fnmatch
import json
from collections.abc import Mapping, Sequence
from operator import itemgetter
from typing import Any, Dict, List, Optional

import jsonpatch
import jsonpointer


def format_json(data: Any, stable: bool = False) -> str:
    """Serialize to json."""
    return json.dumps(data, indent=4, ensure_ascii=False, sort_keys=not stable) + "\n"


def apply_json_fragment(
        old: Dict[str, Any],
        new_fragment: Dict[str, Any],
        acl: List[str],
) -> Dict[str, Any]:
    """
    Replace parts of the old document with 'new_fragment' using ACL restrictions.
    """
    full_new_config = copy.deepcopy(old)
    for acl_item in acl:
        new_pointers = _resolve_json_pointers(acl_item, new_fragment)
        old_pointers = _resolve_json_pointers(acl_item, full_new_config)

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


def apply_acl_filters(content: Dict[str, Any], filters: List[str]) -> Dict[str, Any]:
    result = {}
    for f in filters:
        filter_text = f.strip()
        if not filter_text:
            continue

        pointers = _resolve_json_pointers(filter_text, content)
        for pointer in pointers:
            part = pointer.get(copy.deepcopy(content))

            sub_tree = result
            for i in pointer.get_parts():
                if i not in sub_tree:
                    sub_tree[i] = {}
                sub_tree = sub_tree[i]

            patch = jsonpatch.JsonPatch([{"op": "add", "path": pointer.path, "value": part}])
            result = patch.apply(result)

    return result


def _resolve_json_pointers(pattern: str, content: Dict[str, Any]) -> List[jsonpointer.JsonPointer]:
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
    matched = [([], content)]
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
                new_matched.append((matched_parts + [key], sub_doc))
        matched = new_matched

    ret: List[jsonpointer.JsonPointer] = []
    for matched_parts, _ in matched:
        ret.append(jsonpointer.JsonPointer("/" + "/".join(matched_parts)))
    return ret
