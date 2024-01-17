"""Support JSON patch (RFC 6902) and JSON Pointer (RFC 6901)."""

import copy
import json
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
        pointer = jsonpointer.JsonPointer(acl_item)

        try:
            new_value = pointer.get(new_fragment)
        except jsonpointer.JsonPointerException:
            # no value found in new_fragment by the pointer, skip the ACL item
            continue

        _ensure_pointer_exists(full_new_config, pointer)
        pointer.set(full_new_config, new_value)

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
        if part not in doc_pointer:
            # create an empty object by the pointer part
            doc_pointer[part] = {}

        if isinstance(doc_pointer, dict):
            # follow the pointer to delve deeper
            doc_pointer = doc_pointer[part]
        else:
            # not a dict - cannot delve deeper
            break


def make_patch(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate a JSON patch by comparing the old document with the new one."""
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
