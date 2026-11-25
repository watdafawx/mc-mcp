"""Step 4 of the quality plan: the motif library. Set pieces that make a build read as intentional (clock faces, gears on
blank wall, pagoda roofs, pipe racks, porches, cranes, signs, balconies, smokestacks, water tanks, landing pads, timber
framing), each written once, carefully, and placed by the design composer (design.py).

Three kinds:
- WALL motifs: fn(K, **p) -> {(u, v, y): block} in a wall frame: u = outward from the volume's edge layer (u=0 is the
  edge/pier ring, u=-1 the wall plane with the windows), v = along the wall (0 = motif centre, + = right when you face
  the wall from outside), y = up from the motif's base. Block strings may use {out} {in} {left} {right} (compass
  facings) and {axis_u} {axis_v} (log/pillar axes); `frame()` rotates them per side. Each WALL motif has a SIZE entry
  (half_width, height) so the composer can find a blank stretch of wall for it.
- LINE motifs: fn(K, n, hs, **p) -> {(u, v, y)} along a whole side (v = 0..n-1, y from the volume's plinth).
- TOP motifs: fn(K, w, d, **p) -> {(x, y, z): block} over a w x d roof rectangle (x, z from the volume's bbox corner,
  y = 0 is the first layer above the roof deck). The composer flattens the roof under them.

Interior rule: nothing here goes inside a room. Wall motifs live at u >= 0, top motifs above the roof deck.
"""
from __future__ import annotations

import math

import depth  # stairs/slab variants of kit roles (validated against blocklib)

AIR = "minecraft:air"
COMPASS = {"s": dict(out="south", in_="north", right="east", left="west", axis_u="z", axis_v="x"),
           "n": dict(out="north", in_="south", right="west", left="east", axis_u="z", axis_v="x"),
           "e": dict(out="east", in_="west", right="north", left="south", axis_u="x", axis_v="z"),
           "w": dict(out="west", in_="east", right="south", left="north", axis_u="x", axis_v="z")}


def to_world(side: str, ax: int, az: int, u: int, v: int) -> tuple[int, int]:
    """Wall frame -> world x, z. (ax, az) = the edge-layer cell at the motif centre."""
    if side == "s":
        return ax + v, az + u
    if side == "n":
        return ax - v, az - u
    if side == "e":
        return ax + u, az - v
    return ax - u, az + v


def orient(block: str, side: str) -> str:
    c = COMPASS[side]
    return (block.replace("{out}", c["out"]).replace("{in}", c["in_"]).replace("{right}", c["right"])
            .replace("{left}", c["left"]).replace("{axis_u}", c["axis_u"]).replace("{axis_v}", c["axis_v"]))


def frame(cells: dict, side: str, ax: int, az: int, y0: int) -> list:
    """Wall-frame motif -> world [x, y, z, block]."""
    out = []
    for (u, v, y), b in cells.items():
        x, z = to_world(side, ax, az, u, v)
        out.append([x, y0 + y, z, orient(b, side)])
    return out


def _stairs(K, roles, fallback="minecraft:stone_brick_stairs"):
    for r in roles:
        s = depth._variant(K.get(r), "stairs")
        if s:
            return s
    return fallback


def _slab(K, roles, fallback="minecraft:stone_brick_slab"):
    for r in roles:
        s = depth._variant(K.get(r), "slab")
        if s:
            return s
    return fallback


def _light(K) -> bool:
    """True when the kit's wall reads light (pick dark details then)."""
    import palette
    return palette._lum((K.get("wall2") or K.get("wall") or "").split("[", 1)[0]) > 150


# ---------------------------------------------------------------- WALL motifs

def clock(K: dict, r: int = 4, **_) -> dict:
    """Clock face: backing disc in the edge layer (fills the recessed bays), proud face at u=1 with a trim rim, 12 hour
    markers, hour hand at ten, minute hand at two, lit hub, a slab hood over the top. Centre at y = r + 1."""
    r = max(3, min(6, r))
    face = "minecraft:smooth_quartz" if not _light(K) else "minecraft:white_concrete"
    dark = "minecraft:polished_blackstone"
    rim = K.get("trim", "minecraft:stone_bricks")
    B = {}
    cy = r + 1
    for v in range(-r - 1, r + 2):
        for dy in range(-r - 1, r + 2):
            d = math.hypot(v, dy)
            if d <= r + 0.5:
                B[(0, v, cy + dy)] = K.get("wall2", rim)
            if d <= r - 0.5:
                B[(1, v, cy + dy)] = face
            elif d <= r + 0.5:
                B[(1, v, cy + dy)] = rim
    for k in range(12):  # hour markers just inside the rim
        a = math.radians(k * 30)
        B[(1, round((r - 1.2) * math.sin(a)), cy + round((r - 1.2) * math.cos(a)))] = dark
    for frac in [i / 4 for i in range(1, 4 * r)]:
        for ang, ln in ((-60, 0.55), (60, 0.9)):  # hour hand at ten, minute hand at two
            t = frac / r
            if t <= ln:
                a = math.radians(ang)
                B[(1, round(frac * math.sin(a)), cy + round(frac * math.cos(a)))] = "minecraft:black_concrete"
    B[(1, 0, cy)] = K.get("glow", "minecraft:shroomlight")
    hood = _slab(K, ("trim", "roof"))
    for v in range(-2, 3):
        B[(1, v, cy + r + 1)] = hood + "[type=bottom]"
    return B


def gear(K: dict, r: int = 3, **_) -> dict:
    """Gear disc proud of the wall (u=1) on a backing plate (u=0): toothed rim in trim, spokes + hub in detail."""
    r = max(2, min(5, r))
    B = {}
    cy = r + 2
    for v in range(-r - 1, r + 2):
        for dy in range(-r - 1, r + 2):
            d = math.hypot(v, dy)
            ang = math.degrees(math.atan2(dy, v)) % 45
            b = None
            if r - 0.6 <= d <= r + 0.4:
                b = K["trim"]
            elif r + 0.4 < d <= r + 1.4 and ang < 15:
                b = K["trim"]
            elif d < 1.5 or ((v == 0 or dy == 0 or abs(v) == abs(dy)) and d < r):
                b = K.get("detail", K["trim"])
            if b:
                B[(1, v, cy + dy)] = b
                if d <= r + 0.4:
                    B[(0, v, cy + dy)] = K.get("wall2", K["trim"])
    return B


SIZE = {"clock": lambda p: (min(6, max(3, p.get("r", 4))) + 1, 2 * min(6, max(3, p.get("r", 4))) + 4),
        "gear": lambda p: (min(5, max(2, p.get("r", 3))) + 1, 2 * min(5, max(2, p.get("r", 3))) + 4)}
WALL = {"clock": clock, "gear": gear}


# ---------------------------------------------------------------- LINE motifs

def pipe_rack(K: dict, n: int, hs: list, **_) -> dict:
    """Thin Create pipe run one block off the wall just under the first floor line (u=1), wall brackets every 4,
    risers down to the plinth at both ends with a pump, a lit valve every 8. Reads as plumbing, not graffiti."""
    B = {}
    if n < 6:
        return B
    y = max(3, hs[0] - 1)
    bracket = "minecraft:polished_blackstone_wall"
    for v in range(1, n - 1):
        B[(1, v, y)] = "create:fluid_pipe"
        if v % 4 == 2:
            B[(1, v, y - 1)] = bracket
        if v % 8 == 5:
            B[(2, v, y)] = "minecraft:copper_block"  # valve body with a lit bulb on top
            B[(2, v, y + 1)] = "minecraft:copper_bulb[lit=true]"
    for v in (1, n - 2):
        for yy in range(1, y):
            B[(1, v, yy)] = "create:fluid_pipe"
        B[(1, v, 1)] = "create:mechanical_pump[facing=up]"
        B[(1, v, 0)] = K.get("base", "minecraft:stone_bricks")
    return B


LINE = {"pipe_rack": pipe_rack}


# ---------------------------------------------------------------- TOP motifs

def pagoda(K: dict, w: int, d: int, tiers: int = 3, **_) -> dict:
    """Stacked pagoda roof over a w x d deck: each tier a flared eave (stairs one block past the edge, sweeping up at
    the corners with a hanging lantern), a short lit body set back 2, the next tier 2 smaller; a finial on top."""
    stair = _stairs(K, ("roof", "trim"), "minecraft:deepslate_tile_stairs")
    roof = K.get("roof", "minecraft:deepslate_tiles")
    body, pillar = K.get("wall2", "minecraft:spruce_planks"), K.get("pillar", K.get("trim"))
    glow, glass = K.get("glow", "minecraft:shroomlight"), K.get("glass", "minecraft:glass")
    slab = _slab(K, ("trim", "roof"))
    B = {}
    x0, z0, x1, z1 = 0, 0, w - 1, d - 1
    y = 0
    tiers = max(1, min(4, tiers))
    for t in range(tiers):
        if x1 - x0 < 4 or z1 - z0 < 4:
            break
        # eave: 2 rows of stairs, outer row one past the edge at y, next row on the edge at y+1, cap inside
        for k, (o, yy) in enumerate(((1, y), (0, y + 1))):
            for x in range(x0 - o, x1 + o + 1):
                for z in range(z0 - o, z1 + o + 1):
                    edge_x = x in (x0 - o, x1 + o)
                    edge_z = z in (z0 - o, z1 + o)
                    if not (edge_x or edge_z):
                        continue
                    if edge_x and edge_z:
                        B[(x, yy, z)] = roof
                        continue
                    face = ("west" if x == x0 - o else "east") if edge_x else ("north" if z == z0 - o else "south")
                    back = {"west": "east", "east": "west", "north": "south", "south": "north"}[face]
                    B[(x, yy, z)] = f"{stair}[facing={back},half=bottom]"
        for x in range(x0 + 1, x1):
            for z in range(z0 + 1, z1):
                B[(x, y + 1, z)] = roof
        for cx, cz in ((x0 - 2, z0 - 2), (x1 + 2, z0 - 2), (x0 - 2, z1 + 2), (x1 + 2, z1 + 2)):  # curled corners
            B[(cx, y + 1, cz)] = slab + "[type=bottom]"
        for cx, cz in ((x0 - 1, z0 - 1), (x1 + 1, z0 - 1), (x0 - 1, z1 + 1), (x1 + 1, z1 + 1)):
            B[(cx, y - 1, cz)] = "minecraft:lantern[hanging=true]"
        # body of the next tier: set back 2, 3 high, corner posts, a lit window band mid-side
        nx0, nz0, nx1, nz1 = x0 + 2, z0 + 2, x1 - 2, z1 - 2
        if t == tiers - 1 or nx1 - nx0 < 4 or nz1 - nz0 < 4:
            break
        bh = 3
        for yy in range(y + 2, y + 2 + bh):
            for x in range(nx0, nx1 + 1):
                for z in range(nz0, nz1 + 1):
                    if x not in (nx0, nx1) and z not in (nz0, nz1):
                        continue
                    corner = x in (nx0, nx1) and z in (nz0, nz1)
                    mid = abs(x - (nx0 + nx1) / 2) <= 1 or abs(z - (nz0 + nz1) / 2) <= 1
                    B[(x, yy, z)] = pillar if corner else (glass if mid and yy == y + 3 else body)
            if yy == y + 2 + bh - 1:
                for x in range(nx0, nx1 + 1):
                    for z in range(nz0, nz1 + 1):
                        if (x in (nx0, nx1) or z in (nz0, nz1)) and not (x in (nx0, nx1) and z in (nz0, nz1)):
                            B[(x, yy, z)] = K.get("trim", body)
        B[((nx0 + nx1) // 2, y + 3, (nz0 + nz1) // 2)] = glow
        x0, z0, x1, z1 = nx0, nz0, nx1, nz1
        y += 2 + bh
    # cap + finial
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    top = max(k[1] for k in B) + 1 if B else 0
    for dy, b in enumerate((pillar, K.get("trim", pillar), "minecraft:chain", K.get("tip", "minecraft:lantern"))):
        B[(cx, top + dy, cz)] = b
    return B


TOP = {"pagoda": pagoda}

ALL = sorted(WALL) + sorted(LINE) + sorted(TOP)
