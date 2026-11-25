"""Facade depth pass (step 2 of the quality plan): the layer that makes a wall stop reading as one flat plane.

Runs at the end of massing.structure on its block dict. Every addition goes OUTWARD from the building (into the
outer ring between pilasters or outside the footprint), never into rooms: modded play needs every interior block for
machines, pipe runs and multiblocks.

What it adds (all from the kit, stairs/slabs derived from the role block when that variant exists):
- base skirt: a ring of stairs round the plinth, so the building flares into the ground;
- pier feet and capitals: a stair at the foot and an upside-down stair under the top of every full-height pilaster;
- cornice: upside-down stairs one block outside the roof line (overhang + shadow line under the parapet);
- window sills: an upside-down stair under the bottom row of every window, sitting in the recessed bay;
- window hoods: a top slab over windows that have wall above them (lintel shadow).
"""
from __future__ import annotations

import os

import palette

DIRS = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}
AIR = "minecraft:air"


def _variant(block: str | None, kind: str) -> str | None:
    """stairs/slab id for a block, or None if the pack has no such variant (checked against blocklib)."""
    if not block or ":" not in block:
        return None
    base = block.split("[", 1)[0]
    if base.endswith("_" + kind) or (kind == "stairs" and base.endswith("_stairs")):
        return base
    lib = palette._lib()
    for cand in (palette.variant_id(base, kind),
                 # quartz_pillar / smooth_quartz-ish names: try without the trailing word
                 base.rsplit("_", 1)[0] + "_" + kind if "_" in base.split(":", 1)[1] else None):
        if cand and (not lib or cand in lib):
            return cand
    return None


def _stair(K: dict, roles: tuple, facing: str, half: str) -> str | None:
    for r in roles:
        s = _variant(K.get(r), "stairs")
        if s:
            return f"{s}[facing={facing},half={half}]"
    return None


def _slab(K: dict, roles: tuple, typ: str) -> str | None:
    for r in roles:
        s = _variant(K.get(r), "slab")
        if s:
            return f"{s}[type={typ}]"
    return None


def apply(out: dict, K: dict, fp: set, ledge_ring: set, wall_ring: set, H: int, ry: int) -> int:
    """Add depth details to a structure's block dict in place. Returns blocks added."""
    if os.environ.get("ARCHITECT_DEPTH", "1") == "0":
        return 0
    n0 = len(out)
    glass = K.get("glass")
    pillar = K.get("pillar", K.get("trim"))

    def free(x, y, z):
        return out.get((x, y, z)) in (None, AIR)

    def put(x, y, z, b):
        if b and free(x, y, z):
            out[(x, y, z)] = b

    outline = [(x, z) for (x, z) in fp if any((x + a, z + c) not in fp for a, c in DIRS)]
    # 1. base skirt (y=0, outside the footprint) and 2. cornice (y=ry, outside the roof line)
    for (x, z) in outline:
        for (a, c), name in DIRS.items():
            q = (x + a, z + c)
            if q in fp:
                continue
            back = DIRS[(-a, -c)]  # stair back against the building
            put(q[0], 0, q[1], _stair(K, ("base", "trim"), back, "bottom"))
            put(q[0], ry, q[1], _stair(K, ("trim", "base"), back, "top"))
    # 3. pier feet + capitals: full-height pilasters on the outer ring
    for (x, z) in ledge_ring:
        if out.get((x, 2, z)) != pillar or out.get((x, H, z)) != pillar:
            continue
        for (a, c), name in DIRS.items():
            q = (x + a, z + c)
            if q in fp:
                continue
            back = DIRS[(-a, -c)]
            put(q[0], 1, q[1], _stair(K, ("base", "trim"), back, "bottom"))
            put(q[0], H, q[1], _stair(K, ("pillar", "trim"), back, "top"))
    # 4. sills + hoods: windows in the wall ring look out into the recessed bay (outer ring cell, free at that y)
    if glass:
        for (x, y, z), b in list(out.items()):
            if b != glass or (x, z) not in wall_ring or out.get((x, y - 1, z)) == glass:
                continue
            for (a, c) in DIRS:
                q = (x + a, z + c)
                if q not in ledge_ring and q in fp:
                    continue  # that side is the room
                if q in fp and not free(q[0], y, q[1]):
                    continue  # pilaster in front: no bay there
                back = DIRS[(-a, -c)]
                put(q[0], y - 1, q[1], _stair(K, ("trim", "base"), back, "top"))
                top = y
                while out.get((x, top + 1, z)) == glass:
                    top += 1
                if out.get((x, top + 1, z)) not in (None, AIR, glass) and top + 1 < ry:
                    put(q[0], top + 1, q[1], _slab(K, ("trim", "base"), "top"))
    return len(out) - n0
