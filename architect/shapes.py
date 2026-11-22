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


def rect_perimeter(w: int, d: int, ox: int = 0, oz: int = 0) -> list:
    """Perimeter of a w x d rect (min corner at ox, oz) in walk order, no duplicates on 1-wide sides."""
    walk = ([(x, 0) for x in range(w)] + [(w - 1, z) for z in range(1, d)] +
            [(x, d - 1) for x in range(w - 2, -1, -1)] + [(0, z) for z in range(d - 2, 0, -1)])
    out, seen = [], set()
    for (x, z) in walk:
        c = (x + ox, z + oz)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def out_dir(x: int, z: int, w: int, d: int) -> str:
    """Outward face direction for a cell of a w x d rect's ring (or the ring drawn just outside it)."""
    if z < 0:
        return "north"
    if z >= d:
        return "south"
    if x < 0:
        return "west"
    if x >= w:
        return "east"
    return "north"


def sibling(state: str, kind: str) -> str:
    """The same family's stairs/slab id: minecraft:deepslate_tile_stairs -> minecraft:deepslate_tile_slab."""
    base = state.split("[")[0]
    for suf in ("_stairs", "_slab"):
        if base.endswith(suf):
            return base[: -len(suf)] + "_" + kind
    return derive(base, kind)


def remap_facing(state: str, fmap: dict[str, str]) -> str:
    """Rewrite a stair's facing= through fmap (used when a part is rotated/mirrored onto another face)."""
    if "facing=" not in state:
        return state
    head, _, rest = state.partition("[")
    props = []
    for kv in rest.rstrip("]").split(","):
        k, _, v = kv.partition("=")
        props.append(f"{k}={fmap.get(v, v)}" if k == "facing" else f"{k}={v}")
    return f"{head}[{','.join(props)}]"


def radial_run(x: int, z: int, cx: int, cz: int) -> list:
    """Cells on the straight line from just off (cx, cz) out to (x, z): a stair tread reaching out to radius r."""
    n = max(abs(x - cx), abs(z - cz))
    return [(cx + round((x - cx) * k / n), cz + round((z - cz) * k / n)) for k in range(1, n + 1)]


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
        # Crow-steps: one level per tread, and each step's top block becomes an upside-down stair facing outward, so
        # the riser meets the tread on a chamfer instead of a hard 2-block jag. The apex lands on the ridge height.
        for end, step_out in ((0, -1), (length - 1, 1)):
            # the gable end walls are at the ridge's ends, so the steps protrude along the ridge axis
            outward = ("west" if step_out < 0 else "east") if axis == "x" else ("north" if step_out < 0 else "south")
            for s in range(span):
                top = min(s, span - 1 - s) + 1
                for y in range(top + 1):
                    x, z = (end, s) if axis == "x" else (s, end)
                    ox, oz = (end + step_out, s) if axis == "x" else (s, end + step_out)
                    out.append([x, y, z, gb])
                    out.append([ox, y, oz, stairs(st, outward, "top") if y == top else gb])
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
    """Half sphere radius r, footprint 2r+1. Place `at` = corner, y = top of the walls it sits on.
    Small domes (r <= 5) cut the shallow crown/shoulder cells (and the hollow inner skin) with bottom/top slabs,
    so the silhouette and the rim read as a curve instead of a stack of full blocks."""
    if not 1 <= r <= 40:
        raise ShapeError("dome: r 1..40")
    out, C = [], r
    if r > 5:  # big domes: full blocks, the curvature already reads at this scale
        for y in range(r + 1):
            for x in range(2 * r + 1):
                for z in range(2 * r + 1):
                    dd = (x - C) ** 2 + y ** 2 + (z - C) ** 2
                    if dd <= (r + 0.45) ** 2 and (not hollow or dd >= (r - 0.55) ** 2):
                        out.append([x, y, z, block])
        if tip:
            out.append([C, r + 1, C, tip])
        return out
    sb = sibling(block, "slab") + "[type=bottom]"
    stop = sibling(block, "slab") + "[type=top]"
    ro, ri = r + 0.45, r - 0.55
    for y in range(r + 1):
        y0, y1 = y, y + 1
        for x in range(2 * r + 1):
            for z in range(2 * r + 1):
                d2 = (x - C) ** 2 + (z - C) ** 2
                if d2 > ro * ro:
                    continue
                hi = math.sqrt(ro * ro - d2)                              # outer surface height in this column
                lo = math.sqrt(max(0.0, ri * ri - d2)) if hollow else 0.0  # where the hollow starts
                if y1 <= lo or y0 >= hi:
                    continue
                if y0 >= lo and y1 <= hi:
                    out.append([x, y, z, block])                          # a full block inside the shell
                elif y1 <= hi:                                            # cut at the bottom: hollow skin
                    out.append([x, y, z, stop if lo - y0 <= 0.5 else sb])
                else:                                                     # cut at the top: shallow crown
                    out.append([x, y, z, sb if hi - y0 <= 0.75 else block])
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


# ------------------------------------------------------------------------------------------ fortifications

def square_tower(w: int = 5, d: int = 5, h: int = 14, block: str = "minecraft:stone_bricks", hollow: bool = True,
                 floor: str | None = None, floors_every: int = 0, windows: bool = True, window_every: int = 4,
                 window: str = "minecraft:glass_pane", machicolations: bool = True, crenel: bool = True,
                 crenel_block: str | None = None) -> list:
    """Rectangular tower: w x d footprint, shaft y 0..h-1. Hollow shell with optional floors, slit windows on all
    four faces. machicolations = a corbelled overhang one block proud (upside-down stairs under it) with one drop
    opening in the middle of each side; merlons go on top (y=h, or y=h+1 over an overhang)."""
    if not 3 <= w <= 40 or not 3 <= d <= 40 or not 2 <= h <= 200:
        raise ShapeError("square_tower: w, d 3..40, h 2..200")
    if floors_every and floors_every < 2:
        raise ShapeError("square_tower: floors_every 0 or >= 2")
    per = rect_perimeter(w, d)
    per_set = set(per)
    cells: dict[tuple[int, int, int], str] = {}
    inner = [(x, z) for x in range(w) for z in range(d) if (x, z) not in per_set]
    full = [(x, z) for x in range(w) for z in range(d)]
    for y in range(h):
        for (x, z) in (per if hollow else full):
            cells[(x, y, z)] = block
        if hollow and floor and (y == 0 or (floors_every and y % floors_every == 0)):
            for (x, z) in inner:
                cells[(x, y, z)] = floor
    if windows and window_every:
        mid_x = [w // 2] if w % 2 else [w // 2 - 1, w // 2]
        mid_z = [d // 2] if d % 2 else [d // 2 - 1, d // 2]
        cuts = ([(x, 0) for x in mid_x] + [(x, d - 1) for x in mid_x] +
                [(0, z) for z in mid_z] + [(w - 1, z) for z in mid_z])
        for y in range(3, h - 1, window_every):
            for (x, z) in cuts:
                cells[(x, y, z)] = window
                cells[(x, y + 1, z)] = window
    cb = crenel_block or block
    ring_out = rect_perimeter(w + 2, d + 2, -1, -1)
    if machicolations:
        st = derive(block, "stairs")
        for (x, z) in ring_out:   # corbel: upside-down stairs, struts facing out
            cells[(x, h - 1, z)] = stairs(st, out_dir(x, z, w, d), "top")
        drops = {(w // 2, -1), (w // 2, d), (-1, d // 2), (w, d // 2)}   # 1-block drop openings
        for (x, z) in ring_out:
            if (x, z) not in drops:
                cells[(x, h, z)] = cb
        if crenel:
            for i, (x, z) in enumerate(ring_out):
                if i % 2 == 0:
                    cells[(x, h + 1, z)] = cb
    elif crenel:
        for (x, z) in per:
            cells[(x, h, z)] = cb
        for i, (x, z) in enumerate(per):
            if i % 2 == 0:
                cells[(x, h + 1, z)] = cb
    return [[x, y, z, b] for (x, y, z), b in cells.items()]


def dormer(w: int = 3, h: int = 4, depth: int = 4, facing: str = "south", wall: str = "minecraft:stone_bricks",
           roof: str = "minecraft:deepslate_tile_stairs", window: str = "minecraft:glass_pane") -> list:
    """Roof dormer: a box w wide, h high, `depth` deep, projecting out of the roof on `facing`. Recessed front
    window (glass 1 behind the wall plane, proud sill and jambs) and a pitched gable rooflet above with the ridge
    running along the projection. `at` = its back-bottom corner; the rooflet overhangs 1 to each side."""
    if not 3 <= w <= 15 or not 3 <= h <= 12 or not 2 <= depth <= 12:
        raise ShapeError("dormer: w 3..15, h 3..12, depth 2..12")
    if facing not in DIR:
        raise ShapeError(f"dormer: facing north|south|east|west, not {facing!r}")
    rst = roof if roof.split("[")[0].endswith("_stairs") else derive(roof, "stairs")
    ridge = sibling(rst, "slab") + "[type=bottom]"
    sill = sibling(rst, "slab") + "[type=top]"
    cells: dict[tuple[int, int, int], str] = {}
    fx = depth - 1                                   # front wall plane (local +z = the way it looks out)
    win = max(1, w - 2)
    x0 = (w - win) // 2
    wh = 2 if h >= 5 else 1
    for x in range(w):
        for z in range(depth):
            cells[(x, 0, z)] = wall                  # floor pan: it sits on the main roof
    for y in range(1, h):
        for z in range(depth):
            cells[(0, y, z)] = wall
            cells[(w - 1, y, z)] = wall
        for x in range(w):
            cells[(x, y, fx)] = wall
    for x in range(x0, x0 + win):
        for y in range(1, 1 + wh):
            del cells[(x, y, fx)]                    # the opening
            cells[(x, y, fx - 1)] = window           # glass set back one (D2: never in the wall plane)
        cells[(x, 0, fx + 1)] = sill                 # proud sill under the opening
    for x in (x0 - 1, x0 + win):                     # proud jambs framing the window
        if 0 <= x < w:
            for y in range(1 + wh):
                cells[(x, y, fx + 1)] = wall
    k = 0
    while True:                                      # rooflet: stairs climbing from both sides to a slab ridge
        a, b = k - 1, w - k
        if a > b:
            break
        y = h + k
        for z in range(depth + 1):
            if a == b:
                cells[(a, y, z)] = ridge
            else:
                cells[(a, y, z)] = stairs(rst, "east")
                cells[(b, y, z)] = stairs(rst, "west")
        for x in range(a + 1, b):                    # gable face at the front wall plane
            cells[(x, y, depth - 1)] = wall
        k += 1
    # orient: canonical box = width along x, projection along +z (south). Stair facings rotate with it.
    if facing == "south":
        return [[x, y, z, b] for (x, y, z), b in cells.items()]
    fmap = {"north": {"north": "south", "south": "north", "east": "east", "west": "west"},
            "east": {"south": "east", "north": "west", "east": "south", "west": "north"},
            "west": {"south": "west", "north": "east", "east": "south", "west": "north"}}[facing]
    out = []
    for (x, y, z), b in cells.items():
        if facing == "north":
            nx, nz = x, depth - 1 - z
        elif facing == "east":
            nx, nz = z, x
        else:
            nx, nz = depth - 1 - z, x
        out.append([nx, y, nz, remap_facing(b, fmap)])
    return out


def buttress_row(length: int = 15, h: int = 9, depth: int = 3, spacing: int = 4, axis: str = "x",
                 side: str = "south", block: str = "minecraft:stone_bricks", cap_stairs: str | None = None) -> list:
    """Stepped exterior buttresses along a wall plane at across=0, one every `spacing` blocks: full height against
    the wall, losing a step for every `depth` block they reach out, each step topped with a stair whose slope climbs
    back toward the wall. `side` is the way they project (the wall is at across 0, so north/west give negative cells)."""
    if not 1 <= length <= 200 or not 1 <= h <= 100 or not 1 <= depth <= 8:
        raise ShapeError("buttress_row: length 1..200, h 1..100, depth 1..8")
    if axis not in ("x", "z"):
        raise ShapeError(f"buttress_row: axis x|z, not {axis!r}")
    need = ("north", "south") if axis == "x" else ("east", "west")
    if side not in need:
        raise ShapeError(f"buttress_row: with axis={axis} side is one of {need}, not {side!r}")
    spacing = max(1, spacing)
    st = cap_stairs or derive(block, "stairs")
    step_h = max(1, h // (depth + 1))
    cells: dict[tuple[int, int, int], str] = {}

    def put(pos: int, y: int, out: int, b: str) -> None:
        cells[(pos, y, out) if axis == "x" else (out, y, pos)] = b

    o = 1 if side in ("south", "east") else -1
    for pos in range(0, length, spacing):
        for dd in range(1, depth + 1):
            top = h - (dd - 1) * step_h
            if top < 1:
                break
            for y in range(top):
                put(pos, y, dd * o, block)
            put(pos, top - 1, dd * o, stairs(st, OPP[side]))   # sloped cap: climbs back toward the wall
    return [[x, y, z, b] for (x, y, z), b in cells.items()]


def spiral_stair(r: int = 2, h: int = 10, block: str = "minecraft:stone_bricks", stair_block: str | None = None,
                 pillar: str | None = None, clockwise: bool = True) -> list:
    """Helical stair around a central pillar, footprint 2r+1 (centre at r, r), rising to h. Treads reach from the
    pillar out to radius r, rise 1 every 2 treads (a 0.5 step per block, so it walks) and are 2 blocks thick
    underneath; a turn gains r*4-ish blocks of headroom."""
    if not 1 <= r <= 12 or not 1 <= h <= 100:
        raise ShapeError("spiral_stair: r 1..12, h 1..100")
    R = math.ceil(r)
    st = stair_block or derive(block, "stairs")
    order = sorted(ring(disk(r)), key=lambda c: math.atan2(c[1] - R, c[0] - R))
    if clockwise:
        order.reverse()
    n, per_rise = len(order), 2
    cells: dict[tuple[int, int, int], str] = {}
    for i in range(n * (h + 1)):
        lvl = i // per_rise
        if lvl >= h:
            break
        idx = i % n
        (x, z) = order[idx]
        for (cx, cz) in radial_run(x, z, R, R):
            if lvl:
                cells.setdefault((cx, lvl - 1, cz), block)   # solid flight, not floating treads
            cells.setdefault((cx, lvl, cz), block)
        if i % per_rise == 0 and i:                          # first tread of a level: the step up
            nx, nz = order[(idx + 1) % n]
            f = ("east" if nx > x else "west") if abs(nx - x) >= abs(nz - z) else ("south" if nz > z else "north")
            cells[(x, lvl, z)] = stairs(st, f)
    for y in range(h + 1):
        cells[(R, y, R)] = pillar or block
    return [[x, y, z, b] for (x, y, z), b in cells.items()]


def wall_segment(length: int = 15, h: int = 7, thickness: int = 3, axis: str = "x", block: str = "minecraft:stone_bricks",
                 walkway: str | None = None, crenel: bool = True, crenel_side: str = "both") -> list:
    """Curtain wall: `length` long, h high, `thickness` thick. thickness >= 3 gives a parapet walkway on top (body
    up to y=h-2, walkway floor and parapet base at y=h-1, merlons at y=h); thinner walls are solid with merlons on
    the top. crenel_side: both | near | far (near = the across-0 face) or an explicit face name."""
    if not 1 <= length <= 400 or not 2 <= h <= 60 or not 1 <= thickness <= 15:
        raise ShapeError("wall_segment: length 1..400, h 2..60, thickness 1..15")
    if axis not in ("x", "z"):
        raise ShapeError(f"wall_segment: axis x|z, not {axis!r}")
    faces = ("north", "south") if axis == "x" else ("west", "east")
    if crenel_side == "both":
        want = set(faces)
    elif crenel_side == "near":
        want = {faces[0]}
    elif crenel_side == "far":
        want = {faces[1]}
    elif crenel_side in faces:
        want = {crenel_side}
    else:
        raise ShapeError(f"wall_segment: crenel_side both|near|far|{faces[0]}|{faces[1]}, not {crenel_side!r}")
    walk = thickness >= 3
    wk = walkway or block
    cells: dict[tuple[int, int, int], str] = {}

    def put(i: int, y: int, j: int, b: str) -> None:
        cells[(i, y, j) if axis == "x" else (j, y, i)] = b

    for i in range(length):
        for j in range(thickness):
            for y in range(h - 1 if walk else h):
                put(i, y, j, block)
        if walk:
            for j in range(thickness):
                put(i, h - 1, j, wk if 0 < j < thickness - 1 else block)
        if crenel and i % 2 == 0:
            if walk:   # merlons only on the chosen parapet side(s)
                for j in (0, thickness - 1):
                    if (faces[0] if j == 0 else faces[1]) in want:
                        put(i, h, j, block)
            else:
                for j in range(thickness):
                    put(i, h, j, block)
    return [[x, y, z, b] for (x, y, z), b in cells.items()]


# ------------------------------------------------------------------------------------------ bridge + dispatch

def arch_bridge(length: int = 15, width: int = 5, arch_rise: int = 3, axis: str = "x",
                deck: str = "minecraft:stone_brick_slab[type=top]", arch_block: str = "minecraft:stone_bricks",
                rail: str | None = "minecraft:stone_brick_wall", lanterns: bool = True) -> list:
    """Arched bridge over a span: flat deck along `axis` at y=0, an elliptical arch under it (deepest at the middle,
    solid abutments at both ends, intrados chamfered with upside-down stairs), side railings and lanterns on the ends
    and the crown. `at` = the deck's corner; with the default top-slab deck the walk surface is y=1."""
    if not 5 <= length <= 200 or not 3 <= width <= 31 or not 1 <= arch_rise <= max(1, length // 2):
        raise ShapeError("arch_bridge: length 5..200, width 3..31, arch_rise 1..length/2")
    if axis not in ("x", "z"):
        raise ShapeError(f"arch_bridge: axis x|z, not {axis!r}")
    st = derive(arch_block, "stairs")
    mid = (length - 1) / 2
    A, B = max(1.0, mid), float(arch_rise)
    cells: dict[tuple[int, int, int], str] = {}

    def put(i: int, y: int, j: int, b: str) -> None:
        cells[(i, y, j) if axis == "x" else (j, y, i)] = b

    low: dict[int, set] = {}
    for i in range(length):
        u = (i - mid) / A
        for y in range(-(arch_rise + 1), 1):
            v = (y + 0.5) / B
            if y <= -1 and u * u + v * v <= 1.0:
                continue                                   # inside the arch opening
            low.setdefault(i, set()).add(y)
            for j in range(width):
                put(i, y, j, deck if y == 0 else arch_block)
    for i in range(length):                                # chamfer the intrados where the arch springs
        for y in low[i]:
            if y not in low.get(i + 1, low[i]):
                f = "east" if axis == "x" else "south"
            elif y not in low.get(i - 1, low[i]):
                f = "west" if axis == "x" else "north"
            else:
                continue
            for j in range(width):
                put(i, y, j, stairs(st, f, "top"))
    if rail:
        for i in range(length):
            for j in (0, width - 1):
                put(i, 1, j, rail)
    if lanterns and rail:
        for i in (0, int(mid), length - 1):
            for j in (0, width - 1):
                put(i, 2, j, "minecraft:lantern")
    return [[x, y, z, b] for (x, y, z), b in cells.items()]


KINDS = {
    "round_tower": round_tower, "cone_roof": cone_roof, "gable_roof": gable_roof, "pyramid_roof": pyramid_roof,
    "battlements": battlements, "window_row": window_row, "arch": arch, "dome": dome, "pillar_row": pillar_row,
    "square_tower": square_tower, "dormer": dormer, "buttress_row": buttress_row, "spiral_stair": spiral_stair,
    "wall_segment": wall_segment, "arch_bridge": arch_bridge,
}


import massing  # noqa: E402  (styled volumes; imports disk/ShapeError from here)

KINDS.update(massing.KINDS)
_styled_bridge = KINDS["bridge"]


def bridge(**kw) -> list:
    """Arched stone bridge (see arch_bridge) — or the styled glass sky-bridge of massing when its args (kit, roles,
    along, height, glass_roof) are used. Dispatches on the arguments, so both forms stay available."""
    if {"kit", "roles", "along", "height", "glass_roof"} & set(kw):
        return _styled_bridge(**kw)
    return arch_bridge(**kw)


bridge.__doc__ += " Args of arch_bridge: length, width, arch_rise, axis, deck, arch_block, rail, lanterns."
KINDS["bridge"] = bridge

HELP = """Classic parts: each is {kind, at:[x, y, z], ...options}; local coords from the part's own min corner
(at = that corner), air carves. Stairs/slabs are derived from `block` unless you pass a stair id.
  round_tower    r, h, block, hollow, floor, floors_every, windows, window_every, window, crenel, crenel_block, corbel
  square_tower   w, d, h, block, hollow, floor, floors_every, windows, window_every, window, machicolations, crenel,
                 crenel_block
  cone_roof      r, h, block, overhang, tip, fill_base
  gable_roof     w, d, axis, block, stair, gable, overhang, stepped, ridge
  pyramid_roof   w, d, block, stair, overhang, tip
  dome           r, block, hollow, tip
  battlements    w, d, block, corbel, every
  window_row     length, along, outward, count, spacing, w, h, glass, sill, lintel, frame
  arch           w, h, along, depth, block, stair, frame
  pillar_row     count, spacing, h, along, block, base, cap, size
  dormer         w, h, depth, facing, wall, roof, window
  buttress_row   length, h, depth, spacing, axis, side, block, cap_stairs
  spiral_stair   r, h, block, stair_block, pillar, clockwise
  bridge         length, width, arch_rise, axis, deck, arch_block, rail, lanterns  (alias arch_bridge; kit/along/
                 height/glass_roof = the styled sky-bridge)
  wall_segment   length, h, thickness, axis, block, walkway, crenel, crenel_side
Styled volumes: structure, platform, bridge (kit=...), slope, spire."""


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
