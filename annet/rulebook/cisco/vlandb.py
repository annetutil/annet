import re

from annet.annlib.lib import cisco_collapse_vlandb as collapse_vlandb
from annet.annlib.lib import cisco_expand_vlandb as expand_vlandb
from annet.annlib.types import Op


VLANDB_CHUNK = 15
SWTRUNK_CHUNK = 5


# =====
def simple(rule, key, diff, hw, **_):
    yield from _process_vlandb(rule, key, diff, hw, False, VLANDB_CHUNK)


def swtrunk(rule, key, diff, hw, **_):
    yield from _process_vlandb(rule, key, diff, hw, True, SWTRUNK_CHUNK)


# =====
def _process_vlandb(rule, key, diff, hw, explicit_changing, multi_chunk):
    # pylint: disable=unused-argument
    for affected in diff[Op.AFFECTED]:
        # Изменилось содержимое блока vlan
        yield (True, affected["row"], affected["children"])

    (prefix, new, new_blocks) = _parse_vlancfg_actions(diff[Op.ADDED])
    (prefix2, old, old_blocks) = _parse_vlancfg_actions(diff[Op.REMOVED])
    if not prefix:
        prefix = prefix2

    if len(diff[Op.ADDED]) == 1 and len(new) == 0:
        # switchport trunk allowed vlan none
        yield (True, "%s none" % prefix, None)
        return
    for vlan_id in ((set(old_blocks.keys()) - set(new_blocks)) & new):
        # Удалено содержимое блока vlan, но сам влан остался
        yield (True, "%s %s" % (prefix, vlan_id), old_blocks[vlan_id])

    removed = old.difference(new)
    added = new.difference(old)
    if hw.Catalyst:
        # Каталисты не перечисляют вланы в batch режиме, если они представлены как блоки
        added -= new_blocks.keys()

    if removed:
        collapsed = collapse_vlandb(removed, hw.Catalyst)
        for chunk in _chunked(collapsed, multi_chunk):
            yield (False, "no %s%s%s" % (prefix, " remove " if explicit_changing else " ", ",".join(chunk)), None)

    if added:
        collapsed = collapse_vlandb(added, hw.Catalyst)
        for chunk in _chunked(collapsed, multi_chunk):
            yield (True, "%s%s%s" % (prefix, " add " if explicit_changing else " ", ",".join(chunk)), None)
    if new_blocks:
        for vlan_id, block in new_blocks.items():
            yield (True, "%s %s" % (prefix, vlan_id), block)


def _chunked(items, size):
    for offset in range(0, len(items), size):
        yield items[offset:offset + size]


def _parse_vlancfg_actions(actions):
    prefix = None
    vlandb = set()
    blocks = {}
    for action in actions:
        (prefix, part) = _parse_vlancfg(action["row"])
        if action["children"]:
            assert len(part) == 1, "vlandb block must contain one and only one vlanid: %s" % action["row"]
            blocks[list(part)[0]] = action["children"]
        vlandb.update(part)
    return (prefix, vlandb, blocks)


def _parse_vlancfg(row):
    # иногда циски ставят пробелы между влан ренджами, а иногда нет.
    words = re.sub(r",\s+", ",", row).split()

    if words[-1] == "none":
        # switchport trunk allowed vlan none
        return (" ".join(words[:-1]), set())
    assert re.match(r"[\d,-]+$", words[-1]), "Unable to parse vlancfg row: %s" % row
    prefix = " ".join(words[:-2] if words[-2] == "add" else words[:-1])
    vlancfg = words[-1]
    vlandb = expand_vlandb(vlancfg)
    return (prefix, vlandb)
