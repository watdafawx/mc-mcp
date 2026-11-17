"""Shape generators for the architect: the parts that are hard to draw with boxes (round towers, cone and gable
roofs, arches, window rows, battlements, domes). Each returns blocks [[x, y, z, blockstate]] in local coordinates
from the part's own corner (0,0,0) = its min x, bottom y, min z. Air carves.

Stairs facing = the direction you climb (the tall back is on that side), checked against the 1.21.1 models
(knowledge/principles.md). half=top is upside down; its extra block hangs on the facing side.
"""

from __future__ import annotations

import math

OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
DIR = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


class ShapeError(ValueError):
    pass


# ------------------------------------------------------------------------------------------ materials

_NO_PLURAL = {"minecraft:bricks": "minecraft:brick", "minecraft:nether_bricks": "minecraft:nether_brick",
              # blocks with no stairs/slab of their own: use the closest-looking family
              "minecraft:calcite": "minecraft:polished_diorite", "minecraft:white_concrete": "minecraft:smooth_quartz",
              "minecraft:quartz_pillar": "minecraft:quartz", "minecraft:deepslate": "minecraft:cobbled_deepslate",
              "minecraft:smooth_basalt": "minecraft:polished_blackstone", "minecraft:basalt": "minecraft:polished_blackstone",
              "minecraft:polished_basalt": "minecraft:polished_blackstone", "minecraft:obsidian": "minecraft:polished_blackstone",
              "minecraft:dirt": "minecraft:mud_brick", "minecraft:clay": "minecraft:mud_brick",
              "minecraft:terracotta": "minecraft:granite", "minecraft:sea_lantern": "minecraft:prismarine",
              "minecraft:amethyst_block": "minecraft:purpur", "minecraft:iron_block": "minecraft:smooth_stone"}
# Used when a guessed id turns out not to exist (the architect retries once with these).
FALLBACK = {"stairs": "minecraft:stone_brick_stairs", "slab": "minecraft:stone_brick_slab"}


def derive(block: str, kind: str) -> str:
    """Best-guess stairs/slab id for a full block (stone_bricks -> stone_brick_stairs, oak_planks -> oak_stairs,
    quartz_block -> quartz_stairs). ghost_set reports a bad guess; pass stairs=/slab= explicitly to override."""
    base = block.split("[")[0]
    base = _NO_PLURAL.get(base, base)
    ns, name = base.split(":", 1) if ":" in base else ("minecraft", base)
    for suf in ("_planks", "_block"):
        if name.endswith(suf) and name not in ("smooth_quartz_block",):
            name = name[: -len(suf)]
    if name == "smooth_quartz_block":
        name = "smooth_quartz"
    if name.endswith(("bricks", "tiles")):
        name = name[:-1]
    return f"{ns}:{name}_{kind}"


def stairs(mat: str, facing: str, half: str = "bottom", shape: str = "straight") -> str:
    return f"{mat}[facing={facing},half={half},shape={shape}]"


# ------------------------------------------------------------------------------------------ circles

def disk(r: float) -> set[tuple[int, int]]:
    """Cells of a filled circle radius r, centred on (R, R) where R = ceil(r): footprint 0..2R."""
    R = math.ceil(r)
    return {(x, z) for x in range(2 * R + 1) for z in range(2 * R + 1)
            if (x - R) ** 2 + (z - R) ** 2 <= (r + 0.45) ** 2}


def ring(cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """Edge of a 2D shape: cells with any of 8 neighbours outside it, so diagonal steps stay closed."""
    return {(x, z) for (x, z) in cells
            if any((x + dx, z + dz) not in cells for dx in (-1, 0, 1) for dz in (-1, 0, 1))}


# ------------------------------------------------------------------------------------------ generators

def round_tower(r: int = 3, h: int = 12, block: str = "minecraft:stone_bricks", hollow: bool = True,
                floor: str | None = None, floors_every: int = 0, windows: int = 4, window_every: int = 5,
                window: str = "minecraft:glass_pane", crenel: bool = True, crenel_block: str | None = None,
                corbel: bool = True) -> list:
    """Cylinder radius r (footprint 2r+1), height h. Window slits (1x2) at `windows` angles every `window_every`
    layers; battlements on top with a corbel ring (upside-down stairs) under them."""
    if not 1 <= r <= 20 or not 1 <= h <= 200:
        raise ShapeError("round_tower: r 1..20, h 1..200")
    d = disk(r)
    shell = ring(d)
    R = math.ceil(r)
    out = []
    for y in range(h):
        cells = shell if hollow else d
        for (x, z) in cells:
            out.append([x, y, z, block])
        if hollow and floor and (y == 0 or (floors_every and y % floors_every == 0)):
            for (x, z) in d - shell:
                out.append([x, y, z, floor])
    if windows and window_every:
        picks = []
        for i in range(windows):
            a = 2 * math.pi * i / windows + math.pi / 4
            px, pz = R + math.cos(a) * r, R + math.sin(a) * r
            picks.append(min(shell, key=lambda c: (c[0] - px) ** 2 + (c[1] - pz) ** 2))
        for y in range(2, h - 2, window_every):
            for (x, z) in picks:
                out += [[x, y, z, window], [x, y + 1, z, window]]
    if crenel:
        cb = crenel_block or block
        outer = ring(disk(r + 1)) if corbel else shell
        if corbel:  # ring one wider, sitting on upside-down stairs
            st = derive(block, "stairs")
            for (x, z) in outer:
                dx, dz = x + 1 - (R + 1), z + 1 - (R + 1)
                f = ("east" if dx > 0 else "west") if abs(dx) >= abs(dz) else ("south" if dz > 0 else "north")
                out.append([x - 1, h - 1, z - 1, stairs(st, f, "top")])
            for (x, z) in outer:
                out.append([x - 1, h, z - 1, cb])
        else:
            for (x, z) in shell:
                out.append([x, h, z, cb])
        order = sorted(outer, key=lambda c: math.atan2(c[1] - (R + 1 if corbel else R), c[0] - (R + 1 if corbel else R)))
        for i, (x, z) in enumerate(order):
            if i % 2 == 0:
                o = -1 if corbel else 0
                out.append([x + o, h + 1, z + o, cb])
    return out


def cone_roof(r: int = 3, h: int | None = None, block: str = "minecraft:deepslate_tiles", overhang: int = 1,
              tip: str | None = "minecraft:lightning_rod", fill_base: bool = True) -> list:
    """Pointed cone for a round tower of radius r. Footprint 2(r+overhang)+1; place it with `at` shifted by
    -overhang in x and z, on top of the tower. h defaults to 2.2 x radius (steep, fairy-tale)."""
    R0 = r + overhang
    h = h or max(3, round(R0 * 2.2))
    C = math.ceil(R0)
    def layer_cells(y: int) -> set:
        rr = R0 * (1 - y / h)
        if rr < 0.3:
            return {(C, C)}
        Rr = math.ceil(rr)
        return {(x + C - Rr, z + C - Rr) for (x, z) in disk(rr)}

    out = []
    for y in range(h):
        cells = layer_cells(y)
        nxt = layer_cells(y + 1) if y + 1 < h else set()
        # The visible skin: this layer's edge plus the step between it and the smaller layer above (no holes).
        layer = cells if (y == 0 and fill_base) else ring(cells) | (cells - nxt)
        for (x, z) in layer:
            out.append([x, y, z, block])
    if tip:
        out.append([C, h, C, tip])
    return out


def gable_roof(w: int = 9, d: int = 7, axis: str = "x", block: str = "minecraft:deepslate_tiles",
               stair: str | None = None, gable: str | None = None, overhang: int = 1,
               stepped: bool = False, ridge: str | None = None) -> list:
    """Pitched roof over a w (x) by d (z) wall footprint, ridge along `axis`. Stair rows rise from both eaves;
    gable ends are filled with `gable` (default: the roof block). stepped=True makes crow-stepped gables that
    rise above the roof (Dutch/Bavarian). Place `at` = the wall footprint's corner, y = wall top + 1;
    the eaves overhang by `overhang` on every side."""
    st = stair or derive(block, "stairs")
    gb = gable or block
    span = d if axis == "x" else w           # across the slopes
    length = w if axis == "x" else d         # along the ridge
    o = overhang
    out = []
    half = (span + 2 * o) // 2
    for k in range(half + 1):
        a, b = k - o, span - 1 + o - k       # the two slope rows (across-coordinates)
        y = k
        if a > b:
            break
        for t in range(-o, length + o):
            if a == b:
                cells = [(t, a, ridge or derive(block, "slab") + "[type=bottom]")]
            else:
                fa, fb = ("south", "north") if axis == "x" else ("east", "west")
                cells = [(t, a, stairs(st, fa)), (t, b, stairs(st, fb))]
            for (tt, s, state) in cells:
                x, z = (tt, s) if axis == "x" else (s, tt)
                out.append([x, y, z, state])
        # gable fill between the slopes, at both ends of the walls
        for end in (0, length - 1):
            for s in range(max(a + 1, 0), min(b - 1, span - 1) + 1):
                x, z = (end, s) if axis == "x" else (s, end)
                out.append([x, y, z, gb])
    if stepped:
        for end, step_out in ((0, -1), (length - 1, 1)):
            for s in range(span):
                hz = min(s, span - 1 - s)
                top = (hz // 2) * 2 + 2
                for y in range(0, top + 1):
                    for e in (end, end + step_out):
                        x, z = (e, s) if axis == "x" else (s, e)
                        out.append([x, y, z, gb])
    return out


def pyramid_roof(w: int = 7, d: int = 7, block: str = "minecraft:deepslate_tiles", stair: str | None = None,
                 overhang: int = 1, tip: str | None = None) -> list:
    """Hip roof over a w x d footprint: rings of stairs climbing inward, slab/block on top.
    Same placement rule as gable_roof."""
    st = stair or derive(block, "stairs")
    o = overhang
    x0, z0, x1, z1 = -o, -o, w - 1 + o, d - 1 + o
    out, y = [], 0
    while x0 <= x1 and z0 <= z1:
        if x0 == x1 or z0 == z1:
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    out.append([x, y, z, derive(block, "slab") + "[type=bottom]"])
            y += 1
            break
        for x in range(x0, x1 + 1):
            out.append([x, y, z0, stairs(st, "south", shape="straight")])
            out.append([x, y, z1, stairs(st, "north", shape="straight")])
        for z in range(z0 + 1, z1):
            out.append([x0, y, z, stairs(st, "east")])
            out.append([x1, y, z, stairs(st, "west")])
        # corners: outer stairs
        out += [[x0, y, z0, stairs(st, "south", shape="outer_left")], [x1, y, z0, stairs(st, "south", shape="outer_right")],
                [x0, y, z1, stairs(st, "north", shape="outer_right")], [x1, y, z1, stairs(st, "north", shape="outer_left")]]
        x0, z0, x1, z1, y = x0 + 1, z0 + 1, x1 - 1, z1 - 1, y + 1
    if tip:
        out.append([(w - 1) // 2, y, (d - 1) // 2, tip])
    return out


def battlements(w: int = 9, d: int = 9, block: str = "minecraft:stone_bricks", corbel: bool = False,
                every: int = 2) -> list:
    """Merlons on the top edge of a w x d wall footprint (place `at` = corner, y = wall top + 1).
    corbel=True adds an overhanging ring of upside-down stairs one layer down, outside the wall."""
    out = []
    per = [(x, 0) for x in range(w)] + [(w - 1, z) for z in range(1, d)] + \
          [(x, d - 1) for x in range(w - 2, -1, -1)] + [(0, z) for z in range(d - 2, 0, -1)]
    for i, (x, z) in enumerate(per):
        out.append([x, 0, z, block])
        if i % every == 0:
            out.append([x, 1, z, block])
    if corbel:
        st = derive(block, "stairs")
        for x in range(-1, w + 1):
            out += [[x, -1, -1, stairs(st, "north", "top")], [x, -1, d, stairs(st, "south", "top")]]
        for z in range(0, d):
            out += [[-1, -1, z, stairs(st, "west", "top")], [w, -1, z, stairs(st, "east", "top")]]
    return out


def window_row(length: int = 13, along: str = "x", outward: str = "south", count: int | None = None,
               spacing: int = 3, w: int = 1, h: int = 2, glass: str = "minecraft:glass_pane",
               sill: str | None = None, lintel: str | None = None, frame: str | None = None) -> list:
    """Windows cut into an existing wall plane. The wall runs `along` x or z for `length` blocks from `at`;
    `outward` is the side facing outside (sill/lintel go there). Windows are w x h, `spacing` blocks apart
    (gap between windows), centred along the wall. sill/lintel: a stairs id (e.g. minecraft:stone_brick_stairs)."""
    pitch = w + spacing
    n = count or max(1, (length - spacing) // pitch)
    total = n * w + (n - 1) * spacing
    start = (length - total) // 2
    ox, oz = DIR[outward]
    out = []
    for i in range(n):
        s0 = start + i * pitch
        for s in range(s0, s0 + w):
            x, z = (s, 0) if along == "x" else (0, s)
            for y in range(h):
                out.append([x, y, z, glass])
            if sill:
                out.append([x + ox, -1, z + oz, stairs(sill, OPP[outward])])
            if lintel:
                out.append([x + ox, h, z + oz, stairs(lintel, outward, "top")])
        if frame:
            for s in (s0 - 1, s0 + w):
                x, z = (s, 0) if along == "x" else (0, s)
                for y in range(-1, h + 1):
                    out.append([x + ox, y, z + oz, frame])
    return out


def arch(w: int = 3, h: int = 4, along: str = "x", depth: int = 1, block: str = "minecraft:stone_bricks",
         stair: str | None = None, frame: bool = True) -> list:
    """Arched opening cut through a wall: air w x h with upside-down stairs in the top corners (S9 in the
    principles). `at` = the opening's bottom-left in the wall plane; depth = wall thickness (into +z or +x).
    frame=True adds 1-block pillars and a keystone row around it, proud by nothing (same plane)."""
    st = stair or derive(block, "stairs")
    out = []
    for dd in range(depth):
        for s in range(w):
            for y in range(h):
                corner = y == h - 1 and w >= 3 and s in (0, w - 1)
                x, z = (s, dd) if along == "x" else (dd, s)
                if corner:
                    f = ("west" if s == 0 else "east") if along == "x" else ("north" if s == 0 else "south")
                    out.append([x, y, z, stairs(st, f, "top")])
                else:
                    out.append([x, y, z, "minecraft:air"])
        if frame:
            for s in (-1, w):
                for y in range(h + 1):
                    x, z = (s, dd) if along == "x" else (dd, s)
                    out.append([x, y, z, block])
            for s in range(w):
                x, z = (s, dd) if along == "x" else (dd, s)
                out.append([x, h, z, block])
    return out


def dome(r: int = 5, block: str = "minecraft:smooth_quartz", hollow: bool = True, tip: str | None = None) -> list:
    """Half sphere radius r, footprint 2r+1. Place `at` = corner, y = top of the walls it sits on."""
    out = []
    C = r
    for y in range(r + 1):
        for x in range(2 * r + 1):
            for z in range(2 * r + 1):
                dd = (x - C) ** 2 + y ** 2 + (z - C) ** 2
                if dd <= (r + 0.45) ** 2 and (not hollow or dd >= (r - 0.55) ** 2):
                    out.append([x, y, z, block])
    if tip:
        out.append([C, r + 1, C, tip])
    return out


def pillar_row(count: int = 4, spacing: int = 4, h: int = 6, along: str = "x", block: str = "minecraft:quartz_pillar",
               base: str | None = None, cap: str | None = None, size: int = 1) -> list:
    """Free-standing pillars every `spacing` blocks (centre to centre). size 1 or 2 (2x2).
    base/cap: blocks for the bottom and top layer (e.g. a slab or chiseled block)."""
    out = []
    for i in range(count):
        s0 = i * spacing
        for a in range(size):
            for b in range(size):
                x, z = (s0 + a, b) if along == "x" else (b, s0 + a)
                for y in range(h):
                    st = base if (y == 0 and base) else cap if (y == h - 1 and cap) else block
                    out.append([x, y, z, st])
    return out


KINDS = {
    "round_tower": round_tower, "cone_roof": cone_roof, "gable_roof": gable_roof, "pyramid_roof": pyramid_roof,
    "battlements": battlements, "window_row": window_row, "arch": arch, "dome": dome, "pillar_row": pillar_row,
}


import massing  # noqa: E402  (styled volumes; imports disk/ShapeError from here)

KINDS.update(massing.KINDS)


def build(parts: list[dict]) -> tuple[list, list]:
    """parts: [{kind, at:[x,y,z], ...opts}] -> (blocks with `at` applied, per-part summary)."""
    blocks, summary = [], []
    for i, p in enumerate(parts):
        p = dict(p)
        kind = p.pop("kind", None)
        at = p.pop("at", [0, 0, 0])
        if kind not in KINDS:
            raise ShapeError(f"part {i}: unknown kind {kind}; one of {sorted(KINDS)}")
        try:
            got = KINDS[kind](**p)
        except TypeError as e:
            raise ShapeError(f"part {i} ({kind}): {e}") from None
        ax, ay, az = at
        blocks += [[x + ax, y + ay, z + az, s] for (x, y, z, s) in got]
        if got:
            mn = [min(b[j] for b in got) + at[j] for j in range(3)]
            mx = [max(b[j] for b in got) + at[j] for j in range(3)]
            summary.append({"kind": kind, "blocks": len(got), "min": mn, "max": mx})
    return blocks, summary
