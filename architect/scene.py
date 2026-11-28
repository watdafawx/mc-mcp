"""Declarative scene graph IR + compiler for the architect (design: docs/SCENE_GRAPH_DESIGN.md).

A Scene is plain JSON: a site origin, a style kit (+ role overrides) and a flat list of nodes. Each node names a
generator (structure, platform, bridge, slope, spire, shape, multiblock, boxes) and its params, and is placed either
absolutely (`at`, scene-local) or by attaching to a named anchor of another node:

    {"id": "dish", "kind": "shape", "params": {"shape": "dome", "r": 3, "block": "$glass"},
     "attach": {"target": "wing_create", "surface": "roof_deck", "align": "center", "offset": [0, 0, 0]}}

so the model never does world arithmetic. compile() runs the generators (pure Python, deterministic, no Minecraft),
solves the attachments, and returns one ghost spec per node ({id, origin, palette, boxes, blocks, bounds, anchors})
plus checks (floating nodes, overlaps, blocks the pack lacks) and a compact describe() for the model.
"$role" strings in params are replaced with the resolved kit block ("$trim[axis=y]" keeps the state).
apply_patch() edits a scene with set_node / add_node / patch_node / remove_node / set_palette / set_scene ops;
CompileResult.diff() says which ghosts to redraw.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import inspect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shapes  # noqa: E402  (before massing: shapes imports massing at its end)
import massing  # noqa: E402
import interiors  # noqa: E402
import multiblocks  # noqa: E402
import palettes  # noqa: E402

VERSION = 1
KINDS = ("structure", "platform", "bridge", "slope", "spire", "shape", "multiblock", "boxes")
MASSING = {"structure": massing.structure, "platform": massing.platform, "bridge": massing.bridge,
           "slope": massing.slope, "spire": massing.spire}
DEFAULT_TAG = {"structure": "volume", "platform": "platform", "bridge": "part", "slope": "part", "spire": "part",
               "shape": "part", "multiblock": "multiblock", "boxes": "prop"}
NODE_KEYS = ("id", "kind", "tag", "at", "attach", "kit", "roles", "params", "anchors", "floating")
SCENE_KEYS = ("version", "id", "origin", "kit", "roles", "ground_y", "nodes")
ATTACH_KEYS = ("target", "surface", "align", "align_y", "offset", "side")
ALIGN = ("center", "min", "max")
SIDES = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
SIDE_ALIAS = {"n": "north", "s": "south", "e": "east", "w": "west"}
SURFACE_ALIAS = {"roof": "roof_deck", "deck": "roof_deck", "centre": "center"}
BIG = 250_000  # boxes bigger than this are not expanded (bounds only, treated as supported)
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
AIR = palettes.AIR

HELP = """Scene nodes: {id, kind, params, at:[x,y,z] | attach:{target, surface, align, offset, side}, kit?, roles?, tag?}.
kinds: structure | platform | bridge | slope | spire (massing styled volumes), shape (params.parts=[...] or
params.shape=<kind>), multiblock (params.kind=<crafting_cpu|controller_frame|...>), boxes (params palette/boxes/blocks).
"$role" in params = the kit block for that role ("$glass", "$trim[axis=y]").
Anchors on every node: top, bottom, ground, center, interior, roof_deck, floor, wall:north|south|east|west;
structures add floor[i] (per storey), door:<side>, pad[i] (ground-floor rooms of params.program[0]).
attach puts the child against the surface: on a face it sits outside it (side=inside: just inside it); on the
other axes align=center|min|max (str = x and z; dict {x,y,z} per axis; y defaults to min); offset [dx,dy,dz] last."""


class SceneError(ValueError):
    pass


# ------------------------------------------------------------------------------------------ small helpers

def _int(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and not v.is_integer()):
        raise SceneError(f"{what}: expected an integer, got {v!r}")
    return int(v)


def _vec(v, what):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise SceneError(f"{what}: expected [x, y, z], got {v!r}")
    return [_int(a, what) for a in v]


def _suggest(word, options):
    near = difflib.get_close_matches(str(word), list(options), n=1)
    return f" (did you mean {near[0]!r}?)" if near else ""


def _unknown_keys(d, allowed, what):
    bad = [k for k in d if k not in allowed]
    if bad:
        raise SceneError(f"{what}: unknown key {bad[0]!r}{_suggest(bad[0], allowed)}; allowed: {list(allowed)}")


def _anchor(lo, hi, normal, label=None):
    a = {"min": [int(v) for v in lo], "max": [int(v) for v in hi], "normal": [int(v) for v in normal]}
    if label:
        a["label"] = label
    return a


def _shift(a, d):
    out = dict(a)
    out["min"] = [a["min"][i] + d[i] for i in range(3)]
    out["max"] = [a["max"][i] + d[i] for i in range(3)]
    return out


def canon_surface(name: str) -> str:
    """'wall:n' -> 'wall:north', 'pad:0' -> 'pad[0]', 'roof' -> 'roof_deck'."""
    s = str(name).strip().lower().replace(" ", "")
    s = SURFACE_ALIAS.get(s, s)
    head, sep, tail = s.partition(":")
    if sep and tail.isdigit():
        return f"{head}[{tail}]"
    if sep and head in ("wall", "door"):
        return f"{head}:{SIDE_ALIAS.get(tail, tail)}"
    return s


def _merge_patch(target, patch):
    """RFC 7386 JSON merge patch: dicts merge, None deletes, anything else replaces."""
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    out = dict(target) if isinstance(target, dict) else {}
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = _merge_patch(out.get(k), v)
    return out


def _norm_attach(a, nid):
    if a is None:
        return None
    if isinstance(a, str):  # shorthand "hub.roof_deck"
        t, sep, s = a.partition(".")
        if not sep:
            raise SceneError(f"node {nid!r}: attach shorthand must be 'target.surface', got {a!r}")
        a = {"target": t, "surface": s}
    if not isinstance(a, dict):
        raise SceneError(f"node {nid!r}: attach must be an object, got {a!r}")
    _unknown_keys(a, ATTACH_KEYS, f"node {nid!r} attach")
    t, s = a.get("target"), a.get("surface")
    if not isinstance(t, str) or not t:
        raise SceneError(f"node {nid!r}: attach.target must be a node id")
    if not isinstance(s, str) or not s:
        raise SceneError(f"node {nid!r}: attach.surface must be an anchor name (e.g. roof_deck, wall:north)")
    al = a.get("align", "center")
    if isinstance(al, dict):
        _unknown_keys(al, ("x", "y", "z"), f"node {nid!r} attach.align")
        vals = list(al.values())
        al = {k: al[k] for k in ("x", "y", "z") if k in al}
    else:
        vals = [al]
    for v in vals + ([a["align_y"]] if a.get("align_y") is not None else []):
        if v not in ALIGN:
            raise SceneError(f"node {nid!r}: align {v!r} must be one of {list(ALIGN)}")
    side = a.get("side", "outside")
    if side not in ("outside", "inside"):
        raise SceneError(f"node {nid!r}: attach.side must be outside or inside, got {side!r}")
    out = {"target": t, "surface": canon_surface(s), "align": al,
           "offset": _vec(a.get("offset", [0, 0, 0]), f"node {nid!r} attach.offset"), "side": side}
    if a.get("align_y") is not None:
        out["align_y"] = a["align_y"]
    return out


def _attach_to_dict(a):
    out = {"target": a["target"], "surface": a["surface"]}
    if a["align"] != "center":
        out["align"] = copy.deepcopy(a["align"])
    if "align_y" in a:
        out["align_y"] = a["align_y"]
    if a["offset"] != [0, 0, 0]:
        out["offset"] = list(a["offset"])
    if a["side"] != "outside":
        out["side"] = a["side"]
    return out


# ------------------------------------------------------------------------------------------ IR

@dataclass
class Node:
    id: str
    kind: str
    params: dict = field(default_factory=dict)
    at: list | None = None
    attach: dict | None = None
    kit: str | None = None
    roles: dict = field(default_factory=dict)
    tag: str | None = None
    anchors: dict = field(default_factory=dict)  # custom anchors, node-local {name: {min, max, normal}}
    floating: bool = False  # allowed to float (airship, hanging sign): skips the floating check

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        if not isinstance(d, dict):
            raise SceneError(f"node must be an object, got {d!r}")
        nid = d.get("id")
        if not isinstance(nid, str) or not nid.strip() or any(c in nid for c in "/ \t\n"):
            raise SceneError(f"node id must be a non-empty string without '/' or spaces, got {nid!r}")
        _unknown_keys(d, NODE_KEYS, f"node {nid!r}")
        kind = d.get("kind")
        if kind not in KINDS:
            raise SceneError(f"node {nid!r}: kind {kind!r}{_suggest(kind, KINDS)} must be one of {list(KINDS)}")
        params = copy.deepcopy(d.get("params") or {})
        if not isinstance(params, dict):
            raise SceneError(f"node {nid!r}: params must be an object")
        kit = d.get("kit")
        roles = copy.deepcopy(d.get("roles") or {})
        if kind in MASSING:  # kit/roles belong on the node (the palette resolver feeds them); lift them out of params
            if "kit" in params:
                pk = params.pop("kit")
                if kit is not None and pk != kit:
                    raise SceneError(f"node {nid!r}: kit given twice ({kit!r} and params.kit {pk!r})")
                kit = pk
            if isinstance(params.get("roles"), dict):
                roles = {**params.pop("roles"), **roles}
        if kit is not None and kit not in palettes.list_kits():
            raise SceneError(f"node {nid!r}: unknown kit {kit!r}{_suggest(kit, palettes.list_kits())}")
        if not isinstance(roles, dict):
            raise SceneError(f"node {nid!r}: roles must be an object")
        at = _vec(d["at"], f"node {nid!r} at") if d.get("at") is not None else None
        attach = _norm_attach(d.get("attach"), nid)
        if at is not None and attach is not None:
            raise SceneError(f"node {nid!r}: give either at or attach (use attach.offset to nudge)")
        anchors = {}
        for name, a in (d.get("anchors") or {}).items():
            if not isinstance(a, dict):
                raise SceneError(f"node {nid!r}: anchor {name!r} must be {{min, max, normal}}")
            _unknown_keys(a, ("min", "max", "normal", "label"), f"node {nid!r} anchor {name!r}")
            lo, hi = _vec(a.get("min"), f"anchor {name} min"), _vec(a.get("max", a.get("min")), f"anchor {name} max")
            anchors[canon_surface(name)] = _anchor([min(lo[i], hi[i]) for i in range(3)],
                                                   [max(lo[i], hi[i]) for i in range(3)],
                                                   _vec(a.get("normal", [0, 0, 0]), f"anchor {name} normal"),
                                                   a.get("label"))
        tag = d.get("tag")
        if tag is not None and not isinstance(tag, str):
            raise SceneError(f"node {nid!r}: tag must be a string")
        return cls(id=nid, kind=kind, params=params, at=at, attach=attach, kit=kit, roles=roles, tag=tag,
                   anchors=anchors, floating=bool(d.get("floating", False)))

    def to_dict(self) -> dict:
        out: dict = {"id": self.id, "kind": self.kind}
        if self.tag:
            out["tag"] = self.tag
        if self.at is not None:
            out["at"] = list(self.at)
        if self.attach is not None:
            out["attach"] = _attach_to_dict(self.attach)
        if self.kit is not None:
            out["kit"] = self.kit
        if self.roles:
            out["roles"] = copy.deepcopy(self.roles)
        out["params"] = copy.deepcopy(self.params)
        if self.anchors:
            out["anchors"] = copy.deepcopy(self.anchors)
        if self.floating:
            out["floating"] = True
        return out


@dataclass
class Scene:
    id: str = "scene"
    origin: list = field(default_factory=lambda: [0, 0, 0])
    kit: str = "station_white"
    roles: dict = field(default_factory=dict)
    nodes: list = field(default_factory=list)
    ground_y: int = 0  # scene-local y of the ground: a node with a block at or below it stands on its own

    # ---- (de)serialisation

    @classmethod
    def from_dict(cls, d: dict) -> "Scene":
        if not isinstance(d, dict):
            raise SceneError("scene must be an object")
        _unknown_keys(d, SCENE_KEYS, "scene")
        if d.get("version", VERSION) != VERSION:
            raise SceneError(f"scene version {d.get('version')} not supported (this is {VERSION})")
        sid = d.get("id", "scene")
        if not isinstance(sid, str) or not sid or any(c in sid for c in "/ \t\n"):
            raise SceneError(f"scene id must be a non-empty string without '/' or spaces, got {sid!r}")
        kit = d.get("kit", "station_white")
        if kit not in palettes.list_kits():
            raise SceneError(f"scene: unknown kit {kit!r}{_suggest(kit, palettes.list_kits())}; "
                             f"one of {palettes.list_kits()}")
        roles = copy.deepcopy(d.get("roles") or {})
        if not isinstance(roles, dict):
            raise SceneError("scene: roles must be an object")
        nodes = [Node.from_dict(n) for n in (d.get("nodes") or [])]
        seen = set()
        for n in nodes:
            if n.id in seen:
                raise SceneError(f"duplicate node id {n.id!r}")
            seen.add(n.id)
        return cls(id=sid, origin=_vec(d.get("origin", [0, 0, 0]), "scene origin"), kit=kit, roles=roles,
                   nodes=nodes, ground_y=_int(d.get("ground_y", 0), "scene ground_y"))

    def to_dict(self) -> dict:
        out = {"version": VERSION, "id": self.id, "origin": list(self.origin), "kit": self.kit}
        if self.roles:
            out["roles"] = copy.deepcopy(self.roles)
        if self.ground_y:
            out["ground_y"] = self.ground_y
        out["nodes"] = [n.to_dict() for n in self.nodes]
        return out

    @classmethod
    def from_json(cls, text: str) -> "Scene":
        return cls.from_dict(json.loads(text))

    def to_json(self, indent: int | None = 1) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def copy(self) -> "Scene":
        return Scene.from_dict(self.to_dict())

    # ---- graph

    def index(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}

    def get(self, nid: str) -> Node:
        for n in self.nodes:
            if n.id == nid:
                return n
        ids = [n.id for n in self.nodes]
        raise SceneError(f"no node {nid!r}{_suggest(nid, ids)}; nodes: {ids}")

    def children(self, nid: str) -> list[str]:
        return [n.id for n in self.nodes if n.attach and n.attach["target"] == nid]

    def dependents(self, nid: str) -> list[str]:
        """Every node attached to nid directly or through other nodes, in scene order."""
        out, todo = set(), [nid]
        while todo:
            cur = todo.pop()
            for c in self.children(cur):
                if c not in out and c != nid:
                    out.add(c)
                    todo.append(c)
        return [n.id for n in self.nodes if n.id in out]

    def order(self) -> list[str]:
        """Node ids with every attach target before its children. Raises on a missing target or a cycle."""
        idx = self.index()
        state: dict[str, int] = {}
        out: list[str] = []

        def visit(nid, path):
            st = state.get(nid)
            if st == 2:
                return
            if st == 1:
                cyc = path[path.index(nid):] + [nid]
                raise SceneError("attach cycle: " + " -> ".join(cyc))
            state[nid] = 1
            a = idx[nid].attach
            if a:
                t = a["target"]
                if t not in idx:
                    raise SceneError(f"node {nid!r} attaches to unknown node {t!r}{_suggest(t, idx)}; "
                                     f"nodes: {list(idx)}")
                visit(t, path + [nid])
            state[nid] = 2
            out.append(nid)

        for n in self.nodes:
            visit(n.id, [])
        return out

    def validate(self) -> None:
        self.order()

    # ---- patches

    def apply_patch(self, ops) -> dict:
        """Apply edit ops atomically (all or nothing). Returns {changed, removed, dirty}: dirty = changed nodes plus
        everything attached to them (their position may move). CompileResult.diff() gives the exact redraw set.
        ops: one op or a list of
          {"op": "set_node", "node": {...}}                  add or replace a node (keeps its list position)
          {"op": "add_node", "node": {...}}                  add; error if the id exists
          {"op": "patch_node", "id": "x", "patch": {...}}    JSON merge patch on the node dict (null deletes a key)
          {"op": "remove_node", "id": "x", "orphans": "error|remove|pin"}
               nodes attached to x: error (default), remove them too, or pin them where they are now (at = origin)
          {"op": "set_palette", "kit": "gothic", "roles": {"glass": "...", "trim": null}, "id": "x"?, "replace_roles": false}
               scene palette, or one node's palette with id; roles merge (null deletes) unless replace_roles
          {"op": "set_scene", "origin": [x, y, z], "ground_y": 0}"""
        if isinstance(ops, dict):
            ops = [ops]
        if not isinstance(ops, list):
            raise SceneError("patch must be an op object or a list of ops")
        work = self.copy()
        changed: list[str] = []
        removed: list[str] = []
        for i, op in enumerate(ops):
            try:
                work._apply_one(op, changed, removed)
            except SceneError as e:
                name = op.get("op") if isinstance(op, dict) else op
                raise SceneError(f"patch op {i} ({name}): {e}") from None
        work.validate()
        self.id, self.origin, self.kit, self.roles = work.id, work.origin, work.kit, work.roles
        self.nodes, self.ground_y = work.nodes, work.ground_y
        ids = [n.id for n in self.nodes]
        dirty = set(c for c in changed if c in ids)
        for c in list(dirty):
            dirty.update(self.dependents(c))
        return {"changed": [i for i in ids if i in set(changed)], "removed": removed,
                "dirty": [i for i in ids if i in dirty]}

    def _replace(self, node: Node, must_exist: bool | None):
        for i, n in enumerate(self.nodes):
            if n.id == node.id:
                if must_exist is False:
                    raise SceneError(f"node {node.id!r} already exists (use set_node or patch_node)")
                self.nodes[i] = node
                return
        if must_exist:
            raise SceneError(f"no node {node.id!r}")
        self.nodes.append(node)

    def _apply_one(self, op, changed, removed):
        if not isinstance(op, dict) or "op" not in op:
            raise SceneError(f"op must be an object with 'op', got {op!r}")
        kind = op["op"]
        if kind in ("set_node", "add_node"):
            _unknown_keys(op, ("op", "node"), kind)
            node = Node.from_dict(op.get("node"))
            self._replace(node, False if kind == "add_node" else None)
            changed.append(node.id)
        elif kind == "patch_node":
            _unknown_keys(op, ("op", "id", "patch"), kind)
            cur = self.get(op.get("id"))
            patch = op.get("patch")
            if not isinstance(patch, dict):
                raise SceneError("patch must be an object (JSON merge patch)")
            merged = _merge_patch(cur.to_dict(), patch)
            if merged.get("id") != cur.id:
                raise SceneError("patch_node cannot change the id (remove_node + set_node)")
            if "at" in patch and patch["at"] is not None and "attach" not in patch:
                merged.pop("attach", None)  # moving to an absolute spot detaches
            if "attach" in patch and patch["attach"] is not None and "at" not in patch:
                merged.pop("at", None)
            self._replace(Node.from_dict(merged), True)
            changed.append(cur.id)
        elif kind == "remove_node":
            _unknown_keys(op, ("op", "id", "orphans"), kind)
            nid = self.get(op.get("id")).id
            orphans = op.get("orphans", "error")
            deps = self.dependents(nid)
            if deps and orphans == "error":
                raise SceneError(f"node {nid!r} has attached nodes {deps}; pass orphans: remove | pin")
            if orphans not in ("error", "remove", "pin"):
                raise SceneError(f"orphans must be error, remove or pin, got {orphans!r}")
            gone = {nid}
            if orphans == "remove":
                gone.update(deps)
            elif deps:
                res = self.compile()  # positions don't depend on the registry
                for c in self.children(nid):
                    n = self.get(c)
                    n.at, n.attach = list(res.local_origin[c]), None
                    changed.append(c)
            self.nodes = [n for n in self.nodes if n.id not in gone]
            removed.extend(i for i in [nid] + deps if i in gone)
        elif kind == "set_palette":
            _unknown_keys(op, ("op", "id", "kit", "roles", "replace_roles"), kind)
            target = self.get(op["id"]) if op.get("id") is not None else self
            if "kit" in op:
                k = op["kit"]
                if k is None and target is self:
                    raise SceneError("the scene needs a kit")
                if k is not None and k not in palettes.list_kits():
                    raise SceneError(f"unknown kit {k!r}{_suggest(k, palettes.list_kits())}")
                target.kit = k
            if "roles" in op:
                r = op["roles"] or {}
                if not isinstance(r, dict):
                    raise SceneError("roles must be an object")
                base = {} if op.get("replace_roles") else target.roles
                target.roles = {k: v for k, v in _merge_patch(base, r).items() if v is not None}
                for k, v in target.roles.items():
                    palettes.as_chain(v, f"role {k}")
            if target is self:
                changed.extend(n.id for n in self.nodes if n.kit is None)
            else:
                changed.append(target.id)
        elif kind == "set_scene":
            _unknown_keys(op, ("op", "origin", "ground_y", "id"), kind)
            if "origin" in op:
                self.origin = _vec(op["origin"], "origin")
            if "ground_y" in op:
                self.ground_y = _int(op["ground_y"], "ground_y")
            if "id" in op:
                self.id = Scene.from_dict({"id": op["id"], "kit": self.kit}).id
            changed.extend(n.id for n in self.nodes)
        else:
            raise SceneError(f"unknown op {kind!r}{_suggest(kind, OPS)}; one of {list(OPS)}")

    # ---- compile

    def compile(self, available_blocks=None, on_missing: str = "report") -> "CompileResult":
        """Run every node's generator, solve attachments, check the result.
        available_blocks: None (preferred blocks), "vanilla", a registry_blocks result, or a list of ids.
        on_missing (blocks a generator emits that the registry lacks): report | drop | error."""
        if on_missing not in ("report", "drop", "error"):
            raise SceneError(f"on_missing must be report, drop or error, got {on_missing!r}")
        avail = palettes.normalize_available(available_blocks)
        order = self.order()
        idx = self.index()
        reports: dict = {}
        missing: dict[str, int] = {}
        geo: dict[str, dict] = {}
        for nid in order:
            n = idx[nid]
            kit = n.kit or self.kit
            over = dict(self.roles) if n.kit is None else {}
            over.update(n.roles)
            key = (kit, json.dumps(over, sort_keys=True))
            if key not in reports:
                try:
                    reports[key] = palettes.resolve_report(kit, avail, over)
                except palettes.PaletteError as e:
                    raise SceneError(f"node {nid!r}: {e}") from None
            K = {r: v["block"] for r, v in reports[key].items()}
            spec, info, params = _generate(n, kit, K)
            full, big = _cells(spec, nid)
            if not full and not big:
                raise SceneError(f"node {nid!r} ({n.kind}) produced no blocks")
            lo, hi = _bounds(full, big)  # geometry from the full spec: positions never depend on the pack
            cells = full
            if avail is not None:
                spec = _missing(spec, avail, missing, drop=on_missing == "drop")
                if on_missing == "drop":
                    cells, big = _cells(spec, nid)
            anchors = _box_anchors(lo, hi)
            if n.kind == "structure":
                anchors.update(_structure_anchors(params))
            elif n.kind == "platform":
                anchors.update(_platform_anchors(cells, K))
            anchors.update(copy.deepcopy(n.anchors))
            geo[nid] = {"spec": spec, "info": info, "cells": cells, "big": big, "lo": lo, "hi": hi,
                        "anchors": anchors, "kit": kit, "fallbacks": palettes.fallbacks(reports[key])}
        if missing and on_missing == "error":
            raise SceneError("blocks not in this pack: " + ", ".join(f"{b} ({c})" for b, c in sorted(missing.items())))
        local_origin: dict[str, list] = {}
        local_anchors: dict[str, dict] = {}
        for nid in order:
            n, g = idx[nid], geo[nid]
            if n.attach:
                a = n.attach
                tA = local_anchors[a["target"]]
                if a["surface"] not in tA:
                    raise SceneError(f"node {nid!r}: {a['target']!r} has no anchor {a['surface']!r}"
                                     f"{_suggest(a['surface'], tA)}; anchors: {anchor_names(tA)}")
                origin = _place(g["lo"], g["hi"], tA[a["surface"]], a)
            else:
                origin = list(n.at or [0, 0, 0])
            local_origin[nid] = origin
            local_anchors[nid] = {k: _shift(v, origin) for k, v in g["anchors"].items()}
        world_cells = {nid: {(x + local_origin[nid][0], y + local_origin[nid][1], z + local_origin[nid][2])
                             for (x, y, z) in geo[nid]["cells"]} for nid in order}
        floating, overlaps = _checks(self, world_cells, geo, local_origin)
        so = self.origin
        ghosts = []
        for n in self.nodes:
            g, o = geo[n.id], local_origin[n.id]
            wo = [so[i] + o[i] for i in range(3)]
            ghosts.append({
                "id": n.id, "ghost_id": f"{self.id}/{n.id}", "kind": n.kind, "tag": n.tag or DEFAULT_TAG[n.kind],
                "kit": g["kit"], "origin": wo, "palette": g["spec"]["palette"], "boxes": g["spec"]["boxes"],
                "blocks": g["spec"]["blocks"], "count": len(g["cells"]),
                "bounds": {"min": [wo[i] + g["lo"][i] for i in range(3)], "max": [wo[i] + g["hi"][i] for i in range(3)],
                           "size": [g["hi"][i] - g["lo"][i] + 1 for i in range(3)]},
                "anchors": {k: _shift(v, so) for k, v in local_anchors[n.id].items()},
                "attach": _attach_to_dict(n.attach) if n.attach else None, "info": g["info"],
                "fallbacks": g["fallbacks"]})
        warnings = []
        if floating:
            warnings.append(f"floating (touch nothing and not on the ground): {floating}")
        if missing:
            warnings.append(("dropped" if on_missing == "drop" else "not in this pack") + ": " +
                            ", ".join(sorted(missing)))
        scene_rep = palettes.resolve_report(self.kit, avail, self.roles)
        return CompileResult(scene_id=self.id, origin=list(so), kit=self.kit,
                             palette={r: v["block"] for r, v in scene_rep.items()},
                             fallbacks=palettes.fallbacks(scene_rep), ghosts=ghosts, order=order,
                             floating=floating, overlaps=overlaps, missing_blocks=dict(sorted(missing.items())),
                             warnings=warnings, local_origin=local_origin)


OPS = ("set_node", "add_node", "patch_node", "remove_node", "set_palette", "set_scene")


# ------------------------------------------------------------------------------------------ generation

def _subst(obj, K, where):
    if isinstance(obj, str) and obj.startswith("$"):
        name, sep, rest = obj[1:].partition("[")
        if name not in K:
            raise SceneError(f"{where}: unknown role ${name}{_suggest(name, K)}; roles: {sorted(K)}")
        return palettes.with_state(K[name], rest[:-1] if sep else None)
    if isinstance(obj, dict):
        return {k: _subst(v, K, where) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_subst(v, K, where) for v in obj]
    return obj


def _check_params(fn, params, where):
    sig = inspect.signature(fn)
    valid = [p for p, v in sig.parameters.items() if v.kind is not inspect.Parameter.VAR_KEYWORD
             and p not in ("kit", "roles")]
    for k in params:
        if k not in valid:
            raise SceneError(f"{where}: unknown param {k!r}{_suggest(k, valid)}; params: {valid}")


def _kit_kw(kit, K, kind):
    """kit/roles kwargs for a massing generator: known kits keep their name (massing has per-kit behaviour)."""
    if kit in massing.KITS:
        return {"kit": kit, "roles": K}
    kw = {"kit": dict(K), "roles": None}
    if kind == "structure":
        kw["roof"] = palettes.kit_info(kit)["meta"].get("roof_default", "flat")
    return kw


def _generate(n: Node, kit: str, K: dict):
    """-> (spec {palette, boxes, blocks} in node-local coords, info, substituted params)."""
    where = f"node {n.id!r} ({n.kind})"
    params = _subst(n.params, K, where)
    try:
        if n.kind in MASSING:
            fn = MASSING[n.kind]
            _check_params(fn, params, where)
            kw = {**_kit_kw(kit, K, n.kind), **params}
            return {"palette": {}, "boxes": [], "blocks": fn(**kw)}, None, params
        if n.kind == "shape":
            if "parts" in params:
                _unknown_keys(params, ("parts",), where)
                parts = params["parts"]
            elif "shape" in params:
                p = dict(params)
                parts = [{"kind": p.pop("shape"), **p}]
            else:
                raise SceneError(f"{where}: params need parts=[{{kind, at, ...}}] or shape=<kind>")
            if not isinstance(parts, list) or not parts:
                raise SceneError(f"{where}: parts must be a non-empty list")
            fixed = []
            for i, p in enumerate(parts):
                if not isinstance(p, dict):
                    raise SceneError(f"{where}: part {i} must be an object")
                p = dict(p)
                if p.get("kind") in MASSING and p.get("kind") != "bridge":
                    _check_params(MASSING[p["kind"]], {k: v for k, v in p.items() if k not in ("kind", "at", "kit", "roles")},
                                  f"{where} part {i}")
                    if "kit" not in p and "roles" not in p:
                        p.update(_kit_kw(kit, K, p["kind"]))
                fixed.append(p)
            blocks, summary = shapes.build(fixed)
            return {"palette": {}, "boxes": [], "blocks": blocks}, {"parts": summary}, params
        if n.kind == "multiblock":
            p = dict(params)
            mk = p.pop("kind", None) or p.pop("type", None)
            if mk is None:
                raise SceneError(f"{where}: params.kind must name the multiblock; one of {sorted(multiblocks.KINDS)}")
            if mk in multiblocks.KINDS:
                _check_params(multiblocks.KINDS[mk], p, where)
            spec = multiblocks.build(mk, **p)
            return ({"palette": dict(spec.get("palette") or {}), "boxes": list(spec.get("boxes") or []),
                     "blocks": list(spec.get("blocks") or [])}, spec.get("info"), params)
        # boxes: raw ghost spec
        _unknown_keys(params, ("palette", "boxes", "blocks"), where)
        pal = params.get("palette") or {}
        if not isinstance(pal, dict):
            raise SceneError(f"{where}: palette must be an object")
        boxes, blocks = params.get("boxes") or [], params.get("blocks") or []
        for b in boxes:
            if not isinstance(b, list) or len(b) < 7 or not all(isinstance(v, int) for v in b[:6]):
                raise SceneError(f"{where}: box must be [x1, y1, z1, x2, y2, z2, key, mode?], got {b!r}")
            if len(b) > 7 and b[7] not in ("fill", "hollow", "walls", "frame"):
                raise SceneError(f"{where}: box mode {b[7]!r} must be fill | hollow | walls | frame")
        for b in blocks:
            if not isinstance(b, list) or len(b) != 4 or not all(isinstance(v, int) for v in b[:3]):
                raise SceneError(f"{where}: block must be [x, y, z, key], got {b!r}")
        return {"palette": dict(pal), "boxes": [list(b) for b in boxes], "blocks": [list(b) for b in blocks]}, None, params
    except SceneError:
        raise
    except (shapes.ShapeError, multiblocks.MultiblockError, palettes.PaletteError, TypeError, ValueError, KeyError) as e:
        raise SceneError(f"{where}: {e}") from None


def _state_of(key, pal):
    s = pal.get(key, key)
    return s if isinstance(s, str) else str(s)


def _is_air(state) -> bool:
    try:
        return palettes.base_id(state) in AIR
    except palettes.PaletteError:
        return False


def _missing(spec, avail, missing, drop):
    """Count entries whose block the registry lacks; with drop, remove them from the spec."""
    pal = spec["palette"]

    def bad(key):
        s = _state_of(key, pal)
        b = palettes.base_id(s)
        return None if b in AIR or b in avail else b

    out = {"palette": pal, "boxes": [], "blocks": []}
    for what, i in (("boxes", 6), ("blocks", 3)):
        for e in spec[what]:
            b = bad(e[i])
            if b:
                missing[b] = missing.get(b, 0) + 1
                if drop:
                    continue
            out[what].append(e)
    return out


def _cells(spec, nid):
    """Filled cells {(x, y, z): state} of a spec (boxes first, then blocks; air carves), plus boxes too big to
    expand [(lo, hi)]."""
    pal = spec["palette"]
    cells: dict = {}
    big = []
    try:
        for b in spec["boxes"]:
            x1, x2 = sorted((int(b[0]), int(b[3])))
            y1, y2 = sorted((int(b[1]), int(b[4])))
            z1, z2 = sorted((int(b[2]), int(b[5])))
            s = _state_of(b[6], pal)
            air = _is_air(s)
            mode = b[7] if len(b) > 7 else "fill"
            if (x2 - x1 + 1) * (y2 - y1 + 1) * (z2 - z1 + 1) > BIG:
                if not air:
                    big.append(((x1, y1, z1), (x2, y2, z2)))
                continue
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    for z in range(z1, z2 + 1):
                        on = (x in (x1, x2), y in (y1, y2), z in (z1, z2))
                        if (mode == "hollow" and not any(on)) or (mode == "walls" and not (on[0] or on[2])) \
                                or (mode == "frame" and sum(on) < 2):
                            continue
                        if air:
                            cells.pop((x, y, z), None)
                        else:
                            cells[(x, y, z)] = s
        for b in spec["blocks"]:
            s = _state_of(b[3], pal)
            p = (int(b[0]), int(b[1]), int(b[2]))
            if _is_air(s):
                cells.pop(p, None)
            else:
                cells[p] = s
    except (IndexError, TypeError, ValueError) as e:
        raise SceneError(f"node {nid!r}: bad spec entry: {e}") from None
    return cells, big


def _bounds(cells, big):
    pts = list(cells) + [p for bb in big for p in bb]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


# ------------------------------------------------------------------------------------------ anchors

def _box_anchors(lo, hi) -> dict:
    """Anchors every node has, from its bounding box (node-local)."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    c = [(lo[i] + hi[i]) // 2 for i in range(3)]
    return {
        "top": _anchor([x0, y1, z0], [x1, y1, z1], (0, 1, 0)),
        "roof_deck": _anchor([x0, y1, z0], [x1, y1, z1], (0, 1, 0)),
        "floor": _anchor([x0, y0, z0], [x1, y0, z1], (0, 1, 0)),
        "bottom": _anchor([x0, y0, z0], [x1, y0, z1], (0, -1, 0)),
        "ground": _anchor([x0, y0, z0], [x1, y0, z1], (0, 0, 0)),
        "center": _anchor(c, c, (0, 0, 0)),
        "interior": _anchor(lo, hi, (0, 0, 0)),
        "wall:north": _anchor([x0, y0, z0], [x1, y1, z0], SIDES["north"]),
        "wall:south": _anchor([x0, y0, z1], [x1, y1, z1], SIDES["south"]),
        "wall:west": _anchor([x0, y0, z0], [x0, y1, z1], SIDES["west"]),
        "wall:east": _anchor([x1, y0, z0], [x1, y1, z1], SIDES["east"]),
    }


def _bbox2(cells):
    xs = [p[0] for p in cells]
    zs = [p[1] for p in cells]
    return min(xs), max(xs), min(zs), max(zs)


def _structure_anchors(params) -> dict:
    """Semantic anchors of massing.structure, from the same footprint maths it uses (node-local)."""
    sig = inspect.signature(massing.structure)
    b = sig.bind_partial(**{k: v for k, v in params.items() if k in sig.parameters})
    b.apply_defaults()
    p = b.arguments
    fp = massing.footprint(p["shape"], p["w"], p["d"], p["r"], p["r_in"], p["a0"], p["a1"], p["c"], p["cut_w"],
                           p["cut_d"])
    edge = massing.edge
    inner = {q for q in fp if q not in edge(fp)} if (p["ledges"] or p["pillars"]) else fp
    if len(inner) < 4:
        inner = fp
    wall_ring = edge(inner)
    ledged = inner is not fp
    icells = {q for q in inner if q not in wall_ring} or set(inner)
    hs = [max(3, int(h)) for h in p["floor_hs"]] if p["floor_hs"] else [p["floor_h"]] * p["floors"]
    y0s = [1 + sum(hs[:f]) for f in range(len(hs))]
    ry = sum(hs) + 1
    fx0, fx1, fz0, fz1 = _bbox2(fp)
    ix0, ix1, iz0, iz1 = _bbox2(icells)
    deck = {q for q in inner if q not in edge(inner)} or inner
    dx0, dx1, dz0, dz1 = _bbox2(deck)
    A = {
        "roof_deck": _anchor([dx0, ry, dz0], [dx1, ry, dz1], (0, 1, 0)),
        "floor": _anchor([ix0, 0, iz0], [ix1, 0, iz1], (0, 1, 0)),
        "interior": _anchor([ix0, 1, iz0], [ix1, ry - 1, iz1], (0, 0, 0)),
        # walls span their thickness (outer ring .. inner wall line): outside = against the facade, inside = the room
        "wall:north": _anchor([fx0, 0, fz0], [fx1, ry, max(fz0, iz0 - 1)], SIDES["north"]),
        "wall:south": _anchor([fx0, 0, min(fz1, iz1 + 1)], [fx1, ry, fz1], SIDES["south"]),
        "wall:west": _anchor([fx0, 0, fz0], [max(fx0, ix0 - 1), ry, fz1], SIDES["west"]),
        "wall:east": _anchor([min(fx1, ix1 + 1), 0, fz0], [fx1, ry, fz1], SIDES["east"]),
    }
    for f in range(len(hs)):
        fy = 0 if f == 0 else y0s[f]
        A[f"floor[{f}]"] = _anchor([ix0, fy, iz0], [ix1, fy, iz1], (0, 1, 0))
    if len(icells) < 9:
        return A
    # doors: the same rows massing._fit cuts (3 wide x 3 high, through the outer ring)
    ents = p["entrances"]
    ents = [ents] if isinstance(ents, str) else list(ents or [])
    keys = {"s": lambda q: q[1], "n": lambda q: -q[1], "e": lambda q: q[0], "w": lambda q: -q[0]}
    seen: dict[str, int] = {}
    for ent in ents:
        side, _, at = str(ent).lower().partition("@")
        side = side[:1]
        if side not in keys:
            continue
        key = keys[side]
        m = max(key(q) for q in wall_ring)
        row = [q for q in wall_ring if key(q) == m]
        other = (lambda q: q[0]) if side in "sn" else (lambda q: q[1])
        mid = int(at) if at.lstrip("-").isdigit() else sorted(other(q) for q in row)[len(row) // 2]
        full = SIDE_ALIAS[side]
        nx, _, nz = SIDES[full]
        wc = m if side in "se" else -m
        outer = wc + (nx + nz if ledged else 0)
        a, b = sorted((wc, outer))  # the doorway through the wall thickness
        if side in "sn":
            lo, hi = [mid - 1, 1, a], [mid + 1, 3, b]
        else:
            lo, hi = [a, 1, mid - 1], [b, 3, mid + 1]
        k = seen.get(full, 0)
        seen[full] = k + 1
        A[f"door:{full}" if k == 0 else f"door:{full}[{k}]"] = _anchor(lo, hi, SIDES[full])
    # pads: ground-floor rooms of program[0], split exactly like interiors.fit_floor
    prog = p["program"]
    first = prog[0] if prog else None
    kinds = [first] if isinstance(first, str) else list(first or [])
    kinds = [k for k in kinds if isinstance(k, str) and k.split(":")[0] in interiors.KINDS]
    if kinds:
        ax, _ = interiors.spine_of(icells)
        for i, seg in enumerate(interiors.split(icells, ax, len(kinds))):
            if seg:
                sx0, sx1, sz0, sz1 = _bbox2(seg)
                A[f"pad[{i}]"] = _anchor([sx0, 0, sz0], [sx1, 0, sz1], (0, 1, 0), kinds[i])
    return A


def _platform_anchors(cells, K) -> dict:
    rail = K.get("rail")
    deck = [p for p, s in cells.items() if s != rail]
    if not deck:
        return {}
    y = max(p[1] for p in deck)
    top = [(p[0], p[2]) for p in deck if p[1] == y]
    x0, x1, z0, z1 = _bbox2(top)
    a = _anchor([x0, y, z0], [x1, y, z1], (0, 1, 0))
    return {"roof_deck": a, "floor": dict(a)}


def _align_of(a, axis):
    al = a.get("align", "center")
    v = al.get(axis) if isinstance(al, dict) else (al if axis != "y" else None)
    if axis == "y" and v is None:
        v = a.get("align_y") or "min"
    return v or "center"


def _place(lo, hi, anc, a) -> list:
    """Origin (scene-local) that puts a child with local bounds lo..hi against anchor anc per attach a."""
    size = [hi[i] - lo[i] for i in range(3)]
    amin, amax, nrm = anc["min"], anc["max"], anc["normal"]
    inside = a.get("side") == "inside"
    want = [0, 0, 0]
    for i, axis in enumerate("xyz"):
        if nrm[i] > 0:
            want[i] = amin[i] - 1 - size[i] if inside else amax[i] + 1
        elif nrm[i] < 0:
            want[i] = amax[i] + 1 if inside else amin[i] - 1 - size[i]
        else:
            al = _align_of(a, axis)
            if al == "min":
                want[i] = amin[i]
            elif al == "max":
                want[i] = amax[i] - size[i]
            else:
                want[i] = amin[i] + (amax[i] - amin[i] - size[i]) // 2
        want[i] += a["offset"][i]
    return [want[i] - lo[i] for i in range(3)]


def anchor_names(anchors: dict) -> str:
    """Compact anchor list: 'roof_deck floor floor[0-2] wall:north|south|east|west pad[0-1] ...'."""
    groups: dict[str, list] = {}
    order: list[str] = []
    for name in anchors:
        if name.endswith("]") and "[" in name:
            head, _, idx = name[:-1].partition("[")
            g = head + "[]"
            item = idx
        elif ":" in name:
            head, _, item = name.partition(":")
            g = head + ":"
        else:
            g, item = name, None
        if g not in groups:
            groups[g] = []
            order.append(g)
        if item is not None:
            groups[g].append(item)
    out = []
    for g in order:
        items = groups[g]
        if g.endswith("[]"):
            nums = sorted(int(i) for i in items if i.isdigit())
            rng = f"{nums[0]}-{nums[-1]}" if nums and nums == list(range(nums[0], nums[-1] + 1)) and len(nums) > 1 \
                else ",".join(items)
            out.append(f"{g[:-2]}[{rng}]")
        elif g.endswith(":"):
            out.append(g + "|".join(items))
        else:
            out.append(g)
    return " ".join(out)


# ------------------------------------------------------------------------------------------ checks

def _checks(scene: Scene, world_cells, geo, local_origin):
    """floating: nodes not connected (6-face contact or overlap, through other nodes) to one that stands on the
    ground. overlaps: [{a, b, cells}] for node pairs sharing cells."""
    owner: dict = {}
    for nid, cs in world_cells.items():
        for c in cs:
            owner.setdefault(c, []).append(nid)
    adj = {nid: set() for nid in world_cells}
    shared: dict = {}
    for c, ids in owner.items():
        if len(ids) > 1:
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    k = tuple(sorted((a, b)))
                    shared[k] = shared.get(k, 0) + 1
                    adj[a].add(b)
                    adj[b].add(a)
    for nid, cs in world_cells.items():
        for (x, y, z) in cs:
            for dx, dy, dz in N6:
                o = owner.get((x + dx, y + dy, z + dz))
                if o:
                    for m in o:
                        if m != nid:
                            adj[nid].add(m)
    idx = scene.index()
    seeds = [nid for nid, cs in world_cells.items()
             if idx[nid].floating or geo[nid]["big"]
             or (geo[nid]["lo"][1] + local_origin[nid][1]) <= scene.ground_y]
    seen, todo = set(seeds), list(seeds)
    while todo:
        cur = todo.pop()
        for m in adj[cur]:
            if m not in seen:
                seen.add(m)
                todo.append(m)
    floating = [n.id for n in scene.nodes if n.id not in seen]
    overlaps = [{"a": a, "b": b, "cells": c} for (a, b), c in sorted(shared.items())]
    return floating, overlaps


# ------------------------------------------------------------------------------------------ result

@dataclass
class CompileResult:
    scene_id: str
    origin: list
    kit: str
    palette: dict  # the scene kit, resolved {role: block}
    fallbacks: list  # scene-kit roles that did not get their first choice
    ghosts: list  # one spec per node, in scene order (world coordinates)
    order: list  # attach order
    floating: list
    overlaps: list
    missing_blocks: dict  # block id -> spec entries (only with available_blocks)
    warnings: list
    local_origin: dict = field(default_factory=dict, repr=False)  # scene-local node origins

    @property
    def ok(self) -> bool:
        return not self.floating

    def ghost(self, nid: str) -> dict:
        for g in self.ghosts:
            if g["id"] == nid or g["ghost_id"] == nid:
                return g
        raise SceneError(f"no ghost {nid!r}; ghosts: {[g['id'] for g in self.ghosts]}")

    def ghost_set_args(self, compact: bool = True, mode: str = "replace") -> list[dict]:
        """One ghost_set argument dict per node. compact: block states move into the palette (short keys)."""
        out = []
        for g in self.ghosts:
            pal, boxes, blocks = dict(g["palette"]), [list(b) for b in g["boxes"]], [list(b) for b in g["blocks"]]
            if compact:
                keys: dict[str, str] = {v: k for k, v in pal.items()}

                def key(s):
                    if s in pal:
                        return s
                    if s not in keys:
                        k = f"_{len(keys)}"
                        while k in pal:
                            k += "_"
                        keys[s] = k
                        pal[k] = s
                    return keys[s]
                boxes = [b[:6] + [key(b[6])] + b[7:] for b in boxes]
                blocks = [b[:3] + [key(b[3])] for b in blocks]
            out.append({"id": g["ghost_id"], "origin": list(g["origin"]), "palette": pal, "boxes": boxes,
                        "blocks": blocks, "mode": mode})
        return out

    def hashes(self) -> dict[str, str]:
        return {g["ghost_id"]: hashlib.sha1(json.dumps([g["origin"], g["palette"], g["boxes"], g["blocks"]],
                                                       sort_keys=True).encode()).hexdigest() for g in self.ghosts}

    def diff(self, prev: "CompileResult | None") -> dict:
        """What to send after an edit: set = ghosts new or changed, clear = ghosts gone, keep = unchanged."""
        cur, old = self.hashes(), prev.hashes() if prev else {}
        return {"set": [g for g in cur if old.get(g) != cur[g]], "clear": [g for g in old if g not in cur],
                "keep": [g for g in cur if old.get(g) == cur[g]]}

    def to_dict(self, blocks: bool = True) -> dict:
        gs = [g if blocks else {k: v for k, v in g.items() if k not in ("palette", "boxes", "blocks")}
              for g in self.ghosts]
        return {"scene": self.scene_id, "origin": self.origin, "kit": self.kit, "palette": self.palette,
                "fallbacks": self.fallbacks, "order": self.order, "ghosts": gs, "floating": self.floating,
                "overlaps": self.overlaps, "missing_blocks": self.missing_blocks, "warnings": self.warnings}

    def describe(self, verbose: bool = False) -> str:
        """Compact summary for the model: node ids, placement, bounds and anchor names. No block dumps."""
        total = sum(g["count"] for g in self.ghosts)
        lines = [f"scene {self.scene_id} kit {self.kit} origin {self.origin}: {len(self.ghosts)} nodes, {total} blocks"]
        if self.fallbacks:
            lines.append("palette fallbacks: " + ", ".join(f"{f['role']} {f['wanted']} -> {f['picked']}"
                                                            for f in self.fallbacks))
        for g in self.ghosts:
            b = g["bounds"]
            size = "x".join(str(v) for v in b["size"])
            if g["attach"]:
                a = g["attach"]
                extra = "".join(f" {k} {a[k]}" for k in ("align", "align_y", "offset", "side") if k in a)
                where = f"on {a['target']}.{a['surface']}{extra}"
            else:
                where = f"at {g['origin']}"
            kit = f" kit {g['kit']}" if g["kit"] != self.kit else ""
            lines.append(f"- {g['id']} [{g['kind']}/{g['tag']}]{kit} {where}: size {size}, "
                         f"bounds {b['min']}..{b['max']}, {g['count']} blocks")
            if g["info"] and isinstance(g["info"], str):
                lines.append(f"    {g['info']}")
            if verbose:
                for name, a in g["anchors"].items():
                    lab = f" ({a['label']})" if a.get("label") else ""
                    lines.append(f"    {name}{lab}: {a['min']}..{a['max']} n{a['normal']}")
            else:
                lines.append("    anchors: " + anchor_names(g["anchors"]))
        ov = ", ".join(f"{o['a']}~{o['b']} {o['cells']}" for o in self.overlaps) or "none"
        top = sorted(self.missing_blocks.items(), key=lambda kv: (-kv[1], kv[0]))
        miss = ", ".join(f"{k} ({v})" for k, v in top[:6]) or "none"
        if len(top) > 6:
            miss += f", +{len(top) - 6} more"
        lines.append(f"checks: floating {self.floating or 'none'}; overlaps {ov}; missing {miss}")
        return "\n".join(lines)


def compile_scene(scene: dict | Scene, available_blocks=None, on_missing: str = "report") -> CompileResult:
    s = scene if isinstance(scene, Scene) else Scene.from_dict(scene)
    return s.compile(available_blocks, on_missing)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(HELP)
        sys.exit(0)
    sc = Scene.from_json(Path(sys.argv[1]).read_text(encoding="utf-8"))
    res = sc.compile(sys.argv[2] if len(sys.argv) > 2 else None)
    print(res.describe(verbose="-v" in sys.argv))
