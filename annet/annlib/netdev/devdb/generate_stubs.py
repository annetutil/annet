import itertools
import keyword
from collections.abc import Iterable, Iterator, Mapping


# A devdb node such as ("Huawei", "CE", "CE6800").
Node = tuple[str, ...]
ClassSignature = tuple[Node, tuple[tuple[str, Node], ...]]


# "Huawei.CE?.CE6800" -> (("Huawei", "CE", "CE6800"), frozenset({1})).
def parse_devdb_key(key: str) -> tuple[Node, frozenset[int]]:
    parts = key.split(".")
    canonical: list[str] = []
    optional: set[int] = set()

    for index, part in enumerate(parts):
        if "?" in part:
            if part.count("?") != 1 or not part.endswith("?"):
                raise ValueError(f"invalid optional segment in devdb key {key!r}")
            if index == len(parts) - 1:
                raise ValueError(f"the final segment cannot be optional in devdb key {key!r}")
            part = part.removesuffix("?")
            optional.add(index)

        if not part.isidentifier() or keyword.iskeyword(part):
            raise ValueError(f"invalid segment {part!r} in devdb key {key!r}")
        canonical.append(part)

    return tuple(canonical), frozenset(optional)


# "Huawei.CE?.CE6800" -> ("Huawei", "CE", "CE6800").
def canonicalize_devdb_key(key: str) -> Node:
    canonical, _ = parse_devdb_key(key)
    return canonical


# {1, 2} -> {}, {1}, {2}, {1, 2}.
def _optional_omissions(optional: frozenset[int]) -> Iterator[frozenset[int]]:
    for omitted_count in range(len(optional) + 1):
        for omitted in itertools.combinations(sorted(optional), omitted_count):
            yield frozenset(omitted)


# "Huawei.CE?.CE6800?.CE6850" includes both "Huawei.CE.CE6800.CE6850" and "Huawei.CE6850".
def expand_devdb_key(key: str) -> set[str]:
    canonical, optional = parse_devdb_key(key)
    return {
        ".".join(part for index, part in enumerate(canonical) if index not in omitted)
        for omitted in _optional_omissions(optional)
    }


# "Huawei.CE.CE6800" -> "Huawei_CE_CE6800".
def sanitize_node(node: str) -> str:
    result = node.replace(".", "_")
    if not result.isidentifier():
        raise ValueError(f"unable to convert {node!r} to a valid python identifier")
    return result


# ("Huawei", "CE6850") -> ("Huawei", "CE", "CE6800", "CE6850").
def _expanded_nodes(keys: Iterable[str]) -> dict[Node, Node]:
    canonical_owners: dict[Node, str] = {}
    owners: dict[Node, str] = {}
    targets: dict[Node, Node] = {}

    for key in keys:
        canonical, optional = parse_devdb_key(key)
        if canonical in canonical_owners and canonical_owners[canonical] != key:
            path = ".".join(canonical)
            raise ValueError(f"devdb keys {canonical_owners[canonical]!r} and {key!r} both generate path {path!r}")
        canonical_owners[canonical] = key

        for omitted in _optional_omissions(optional):
            expanded = []
            for index, part in enumerate(canonical):
                if index in omitted:
                    continue

                expanded.append(part)
                node = tuple(expanded)
                target = canonical[: index + 1]
                if node in targets and targets[node] != target:
                    path = ".".join(node)
                    raise ValueError(f"devdb keys {owners[node]!r} and {key!r} both generate path {path!r}")
                owners.setdefault(node, key)
                targets[node] = target

    return targets


# ("Huawei", "CE6800") is child "CE6800" of ("Huawei",).
def _children_by_node(nodes: Iterable[Node]) -> dict[Node, dict[str, Node]]:
    children: dict[Node, dict[str, Node]] = {node: {} for node in nodes}

    for node in children:
        if len(node) > 1:
            children[node[:-1]][node[-1]] = node

    return children


def _class_representatives(
    targets: Mapping[Node, Node], children: Mapping[Node, Mapping[str, Node]]
) -> dict[Node, Node]:
    representatives: dict[Node, Node] = {}
    representatives_by_signature: dict[ClassSignature, Node] = {}

    # Leaves first: child representatives are part of their parent's signature.
    for node in sorted(targets, key=lambda item: (-len(item), item)):
        child_types = tuple((name, representatives[child]) for name, child in sorted(children[node].items()))
        signature = (targets[node], child_types)
        # Aruba.AP615 and Aruba.AP.AP600.AP615 can share Aruba_AP_AP600_AP615.
        representatives[node] = representatives_by_signature.setdefault(signature, node)

    return representatives


def _node_name(node: Node) -> str:
    return sanitize_node(".".join(node))


def _shortest_paths(targets: Mapping[Node, Node]) -> list[Node]:
    shortest: dict[Node, Node] = {}

    for path, target in targets.items():
        # Huawei.CE6850 wins over Huawei.CE.CE6800.CE6850 for the same target.
        if target not in shortest or (len(path), path) < (len(shortest[target]), shortest[target]):
            shortest[target] = path

    return sorted(shortest.values())


def generate_stubs(devdb: Mapping[str, str]) -> str:
    targets = _expanded_nodes(devdb)
    children = _children_by_node(targets)
    representatives = _class_representatives(targets, children)
    classes = sorted(set(representatives.values()))

    code = ""
    code += "# Generated by annet/annlib/netdev/devdb/generate_stubs.py\n"
    code += "# DO NOT MODIFY!\n"
    # Keep one short spelling per canonical target in the module docstring.
    code += '"""\n'
    for node in _shortest_paths(targets):
        code += f"hw.{'.'.join(node)}\n"
    code += '"""\n'
    code += "from __future__ import annotations\n"
    code += "\n"
    code += "from annet.annlib.netdev.views.hardware import HardwareLeaf\n"
    code += "\n"
    code += "\n"

    # Each representative becomes one HardwareLeaf subclass.
    for node in classes:
        code += f"class {_node_name(node)}(HardwareLeaf):\n"
        for name, child in sorted(children[node].items()):
            code += f"    {name}: {_node_name(representatives[child])}\n"
        if not children[node]:
            code += "    ...\n"
        code += "\n"

    # FakeHardwareView is the typed root: hw.Huawei starts at its Huawei field.
    code += "class FakeHardwareView(HardwareLeaf):\n"
    code += '    """\n'
    code += "    NOT TO BE USED AT RUNTIME\n"
    code += "    fake base class for HardwareView that has annotations for entire devdb\n"
    code += '    """\n'
    code += "\n"
    root_nodes = sorted(node for node in targets if len(node) == 1)
    for node in root_nodes:
        code += f"    {node[0]}: {_node_name(representatives[node])}\n"
    if not root_nodes:
        # devdb is empty?
        code += "    ...\n"

    return code


def _main() -> None:
    import json
    import sys

    if len(sys.argv) != 3:
        print(f"Usage: {sys.executable} {sys.argv[0]} <devdb.json> <generated.pyi>")
        sys.exit(2)

    file_devdb = sys.argv[1]
    file_code = sys.argv[2]

    with open(file_devdb, "r") as f:
        devdb = json.load(f)

    with open(file_code, "w") as f:
        f.write(generate_stubs(devdb))


if __name__ == "__main__":
    _main()
