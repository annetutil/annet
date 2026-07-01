from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any, cast

from annet.annlib.patching import match_row_to_acl
from annet.annlib.rbparser.acl import compile_ref_acl_text


class RefMatchResult:
    def __init__(self, gen_cls: type | None = None, groups: list[Any] | None = None) -> None:
        self.elems: dict[type, list[Any]] = {}
        if gen_cls and groups:
            self.elems[gen_cls] = groups

    def gen_cls(self) -> list[type]:
        return list(self.elems.keys())

    def groups(self) -> list[Any]:
        return list(sum(self.elems.values(), []))

    def __iter__(self) -> Iterator[tuple[type, list[Any]]]:
        yield from self.elems.items()

    def __add__(self, other: RefMatchResult) -> RefMatchResult:
        ret = RefMatchResult()
        ret.elems.update(self.elems)
        ret.elems.update(other.elems)
        return ret


class RefMatch:
    def __init__(self, acl: Any, gen_cls: type) -> None:
        self.acl = acl
        self.gen_cls = gen_cls

    def match(self, config: dict[str, Any]) -> RefMatchResult:
        ret = RefMatchResult()
        passed = self._match(config, self.acl)
        if passed:
            ret = RefMatchResult(self.gen_cls, passed)
        return ret

    @classmethod
    def _match(cls, config: dict[str, Any], acl: Any, _path: tuple[str, ...] = tuple()) -> list[Any]:
        ret: list[Any] = []
        for row, children in config.items():
            (rule, children_rules) = match_row_to_acl(row, acl)
            if rule and rule["attrs"]["match"]:
                ret.append(rule["attrs"]["match"])
            if rule and children and children_rules:
                ret += cls._match(children, children_rules, _path + (row,))
        return ret


class RefMatcher:
    def __init__(self) -> None:
        self.matches: list[RefMatch] = []

    def match(self, config: dict[str, Any]) -> RefMatchResult:
        ret = RefMatchResult()
        for rmatch in self.matches:
            ret += rmatch.match(config)
        return ret

    def add(self, acl_text: str, gen_class: type) -> None:
        acl = compile_ref_acl_text(acl_text)
        self.matches.append(RefMatch(acl, gen_class))


class RefTracker:
    class Root:
        pass

    def __init__(self) -> None:
        # mapidx is a bidirectional map: node_id (int) <-> generator class (type).
        self.cfgs: dict[Any, Any] = {}
        self.mapidx: dict[Any, Any] = {}
        self.graph = Graph()
        self.root = self.__class__.Root
        self.map(self.root, self.graph.root_id)

    def map(self, newcls: type, node_id: int) -> None:
        self.mapidx[node_id] = newcls
        self.mapidx[newcls] = node_id

    def addcls(self, newcls: type) -> int:
        if newcls not in self.mapidx:
            self.map(newcls, self.graph.newnode())
        return cast(int, self.mapidx[newcls])

    def add(self, refcls: type, defcls: type) -> None:
        if refcls not in self.mapidx:
            self.add(self.root, refcls)
        ridx = self.addcls(refcls)
        didx = self.addcls(defcls)
        self.graph.connect(ridx, didx)

    def config(self, newcls: type, config: Any) -> None:
        self.cfgs[newcls] = config

    def walk(self) -> Generator[tuple[Any, Any], None, list[tuple[type, type]]]:
        ret: list[tuple[type, type]] = []
        for didx, ridx in self.graph.walk():
            dc = self.mapidx[didx]
            rc = self.mapidx[ridx]
            yield dc, rc
        return ret

    def configs(self) -> list[tuple[Any, Any]]:
        ret: list[tuple[Any, Any]] = []
        for dc, rc in self.walk():
            if dc in self.cfgs and rc in self.cfgs:
                ret.append((self.cfgs[dc], self.cfgs[rc]))
        return ret


class Graph:
    def __init__(self) -> None:
        self.indices: list[list[int]] = []
        self.root_id = self.newnode()

    def newnode(self) -> int:
        node_id = len(self.indices)
        self.indices.append([0 for _ in range(len(self.indices))])
        for ind in self.indices:
            ind.append(0)
        return node_id

    def connect(self, ridx: int, didx: int) -> None:
        self.indices[ridx][didx] = 1

    def walk(self) -> Iterator[tuple[int, int]]:
        def childs(ridx: int) -> list[tuple[int, int]]:
            ret: list[tuple[int, int]] = []
            for didx, is_ref in enumerate(self.indices[ridx]):
                if is_ref:
                    ret.append((ridx, didx))
            return ret

        def bfs(run: list[tuple[int, int]], seen: set[tuple[int, int]]) -> Iterator[tuple[int, int]]:
            ch: list[tuple[int, int]] = []
            for key in run:
                ridx, didx = key
                if key not in seen:
                    seen.add(key)
                    ch += childs(didx)
                    yield ridx, didx
            if ch:
                yield from bfs(ch, seen)

        for left, right in bfs(childs(self.root_id), set()):
            if left not in (self.root_id, right):
                yield left, right
