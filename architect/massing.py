"""Styled building volumes for the architect: the part that turns "a couple of boxes" into architecture.

One facade engine works on any 2D footprint (rect, octagon, round, ring sector, L). It gives every volume what good
builds have: a plinth, a ledge at every floor line (shadow lines), recessed window bands with mullions, corner
pillars, an accent stripe, glow bands, a parapet with a rail, a roof deck with vents and antennas, and real floors
inside (so cutaways show rooms). A style KIT maps roles (wall, trim, accent, glass, glow, ...) to blocks, so a whole
base stays in one palette.

Every generator returns [[x, y, z, blockstate]] in local coordinates from the part's min corner, y=0 = plinth.
"""
from __future__ import annotations

import math
import random

from shapes import ShapeError, disk

# ------------------------------------------------------------------------------------------ style kits
# Roles: base (plinth, ground), wall, wall2 (second wall tone / interior floor), trim (ledges, pillars, frames),
# pillar (corner piers, default trim), accent (one bold stripe), glass, glow (light bands), rail, roof (deck), detail (vents, units), antenna, tip.
KITS: dict[str, dict[str, str]] = {
    # Every block here is survival-cheap in ATM10 (<= ~3 cobble units per block, see blocklib.py); no gold, sea lanterns,
    # prismarine or froglights in bulk. Mod blocks: chipped / rechiseled / chisel (free chisel variants), xtonesreworked,
    # luminax (cheap coloured glow cubes), create, connectedglass, mcwfences.
    "station_white": {  # white/grey station with orange-red stripe (space station, sausbuilds lab)
        "base": "minecraft:smooth_quartz", "wall": "minecraft:white_concrete", "wall2": "chisel:large_tile/white_concrete",
        "trim": "minecraft:light_gray_concrete", "accent": "minecraft:orange_concrete", "glass": "connectedglass:borderless_glass_light_blue",
        "glow": "luminax:white_luminax_block", "rail": "minecraft:iron_bars", "roof": "minecraft:white_concrete",
        "detail": "create:industrial_iron_block", "antenna": "minecraft:iron_bars", "tip": "luminax:red_luminax_block"},
    "cyber_dark": {  # dark tech with cyan glow (cyberpunk shop, data core)
        "base": "minecraft:polished_deepslate", "wall": "minecraft:deepslate_tiles", "wall2": "minecraft:polished_blackstone",
        "trim": "minecraft:smooth_basalt", "accent": "minecraft:cyan_concrete", "glass": "connectedglass:borderless_glass_cyan",
        "glow": "luminax:cyan_luminax_block", "rail": "minecraft:iron_bars", "roof": "minecraft:polished_deepslate",
        "detail": "create:industrial_iron_block", "antenna": "minecraft:iron_bars", "tip": "luminax:red_luminax_block"},
    "ae_sky": {  # AE2 house style: sky stone, quartz glass, fluix purple glow
        "base": "ae2:smooth_sky_stone_block", "wall": "ae2:sky_stone_brick", "wall2": "ae2:smooth_sky_stone_block",
        "trim": "ae2:sky_stone_block", "accent": "luminax:purple_luminax_block", "glass": "ae2:quartz_glass",
        "glow": "luminax:purple_luminax_block", "rail": "minecraft:iron_bars", "roof": "ae2:smooth_sky_stone_block",
        "detail": "create:industrial_iron_block", "antenna": "minecraft:iron_bars", "tip": "luminax:purple_luminax_block"},
    "hextech": {  # Arcane/Piltover: cream panelled stone, gold piers, greek-key blue band, teal roofs, hextech-blue glow
        "base": "minecraft:smooth_sandstone", "wall": "chipped:smooth_inlayed_sandstone", "wall2": "chipped:rounded_sandstone_bricks",
        "trim": "rechiseled:bone_block_decorated_bordered", "pillar": "xtonesreworked:sols_block_0",
        "accent": "xtonesreworked:azur_block_2", "glass": "connectedglass:borderless_glass_light_blue",
        "glow": "luminax:light_blue_luminax_block", "rail": "mcwfences:railing_sandstone_wall", "roof": "xtonesreworked:zane_block_5",
        "detail": "xtonesreworked:sols_block_10", "antenna": "minecraft:lightning_rod", "tip": "minecraft:end_rod"},
    "steampunk": {  # dark brick, copper, brass casing, spruce, warm light
        "base": "minecraft:polished_blackstone_bricks", "wall": "minecraft:deepslate_bricks", "wall2": "minecraft:spruce_planks",
        "trim": "minecraft:cut_copper", "accent": "minecraft:exposed_cut_copper", "glass": "connectedglass:borderless_glass_orange",
        "glow": "minecraft:shroomlight", "rail": "minecraft:spruce_fence", "roof": "minecraft:deepslate_tiles",
        "detail": "create:andesite_casing", "antenna": "minecraft:lightning_rod", "tip": "minecraft:lantern"},
    "gothic": {  # deepslate, blackstone, purple glass, violet glow
        "base": "minecraft:polished_blackstone_bricks", "wall": "minecraft:deepslate_bricks", "wall2": "minecraft:deepslate_tiles",
        "trim": "minecraft:stone_bricks", "pillar": "minecraft:polished_deepslate", "accent": "chisel:ornate/purpur", "glass": "connectedglass:borderless_glass_purple",
        "glow": "luminax:purple_luminax_block", "rail": "minecraft:polished_blackstone_wall", "roof": "minecraft:deepslate_tiles",
        "detail": "minecraft:chiseled_deepslate", "antenna": "minecraft:chain", "tip": "minecraft:soul_lantern"},
    "solarpunk": {  # warm white limestone, moss, wood, lots of glass, green roofs
        "base": "minecraft:mossy_stone_bricks", "wall": "create:polished_cut_limestone", "wall2": "minecraft:birch_planks",
        "trim": "create:cut_limestone_bricks", "pillar": "create:limestone_pillar", "accent": "minecraft:moss_block", "glass": "connectedglass:borderless_glass",
        "glow": "minecraft:shroomlight", "band": "minecraft:green_terracotta", "rail": "minecraft:oak_fence", "roof": "minecraft:moss_block",
        "detail": "minecraft:oak_leaves[persistent=true]", "antenna": "minecraft:lightning_rod", "tip": "minecraft:lantern"},
    "rust_industrial": {  # teal concrete, rusty copper, iron (sea platform)
        "base": "minecraft:gray_concrete", "wall": "minecraft:cyan_terracotta", "wall2": "minecraft:light_gray_concrete",
        "trim": "minecraft:weathered_cut_copper", "accent": "minecraft:orange_terracotta", "glass": "connectedglass:borderless_glass_gray",
        "glow": "luminax:orange_luminax_block", "rail": "minecraft:iron_bars", "roof": "minecraft:gray_concrete",
        "detail": "create:andesite_casing", "antenna": "minecraft:iron_bars", "tip": "luminax:red_luminax_block"},
}


# v7 contrast: cheap structural stone, bright metal accents, warm gothic windows.
KITS["steampunk"].update(pillar="minecraft:polished_deepslate", glass="minecraft:cyan_stained_glass",
    dome_rib="minecraft:deepslate_tiles", wall2="minecraft:polished_deepslate")
KITS["gothic"].update(glow="minecraft:shroomlight", glass="minecraft:orange_stained_glass", tip="minecraft:lantern",
    ridge="minecraft:polished_deepslate")
# v10 hextech: Arcane/Piltover, less yellow. Quartz + polished blackstone body, purple glass, cyan glow, brass only as small accents.
KITS["hextech"].update(base="minecraft:polished_blackstone_bricks", wall="minecraft:quartz_bricks", wall2="minecraft:polished_blackstone",
    trim="minecraft:smooth_quartz", pillar="minecraft:quartz_pillar", accent="minecraft:purple_concrete",
    glass="minecraft:purple_stained_glass", glow="luminax:light_blue_luminax_block", roof="minecraft:deepslate_tiles",
    detail="create:brass_casing", rail="minecraft:iron_bars", antenna="minecraft:lightning_rod", tip="minecraft:amethyst_block",
    dome_rib="minecraft:chiseled_polished_blackstone")

# Default roof shape per kit when a structure doesn't pass roof=.
ROOF_DEFAULT = {"hextech": "mansard", "gothic": "mansard", "steampunk": "mansard"}


def _kit(k: str | dict | None, overrides: dict | None = None) -> dict[str, str]:
    if isinstance(k, dict):
        base = dict(KITS["station_white"])
        base.update(k)
    else:
        if (k or "station_white") not in KITS:
            raise ShapeError(f"unknown kit {k}; one of {sorted(KITS)} or a dict of roles")
        base = dict(KITS[k or "station_white"])
    base.update(overrides or {})
    return base


# ------------------------------------------------------------------------------------------ footprints

def fp_rect(w: int, d: int) -> set[tuple[int, int]]:
    return {(x, z) for x in range(w) for z in range(d)}


def fp_octagon(w: int, d: int, c: int | None = None) -> set[tuple[int, int]]:
    c = max(1, min(w, d) // 4) if c is None else c
    return {(x, z) for x in range(w) for z in range(d)
            if min(x, w - 1 - x) + min(z, d - 1 - z) >= c}


def fp_round(r: int) -> set[tuple[int, int]]:
    return disk(r)


def fp_ring(r: int, r_in: int, a0: float = 0, a1: float = 360) -> set[tuple[int, int]]:
    """Annulus sector: angles in degrees, 0 = +x (east), 90 = +z (south)."""
    R = r
    out = set()
    span = (a1 - a0) % 360 or 360
    for x in range(2 * R + 1):
        for z in range(2 * R + 1):
            dx, dz = x - R, z - R
            dd = math.hypot(dx, dz)
            if not (r_in - 0.45 <= dd <= r + 0.45):
                continue
            ang = math.degrees(math.atan2(dz, dx)) % 360
            if (ang - a0) % 360 <= span:
                out.add((x, z))
    if not out:
        raise ShapeError("empty ring footprint")
    mx, mz = min(c[0] for c in out), min(c[1] for c in out)
    return {(x - mx, z - mz) for x, z in out}


def fp_l(w: int, d: int, cut_w: int, cut_d: int) -> set[tuple[int, int]]:
    """L shape: a w x d rect with the +x/+z corner (cut_w x cut_d) removed."""
    return {(x, z) for x in range(w) for z in range(d) if not (x >= w - cut_w and z >= d - cut_d)}


def footprint(shape: str, w=None, d=None, r=None, r_in=None, a0=0, a1=360, c=None, cut_w=None, cut_d=None):
    if shape == "rect":
        return fp_rect(w, d)
    if shape == "octagon":
        return fp_octagon(w, d, c)
    if shape == "round":
        return fp_round(r)
    if shape == "ring":
        return fp_ring(r, r_in if r_in is not None else max(1, r - 6), a0, a1)
    if shape == "L":
        return fp_l(w, d, cut_w or w // 2, cut_d or d // 2)
    raise ShapeError(f"unknown shape {shape}; rect | octagon | round | ring | L")


N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def edge(cells: set) -> set:
    return {(x, z) for (x, z) in cells if any((x + a, z + b) not in cells for a, b in N4)}


def corners(cells: set) -> set:
    """Edge cells where the outline turns (outside neighbours on two axes)."""
    out = set()
    for (x, z) in cells:
        ox = (x + 1, z) not in cells or (x - 1, z) not in cells
        oz = (x, z + 1) not in cells or (x, z - 1) not in cells
        if ox and oz:
            out.add((x, z))
    return out


# ------------------------------------------------------------------------------------------ the facade engine

def _arch_top(floor_h: int, bay: int, u: int, kit=None) -> int:
    """Highest glass row of a pointed (lancet) window at offset u inside a bay: tallest in the middle, stepping down."""
    step = 2 if floor_h >= 8 else 1
    if kit == "gothic" and floor_h >= 8:  # tall lancet: 6/5/3 rows across a 6 bay, reads from the street
        return max(1, floor_h - 2 - int(abs(u - bay / 2) * 1.5 + 0.01))
    return max(1, floor_h - 3 - step * int(abs(u - bay / 2) + 0.01))


def structure(shape: str = "rect", w: int = 15, d: int = 11, r: int = 8, r_in: int | None = None,
              a0: float = 0, a1: float = 360, c: int | None = None, cut_w: int | None = None, cut_d: int | None = None,
              floors: int = 2, floor_h: int = 4, kit: str | dict | None = None, roles: dict | None = None,
              windows: str = "band", bay: int = 4, accent_floor: int | None = 0, glow_floors: list | None = None,
              plinth: bool = True, ledges: bool = True, pillars: bool = True, parapet: str = "rail",
              roof_details: int = 3, antennas: int = 1, interior_floors: bool = True, open_ground: bool = False,
              seed: int = 1, roof: str | None = None, floor_hs: list | None = None, program: list | None = None,
              core: str = "auto", entrances: list | str | None = ("s",), pilasters: bool = True,
              rhythm: int = 0, finial: int = 3, depth: bool = True, **_ignored) -> list:
    """A styled building on any footprint. roof: flat (deck, parapet, vents, antennas) | mansard (steep stepped
    roof with dormers and a finial) | dome (ribbed glass dome with a lantern) | crown (art-deco stepped
    setbacks with glow bands and a mast). The outer ring of the footprint carries ledges/pillars; walls sit one
    block in. windows: band | grid | slit | none. accent_floor: index of the floor whose lintel+ledge is the accent
    stripe (None = no stripe). glow_floors: floors with a glowing lintel band (default: the top floor).
    parapet: rail | wall | none. open_ground: ground floor is open columns (pilotis) instead of walls.
    floor_hs: height per floor (overrides floors/floor_h), e.g. [7, 5, 5]: machine floors 6-8, living 4-5.
    program: room kinds per floor (a kind or a list of kinds split along the long axis), e.g.
    ["machine_hall", ["workshop", "storage"], ["living", "living"], "expansion"]; kinds: living, workshop, storage,
    machine_hall, expansion, lab, hall. A 3-wide spine along the long axis stays clear on every floor.
    core: auto | stairs | elevator | none -- how the floors connect (auto: stairs up to 3 floors, then a lift).
    entrances: sides with a 3-wide doorway on the ground floor (s, n, e, w), default ["s"].
    pilasters: piers on the outer ring every bay, full height, plus a base course: the facade gets depth (window
    bays sit one block back between piers) instead of one flat plane.
    rhythm: 0-3, facade bay rhythm (0 = every bay the same; 1-3 mix narrow and wide bays; wide bays get a centre mullion,
    ground floor gets a sill course + transom, upper floors run full-height glass). finial: height of roof finials.
    depth: facade depth pass (depth.py): base skirt, pier feet/capitals, cornice, window sills and hoods, all outward."""
    K = _kit(kit, roles)
    roof = roof or ROOF_DEFAULT.get(kit if isinstance(kit, str) else "", "flat")
    fp = footprint(shape, w, d, r, r_in, a0, a1, c, cut_w, cut_d)
    inner = {p for p in fp if p not in edge(fp)} if (ledges or pillars) else fp
    if len(inner) < 4:
        inner = fp
    wall_ring = edge(inner)
    ledge_ring = edge(fp) if inner is not fp else set()
    outer_corners = corners(fp) if ledge_ring else set()
    wall_corners = corners(inner)
    tmin = min(x + z for (x, z) in fp)
    tmax = max(x + z for (x, z) in fp) - tmin + 2
    seq = {0: [bay], 1: [bay, bay + 2], 2: [bay + 2, bay, bay], 3: [max(3, bay - 1), bay + 1, bay + 3]}.get(rhythm % 4, [bay])
    bayat, pos, k = {}, 0, 0
    while pos <= tmax:  # t -> (offset inside the bay, bay width)
        wdt = seq[k % len(seq)]
        for u in range(wdt):
            bayat[pos + u] = (u, wdt)
        pos, k = pos + wdt, k + 1
    mull_cells: set = set()
    arch_top: dict = {}
    hs = [max(3, int(h)) for h in floor_hs] if floor_hs else [floor_h] * floors
    floors = len(hs)
    y0s = [1 + sum(hs[:f]) for f in range(floors)]
    H = sum(hs)
    glow = set(glow_floors) if glow_floors is not None else {floors - 1}
    out: dict[tuple[int, int, int], str] = {}

    def put(x, y, z, b):
        out[(x, y, z)] = b

    # plinth: full footprint at y=0
    for (x, z) in fp:
        put(x, 0, z, K["base"] if plinth else K["wall2"])
    for f in range(floors):
        floor_h = hs[f]
        y0 = y0s[f]
        top = y0 + floor_h - 1
        stripe = accent_floor is not None and f == accent_floor
        for (x, z) in wall_ring:
            u, wb = bayat.get(x + z - tmin, (1, bay))
            mull = u == 0 or (x, z) in wall_corners
            if wb >= 7 and u == wb // 2 and windows in ("band", "grid", "lancet"):
                mull = True  # wide bay: centre mullion splits it into two windows
            if mull:
                mull_cells.add((x, z))
            for y in range(y0, top + 1):
                row = y - y0
                b = None
                if open_ground and f == 0:
                    b = K["trim"] if mull else None
                elif row == 0:
                    b = K["trim"]  # floor line
                elif y == top:
                    b = K["accent"] if stripe else (K.get("band", K["glow"]) if f in glow and not mull else K["wall"])
                else:
                    at = _arch_top(floor_h, wb, u, kit)
                    win = {"band": not mull,
                           "grid": not mull and 1 <= u <= min(wb - 2, 2 + (wb >= 6)) and row <= floor_h - 2,
                           "slit": u == wb // 2 and row <= floor_h - 2,
                           "lancet": not mull and 1 <= row <= at,
                           "none": False}.get(windows, not mull)
                    ground = f == 0 and floor_h >= 7 and windows != "lancet" and not mull
                    if ground and row == 1:
                        win = False  # ground floor: solid sill course
                    transom = ground and floor_h >= 9 and row == floor_h - 3
                    if transom:
                        win = False
                    b = K["glass"] if win else (K["trim"] if (mull or transom) else K["wall2"])
                    if kit == "gothic" and mull and not transom and (x, z) not in wall_corners and not win:
                        b = K["trim"]
                    if windows == "lancet" and kit == "gothic" and win and row == 3 and floor_h >= 8:
                        b = K["trim"]  # tracery bar across every lancet
                    if windows == "lancet" and not win and not mull and row == at + 1:
                        b = K["trim"]  # light frame over the pointed arch so it reads from the street
                    if windows == "lancet" and win and row == at:
                        arch_top[(x, z)] = y + 1
                if b:
                    put(x, y, z, b)
                    if b == K["glass"] and kit == "gothic" and row == 2:
                        q = next(((x+a,z+c) for a,c in N4 if (x+a,z+c) in inner and (x+a,z+c) not in wall_ring), None)
                        if q: put(q[0], y, q[1], K["glow"])
        # ledges on the outer ring at each floor line, plus the accent band
        for (x, z) in ledge_ring:
            put(x, top, z, K["accent"] if stripe else K["trim"])
            if f == floors - 1 and top - y0 >= 4 and any((x + a, z + c) in wall_ring for a, c in N4):
                put(x, top - 1, z, K["wall2"] if (x + z) % 3 else K["trim"])  # cornice: dentil course under the cap
        if interior_floors and f > 0:
            for (x, z) in inner:
                if (x, z) not in wall_ring:
                    put(x, y0, z, K["wall2"])
    # pilasters: a pier in the outer ring in front of every wall mullion, base course between them
    if pilasters and ledge_ring:
        for (x, z) in ledge_ring:
            put(x, 1, z, K["base"])
            nbr = [(x + a, z + c) for a, c in N4 if (x + a, z + c) in wall_ring]
            if any(q in mull_cells for q in nbr) and (x, z) not in outer_corners:
                for y in range(1, H + 1):
                    put(x, y, z, K.get("pillar", K["trim"]))
            elif kit == "gothic":  # pointed hood moulding standing out over every lancet
                for q in nbr:
                    if q in arch_top:
                        put(x, arch_top[q], z, K["trim"])
    # corner pillars full height on the outer ring
    if pillars:
        for (x, z) in outer_corners:
            for y in range(1, H + 1):
                put(x, y, z, K.get("pillar", K["trim"]))
    # roof deck + parapet
    ry = H + 1
    for (x, z) in inner:
        put(x, ry, z, K["roof"])
    for (x, z) in (ledge_ring or wall_ring):
        put(x, ry, z, K["trim"])
        if roof == "flat" and parapet == "rail":
            put(x, ry + 1, z, K["rail"])
        elif roof == "flat" and parapet == "wall":
            put(x, ry + 1, z, K["wall"])
    if program or core not in ("auto", "none") or entrances:
        _fit(put, out, inner, wall_ring, hs, y0s, ry, K, kit, program, core, entrances, seed, ledge_ring)
    if depth:
        import depth as _depth
        _depth.apply(out, K, fp, ledge_ring, wall_ring, H, ry)
    if roof != "flat":
        _roof(put, roof, inner, ry, K, bay, finial)
        return [[x, y, z, b] for (x, y, z), b in out.items()]
    # rooftop: vents/units and antennas, kept off the edge
    rnd = random.Random(seed)
    deck = sorted(p for p in inner if p not in edge(inner))
    if kit == "station_white" and deck:  # solar-panel rows with skylight strips between them
        zmin = min(p[1] for p in deck)
        for (x, z) in deck:
            v = (z - zmin) % 5
            if v in (1, 2):
                put(x, ry + 1, z, "minecraft:daylight_detector")
            elif v == 4 and (x // 3) % 2 == 0:
                put(x, ry, z, K["glass"])
    for _ in range(roof_details if deck else 0):
        x, z = rnd.choice(deck)
        sx, sz, sy = rnd.choice(((2, 2, 1), (3, 2, 2), (2, 3, 1), (1, 1, 2)))
        for dx in range(sx):
            for dz in range(sz):
                if (x + dx, z + dz) in inner:
                    for dy in range(sy):
                        put(x + dx, ry + 1 + dy, z + dz, K["detail"])
    for i in range(antennas if deck else 0):
        x, z = deck[(i * 7919 + seed * 31) % len(deck)]
        h = 4 + (i * 3 + seed) % 4
        for dy in range(h):
            put(x, ry + 1 + dy, z, K["antenna"])
        put(x, ry + 1 + h, z, K["tip"])
    return [[x, y, z, b] for (x, y, z), b in out.items()]


def _fit(put, out, inner, wall_ring, hs, y0s, ry, K, kit, program, core, entrances, seed, ledge_ring=()):
    """Entrances, stair/lift core and room fit-out inside a structure (see interiors.py)."""
    import interiors
    icells = {p for p in inner if p not in wall_ring}
    if len(icells) < 9:
        return
    kitname = kit if isinstance(kit, str) else ""
    floors = len(hs)
    stand = [1] + [y0s[f] + 1 for f in range(1, floors)]  # y a player stands at on each floor
    fy = [0] + [y0s[f] for f in range(1, floors)]  # y of the floor surface block
    ceil = [y0s[f + 1] if f + 1 < floors else ry for f in range(floors)]
    ax, spine = interiors.spine_of(icells)
    reserved: set = set()
    air = "minecraft:air"
    later = []  # doorways, stairs, holes and lifts go in after the fit-out so nothing refills them
    final_put = put
    put = lambda x, y, z, blk: later.append((x, y, z, blk))
    keys = {"s": lambda p: p[1], "n": lambda p: -p[1], "e": lambda p: p[0], "w": lambda p: -p[0]}
    # entrances: 3 wide x 3 high through the ground-floor wall, framed, glow lintel, approach kept clear
    for ent in ([entrances] if isinstance(entrances, str) else list(entrances or [])):
        side, _, at = str(ent).lower().partition("@")  # "n@15": door centred at local x (or z) 15
        side = side[:1]
        key = keys.get(side)
        if not key:
            continue
        m = max(key(p) for p in wall_ring)
        row = [p for p in wall_ring if key(p) == m]
        other = (lambda p: p[0]) if side in "sn" else (lambda p: p[1])
        mid = int(at) if at.lstrip("-").isdigit() else sorted(other(p) for p in row)[len(row) // 2]
        out_step = {"s": (0, 1), "n": (0, -1), "e": (1, 0), "w": (-1, 0)}[side]
        for (x, z) in row:
            if abs(other((x, z)) - mid) <= 1:
                shoulder = kitname == "gothic" and abs(other((x, z)) - mid) == 1  # pointed arch: no square top corners
                for y in range(1, 4):
                    put(x, y, z, K["trim"] if shoulder and y == 3 else air)
                put(x, 4, z, K["glow"])
                q = (x + out_step[0], z + out_step[1])  # through the outer ring too (pilasters, base course)
                if q in ledge_ring:
                    for y in range(1, 4):
                        put(q[0], y, q[1], K["trim"] if shoulder and y == 3 else air)
            elif abs(other((x, z)) - mid) == 2:
                for y in range(1, 5):
                    put(x, y, z, K.get("pillar", K["trim"]))
        for p in icells:  # approach: 4 deep inside the doorway
            if abs(other(p) - mid) <= 1 and m - key(p) <= 4:
                reserved.add(p)
    # core: how the floors connect
    rises = [stand[f + 1] - stand[f] for f in range(floors - 1)]
    kind = core
    if kind == "auto":
        kind = "stairs" if floors <= 3 else "elevator"
    wood = K.get("wood") or interiors.WOOD.get(kitname, "oak")
    if floors > 1 and kind == "stairs":
        L = max(rises) + 2  # landing + flight + landing
        a = 0 if ax == "x" else 1  # run along the long axis, against a long wall, off the spine
        b = 1 - a
        found = None
        for rb, step in ((min(p[b] for p in icells), 1), (max(p[b] for p in icells), -1)):
            for start in sorted({p[a] for p in icells}):
                def P(i, j, start=start, rb=rb, step=step):
                    return (start + i, rb + j * step) if a == 0 else (rb + j * step, start + i)
                if all(P(i, j) in icells and P(i, j) not in reserved and P(i, j) not in spine
                       for i in range(L) for j in range(3)):
                    found = P
                    break
            if found:
                break
        if found:
            P = found
            up = "east" if a == 0 else "south"
            for i in range(L):
                for j in range(3):
                    reserved.add(P(i, j))
            for f, rise in enumerate(rises):
                s0 = stand[f]
                for i in range(rise):
                    for j in (0, 1):
                        x, z = P(1 + i, j)
                        put(x, s0 + i, z, f"minecraft:{wood}_stairs[facing={up}]")
                for i in range(max(0, rise - 3), rise - 1):  # hole in the floor above for headroom
                    for j in (0, 1):
                        x, z = P(1 + i, j)
                        put(x, stand[f + 1] - 1, z, air)
        else:
            kind = "elevator"
    if floors > 1 and kind == "elevator":
        # lift shaft at one end of the spine: an elevator block in every floor, 2 air above each
        ends = sorted(spine, key=lambda p: p[0] + p[1])
        shaft = next((p for p in (ends[0], ends[-1]) if p not in reserved), ends[0])
        for f in range(floors):
            put(shaft[0], fy[f], shaft[1], f"elevatorid:elevator_{interiors.COLOUR.get(kitname, 'white')}")
            for dy in (1, 2):
                put(shaft[0], fy[f] + dy, shaft[1], air)
        reserved.add(shaft)
    for f in range(floors):
        prog = program[f] if program and f < len(program) else None
        if prog:
            interiors.fit_floor(prog, icells, fy[f], ceil[f] - fy[f] - 1, K, reserved, kitname,
                                seed + f * 17, final_put, ceil[f], K["wall2"],
                                door=(str(([entrances] if isinstance(entrances, str) else list(entrances or []))[0])[:1].lower()
                                      if entrances and f == 0 else None))
    for x, y, z, blk in later:
        final_put(x, y, z, blk)


def _shrink(cells: set, n: int = 1) -> set:
    for _ in range(n):
        cells = {p for p in cells if p not in edge(cells)}
    return cells


def _roof(put, kind: str, inner: set, ry: int, K: dict, bay: int, finial: int = 3):
    """Shaped roofs on top of the deck at y=ry (deck already placed)."""
    xs = [p[0] for p in inner]
    zs = [p[1] for p in inner]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    if kind == "mansard":
        layer, y, k = inner, ry + 1, 0
        while layer and k < 4:
            ring = edge(layer)
            for (x, z) in ring:
                dormer = k == 0 and (x + z) % bay == bay // 2 and (x, z) not in corners(layer)
                put(x, y, z, K["glass"] if dormer else K["roof"])
                if dormer:
                    put(x, y + 1, z, K["trim"])
            layer, y, k = _shrink(layer), y + 1, k + 1
        for (x, z) in layer:  # flat top with a trim edge
            put(x, y - 1, z, K["roof"])
        for (x, z) in edge(layer) if layer else []:
            put(x, y, z, K["trim"])
        top = y
    elif kind == "dome":
        rx = (max(xs) - min(xs)) / 2 + 0.5
        rz = (max(zs) - min(zs)) / 2 + 0.5
        rh = max(3.0, min(rx, rz))

        def inside(x, yy, z):
            if yy < 0:
                return True  # the deck below
            if (x, z) not in inner:
                return False
            dx, dz = (x - cx) / rx, (z - cz) / rz
            return dx * dx + dz * dz + (yy / rh) ** 2 <= 1.0
        # a real shell: every inside voxel with an outside face. Frame = meridian ribs (12, evenly spaced by arc
        # length), a ring every 4 rows, a solid drum at the base and a solid cap; glass only between the ribs.
        nrib = 12
        for (x, z) in inner:
            rho = math.hypot(x - cx, z - cz)
            ang = math.atan2(z - cz, x - cx)
            near = abs(((ang * nrib / (2 * math.pi)) + 0.5) % 1 - 0.5) * 2 * math.pi / nrib  # radians to a rib
            rib = rho * near < 0.6
            for yy in range(int(rh) + 1):
                if not inside(x, yy, z):
                    break
                if all(inside(x + a, yy + b, z + c) for a, b, c in
                       ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1))):
                    continue
                steep = not all(inside(x + a, yy, z + c) for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                frame = rib or yy <= 1 or (yy % 5 == 0 and steep) or rho < 2.6
                put(x, ry + 1 + yy, z, K.get("dome_rib", K["trim"]) if frame else K["glass"])
        top = ry + 1 + int(rh) + 1
        c0 = (round(cx), round(cz))  # lantern: glow core in a trim cage
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                put(c0[0] + a, top - 1, c0[1] + b, K["trim"])
                if a and b:
                    put(c0[0] + a, top, c0[1] + b, K["trim"])
        put(c0[0], top, c0[1], K["glow"])
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            put(c0[0] + a, top, c0[1] + b, K["glass"])
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                put(c0[0] + a, top + 1, c0[1] + b, K["trim"])
        top += 2
    elif kind == "crown":
        layer, y = inner, ry + 1
        for t in range(3):
            layer = _shrink(layer, 2)
            if len(layer) < 4:
                break
            ring = edge(layer)
            for h in range(3):
                for (x, z) in ring:
                    mull = (x + z) % 2 == 0
                    put(x, y + h, z, K["trim"] if h == 2 else (K["glow"] if h == 1 and not mull else K["wall"]))
            for (x, z) in layer:
                put(x, y + 2, z, K["trim"] if (x, z) in ring else K["roof"])
            y += 3
        top = y
    elif kind in HF_ROOFS:
        top = _hf_roof(put, kind, inner, ry, K, bay, finial)
        if top is None:
            return
    else:
        raise ShapeError(f"unknown roof {kind}; flat | mansard | dome | crown | " + " | ".join(sorted(HF_ROOFS)))
    c = (round(cx), round(cz))
    for dy in range(finial):
        put(c[0], top + dy, c[1], K["antenna"])
    put(c[0], top + finial, c[1], K["tip"])


HF_ROOFS = {"gable", "gable_steep", "gable_low", "hip", "hip_steep", "hip_low", "spire", "barrel", "sawtooth", "garden"}
LEAF = "minecraft:azalea_leaves[persistent=true]"
BLOOM = "minecraft:flowering_azalea_leaves[persistent=true]"
FLOWERS = ("minecraft:poppy", "minecraft:dandelion", "minecraft:allium", "minecraft:cornflower", "minecraft:azure_bluet",
           "minecraft:oxeye_daisy")


def _depth(inner: set) -> dict:
    """Distance of every cell to the footprint edge (0 = edge ring)."""
    out, layer, k = {}, set(inner), 0
    while layer:
        for p in edge(layer):
            out[p] = k
        layer = {p for p in layer if p not in out}
        k += 1
    return out


def _hf_roof(put, kind: str, inner: set, ry: int, K: dict, bay: int, finial: int = 3):
    """Height-field roofs (gable, hip, spire, barrel vault, sawtooth, planted garden). Each cell gets a column
    of blocks from its lowest neighbour up to its height: a one-block shell that reads as stepped slopes, with a
    solid gable end. Returns the finial y for hip/spire, else None (no finial)."""
    xs = [p[0] for p in inner]
    zs = [p[1] for p in inner]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    depth = _depth(inner)
    rect = len(inner) == (x1 - x0 + 1) * (z1 - z0 + 1)
    along_x = (x1 - x0) >= (z1 - z0)  # ridge direction (long axis)
    base = kind.split("_")[0]
    steep = kind.endswith("_steep")
    low = kind.endswith("_low")
    rnd = random.Random(len(inner) * 31 + ry)
    if base == "garden":  # roof planting: hedge ring on the edge only, low beds, flowers and skylights inside
        for (x, z) in inner:
            d = depth[(x, z)]
            if d == 0:
                put(x, ry + 1, z, LEAF if (x + z) % 5 else BLOOM)
                if (x * 7 + z * 3) % 4 == 0:
                    put(x, ry + 2, z, BLOOM)
                continue
            r = rnd.random()
            if d >= 2 and (x + z) % 5 == 0:
                put(x, ry, z, K["glass"])  # skylight into the room below
            elif d == 1 and r < 0.3:
                put(x, ry + 1, z, rnd.choice((LEAF, BLOOM)))
            elif r < 0.12:
                put(x, ry + 1, z, rnd.choice(FLOWERS))
        return None
    if base == "sawtooth":
        hf = {p: 1 + (((p[1] - z0) if along_x else (p[0] - x0)) % 6) // 2 for p in inner}
    elif base == "barrel" and rect:
        R = ((z1 - z0) if along_x else (x1 - x0)) / 2 + 0.5
        rise = min(R, 7.0)
        hf = {}
        for (x, z) in inner:
            c = abs(z - cz) if along_x else abs(x - cx)
            hf[(x, z)] = 1 + round(rise * math.sqrt(max(0.0, 1 - (c / R) ** 2)))
    elif base == "gable" and rect:
        s = 1.0 if steep else ((0.45 if "ridge" in K else 0.34) if low else 0.5)
        hf = {(x, z): 1 + int(min((z - z0, z1 - z) if along_x else (x - x0, x1 - x)) * s) for (x, z) in inner}
    else:  # hip, spire, and the fallback for non-rect footprints
        s = 2.0 if base == "spire" else (1.0 if steep else (0.34 if low else 0.5))
        hf = {p: 1 + int(depth[p] * s) for p in inner}
    cap = {"spire": 18, "hip": 6, "gable": 6, "barrel": 9, "sawtooth": 4}[base] + (4 if steep else 0)
    hf = {p: min(h, cap) for p, h in hf.items()}
    top = max(hf.values())
    for (x, z) in inner:
        h = hf[(x, z)]
        lo = min(hf.get((x + a, z + b), 0) for a, b in N4)
        end = (x in (x0, x1)) if along_x else (z in (z0, z1))
        for lv in range(max(1, lo), h + 1):
            if base == "sawtooth":
                u = ((z - z0) if along_x else (x - x0)) % 6
                blk = K["glass"] if u == 5 and lv >= 2 else K["roof"]
            elif base == "barrel":
                rib = (((x - x0) if along_x else (z - z0)) % 4) == 0
                blk = K["trim"] if (rib or end or lv == 1) else K["glass"]
            elif base == "gable":
                if end and rect:
                    off = abs((z - cz) if along_x else (x - cx))
                    mid = off <= 1
                    blk = K["glass"] if lv == 2 and h >= 4 and mid else K["wall"]
                    if "ridge" in K and h >= 3:  # gothic gable end (every gable type): rose window over a lancet
                        r2 = off * off + (lv - min(4, max(2, top - 2))) ** 2
                        if r2 <= 2:
                            blk = K["glass"]
                        elif r2 <= 5 and lv >= 2:
                            blk = K["trim"]
                        elif off <= 1 and lv <= 3:
                            blk = K["glass"]
                        elif off == 2 and lv <= 3:
                            blk = K["trim"]
                else:
                    blk = K.get("ridge", K["trim"]) if (lv == h and h == top) else K["roof"]
                    blk, dorm = _rib(blk, lv == h, (x - x0) if along_x else (z - z0), depth[(x, z)], K)
                    if dorm:
                        put(x, ry + lv + 1, z, K["trim"])
            else:  # hip / spire
                blk = K.get("ridge", K["trim"]) if (lv == h and depth[(x, z)] == 0) else K["roof"]
                if base == "hip":
                    blk, dorm = _rib(blk, lv == h, x - x0 + z - z0, depth[(x, z)], K)
                    if dorm:
                        put(x, ry + lv + 1, z, K["trim"])
            put(x, ry + lv, z, blk)
    if base == "gable" and rect:  # lantern finials on both ridge ends
        for (fx, fz) in (((x0, round(cz)), (x1, round(cz))) if along_x else ((round(cx), z0), (round(cx), z1))):
            for dy in range(1, finial):
                put(fx, ry + top + dy, fz, K["antenna"])
            put(fx, ry + top + finial, fz, K["tip"])
    if base in ("hip", "spire"):
        return ry + top + 1
    return None


def _rib(blk, surface, a, depth, K):
    """Roof surface rib every 4 cells, and a lit dormer slot every 8 on the second row. Returns (block, dormer_lintel)."""
    if not surface:
        return blk, False
    if depth == 1 and a % 8 == 4:
        return K["glass"], True
    if a % 4 == 0:
        return K["trim"], False
    return blk, False


def platform(shape: str = "round", w: int = 21, d: int = 21, r: int = 12, c: int | None = None,
             kit: str | dict | None = None, roles: dict | None = None, steps: int = 2, rail: bool = False,
             pattern: str = "grid", **_ignored) -> list:
    """A base/island to set buildings on: a terraced footprint `steps` high, each step 1 smaller, top at y=steps-1.
    pattern: grid (trim lines every 4), plain, or ring (concentric trim). The single most effective framing trick."""
    K = _kit(kit, roles)
    fp = footprint(shape, w, d, r, None, 0, 360, c)
    out = {}
    layer = fp
    for s in range(steps):
        top = s == steps - 1
        e = edge(layer)
        for (x, z) in layer:
            if top:
                # quiet floor: grid lines in the second tone, trim only on the rim
                b = K["trim"] if (x, z) in e else (
                    K["wall2"] if pattern == "grid" and (x % 6 == 0 or z % 6 == 0) else K["base"])
            else:
                b = K["wall2"] if (x, z) in e else K["base"]
            out[(x, s, z)] = b
        if top and rail:
            for (x, z) in e:
                out[(x, s + 1, z)] = K["rail"]
        nxt = {p for p in layer if p not in e}
        if not nxt:
            break
        layer = nxt if not top else layer
    return [[x, y, z, b] for (x, y, z), b in out.items()]


def bridge(length: int = 12, along: str = "x", width: int = 5, height: int = 4, kit: str | dict | None = None,
           roles: dict | None = None, glass_roof: bool = True, **_ignored) -> list:
    """Enclosed sky-bridge/corridor: floor, trim edges, glass walls with mullions every 3, glass or solid roof,
    a glow strip down the floor centre. Use it to connect wings instead of plain boxes."""
    K = _kit(kit, roles)
    out = []
    for i in range(length):
        for j in range(width):
            x, z = (i, j) if along == "x" else (j, i)
            side = j in (0, width - 1)
            out.append([x, 0, z, K["glow"] if j == width // 2 and i % 3 == 1 else K["base"]])
            if side:
                for y in range(1, height):
                    out.append([x, y, z, K["trim"] if (i % 3 == 0 or y == 1) else K["glass"]])
            out.append([x, height, z, K["trim"] if side else (K["glass"] if glass_roof else K["roof"])])
    return out


def slope(w: int = 9, run: int = 12, rise: int = 8, axis: str = "x", kit: str | dict | None = None,
          roles: dict | None = None, **_ignored) -> list:
    """Sloped glass wall/roof rising along `axis` from y=0 to y=rise over `run`, framed by solid trim edges
    (the greenhouse/lab ramp look). The space under it is filled with wall so it reads as a volume."""
    K = _kit(kit, roles)
    out = []
    for i in range(run):
        yt = round((i + 1) * rise / run)
        for j in range(w):
            x, z = (i, j) if axis == "x" else (j, i)
            framed = j in (0, w - 1)
            for y in range(0, yt):
                out.append([x, y, z, K["wall"] if framed else K["wall2"]])
            out.append([x, yt, z, K["trim"] if framed or i % 4 == 0 else K["glass"]])
    return out


def spire(h: int = 20, base: int = 5, kit: str | dict | None = None, roles: dict | None = None,
          **_ignored) -> list:
    """Tapering tower/antenna mast: square stages that shrink every h/base blocks, ledge at each step, glow
    ring at mid height, a tip. A landmark silhouette for the tallest point of a base."""
    K = _kit(kit, roles)
    out = {}
    stages = max(1, base // 2 + 1)
    sh = max(2, h // stages)
    y = 0
    for s in range(stages):
        size = base - 2 * s
        if size < 1:
            break
        o = s
        for yy in range(sh):
            for x in range(size):
                for z in range(size):
                    shell = x in (0, size - 1) or z in (0, size - 1)
                    if shell or size <= 2:
                        b = K["glow"] if yy == sh // 2 and s == stages // 2 else (K["trim"] if (x in (0, size - 1) and z in (0, size - 1)) else K["wall"])
                        out[(o + x, y + yy, o + z)] = b
        y += sh
    c = base // 2
    for yy in range(4):
        out[(c, y + yy, c)] = K["antenna"]
    out[(c, y + 4, c)] = K["tip"]
    return [[x, yy, z, b] for (x, yy, z), b in out.items()]


KINDS = {"structure": structure, "platform": platform, "bridge": bridge, "slope": slope, "spire": spire}
