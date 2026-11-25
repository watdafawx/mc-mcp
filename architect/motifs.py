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
import palette

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
    return palette._lum((K.get("wall2") or K.get("wall") or "").split("[", 1)[0]) > 150


def _blk(K, role, fallback):
    """Kit role block when the pack has it (blocklib), else the vanilla fallback."""
    b = K.get(role)
    lib = palette._lib()
    if b and (not lib or b.split("[", 1)[0] in lib):
        return b
    return fallback


def _axised(block: str, axis: str) -> str:
    """block with an axis state when it is a log / pillar style block, else unchanged."""
    base = block.split("[", 1)[0]
    name = base.split(":", 1)[-1]
    if name.endswith(("_log", "_wood", "_stem", "_hyphae", "_pillar")) or name == "bone_block":
        return f"{base}[axis={axis}]"
    return block


def _disc(r: int) -> set:
    """Filled blocky disc of radius r: r=1 is the 3x3 square, r>=2 the square minus its corners (d=5: 3,5,5,5,3)."""
    return {(a, b) for a in range(-r, r + 1) for b in range(-r, r + 1) if r < 2 or not (abs(a) == r and abs(b) == r)}


def candidates(kind: str, size: int = 0) -> list:
    """Parameter sets to try for a wall motif, biggest first (the composer shrinks it until it fits a spot)."""
    if kind in ("clock", "gear"):
        lo = 2 if kind == "clock" else 3
        return [{"r": r} for r in range(max(lo, size or 4), lo - 1, -1)]
    if kind == "balcony":
        return [{"hw": hw} for hw in range(min(3, max(1, size or 2)), 0, -1)]
    if kind == "smokestack":
        return [{"h": max(8, min(40, size or 14))}]
    return [{}]


# ---------------------------------------------------------------- WALL motifs

def clock(K: dict, r: int = 4, **_) -> dict:
    """Clock face: backing disc in the edge layer (fills the recessed bays), proud face at u=1 with a trim rim, dark
    markers at 12/3/6/9 (r >= 4), axis-aligned hands (minute up, hour to 3: clean at block scale), lit hub, a slab
    hood over the top. Centre at y = r + 1. r 2..6 (r=2 fits a 5-wide tower face)."""
    r = max(2, min(6, r))
    face = "minecraft:smooth_quartz" if not _light(K) else "minecraft:white_concrete"
    dark = "minecraft:polished_blackstone"
    hand = "minecraft:black_concrete"
    rim = K.get("trim", "minecraft:stone_bricks")
    B = {}
    cy = r + 1
    for v in range(-r - 1, r + 2):
        for dy in range(-r - 1, r + 2):
            d = math.hypot(v, dy)
            if d <= r + 0.5:
                B[(0, v, cy + dy)] = K.get("wall2", rim)
                B[(1, v, cy + dy)] = face if d <= r - 0.5 else rim
    if r >= 4:
        for v, dy in ((0, r - 1), (r - 1, 0), (0, -(r - 1)), (-(r - 1), 0)):
            B[(1, v, cy + dy)] = dark
    for k in range(1, max(2, r - 1)):  # minute hand straight up
        B[(1, 0, cy + k)] = hand
    for k in range(1, max(2, r // 2 + 1)):  # hour hand to three
        B[(1, k, cy)] = hand
    B[(1, 0, cy)] = K.get("glow", "minecraft:shroomlight")
    hood = _slab(K, ("trim", "roof"))
    for v in range(-min(2, r), min(2, r) + 1):
        B[(1, v, cy + r + 1)] = hood + "[type=bottom]"
    return B


def gear(K: dict, r: int = 4, **_) -> dict:
    """Cog proud of the wall (u=1) on a backing plate (u=0): a solid rim ring in trim with 8 square teeth (4 on the axes,
    4 on the diagonals, 2x2 so they read at block scale), 4 axis spokes and a 3x3 hub in detail, a lit axle.
    Only placed on a blank stretch of wall (never over windows). r 3..5."""
    r = max(3, min(5, r))
    rim, body = K["trim"], K.get("detail", K["trim"])
    B = {}
    cy = r + 1
    for v in range(-r, r + 1):
        for dy in range(-r, r + 1):
            d = math.hypot(v, dy)
            if r - 1.5 <= d <= r + 0.4:
                B[(1, v, cy + dy)] = rim
            elif d < r - 1.5 and (v == 0 or dy == 0 or (abs(v) <= 1 and abs(dy) <= 1)):
                B[(1, v, cy + dy)] = body
            if d <= r + 0.4:
                B[(0, v, cy + dy)] = K.get("wall2", rim)
    for v, dy in ((0, r + 1), (0, -r - 1), (r + 1, 0), (-r - 1, 0)):  # axis teeth: 3 wide, 1 deep
        for k in (-1, 0, 1):
            B[(1, v + (k if v == 0 else 0), cy + dy + (k if dy == 0 else 0))] = rim
    t = round((r + 0.4) / math.sqrt(2))
    for sv in (-1, 1):  # diagonal teeth: 2x2 on the rim
        for sd in (-1, 1):
            for a in (0, 1):
                for b in (0, 1):
                    B[(1, sv * (t + a), cy + sd * (t + b))] = rim
    B[(1, 0, cy)] = K.get("glow", "minecraft:shroomlight")
    return B


def porch(K: dict, style: str = "classic", **_) -> dict:
    """Entrance canopy over a doorway (centred on v=0, doorway 3 wide). classic: two pillars at u=3 under a log beam,
    a lean-to roof falling away from the wall, a pediment on the front plane and a hanging lantern; industrial: no
    columns, a flat steel-look canopy hung from wall brackets by chains. Both: stairs facing in at the threshold plus
    a slab apron. 7 wide, up to 8 high, 4 deep (u=1..4). y=0 is the ground (plinth) level."""
    classic = style != "industrial"
    trim = _blk(K, "trim", "minecraft:stone_bricks")
    pillar = _blk(K, "pillar", trim)
    roof = _blk(K, "roof", trim)
    base = _blk(K, "base", trim)
    stair_r = _stairs(K, ("roof", "trim"))
    B = {}
    for v in range(-1, 2):  # threshold steps, tall back toward the building
        B[(1, v, 0)] = _stairs(K, ("base", "trim")) + "[facing={in},half=bottom]"
    for v in range(-2, 3):
        B[(2, v, 0)] = _slab(K, ("base", "trim")) + "[type=bottom]"
    if classic:
        for v in (-2, 2):  # columns on a plinth, tie beams back to the wall
            B[(3, v, 0)] = base
            for y in range(1, 4):
                B[(3, v, y)] = _axised(pillar, "y")
            for u in (1, 2):
                B[(u, v, 4)] = _axised(pillar, "{axis_u}")
        for v in range(-3, 4):  # entablature beam, lean-to roof falling away from the wall
            B[(3, v, 4)] = _axised(pillar, "{axis_v}")
            B[(1, v, 5)] = roof
            B[(2, v, 5)] = stair_r + "[facing={in},half=bottom]"
            B[(4, v, 4)] = stair_r + "[facing={in},half=bottom]"
        up = lambda v: "[facing={right},half=bottom]" if v < 0 else "[facing={left},half=bottom]"  # climb to centre
        for v in range(-3, 4):  # pediment: stepped triangle on the front plane
            B[(3, v, 5)] = stair_r + up(v) if abs(v) == 3 else trim
        for v in range(-2, 3):
            B[(3, v, 6)] = stair_r + up(v) if abs(v) == 2 else trim
        for v in (-1, 0, 1):
            B[(3, v, 7)] = stair_r + up(v) if v else trim
        B[(3, 0, 3)] = "minecraft:lantern[hanging=true]"
    else:
        deck = _slab(K, ("trim", "roof"))
        for u in range(1, 5):
            for v in range(-3, 4):
                B[(u, v, 4)] = deck + "[type=bottom]"
        for v in range(-3, 4):
            B[(4, v, 5)] = "minecraft:iron_bars"  # front lip
        for v in (-3, 3):  # bracket arms on the wall, chains down to the canopy corners
            for u in range(0, 5):
                B[(u, v, 7)] = "minecraft:iron_bars"
            for u in (1, 4):
                B[(u, v, 5)] = "minecraft:chain[axis=y]"
                B[(u, v, 6)] = "minecraft:chain[axis=y]"
        B[(2, 0, 3)] = "minecraft:lantern[hanging=true]"
    return B


def balcony(K: dict, hw: int = 2, **_) -> dict:
    """Balcony: top-slab floor at u=0..2 (level with the room floor behind it), a rail on the outer edge and both
    sides, upside-down stair brackets under it every 2 blocks. y=0 is the bracket row, y=1 the floor, y=2 the rail."""
    hw = max(1, min(3, hw))
    slab = _slab(K, ("trim", "base"))
    stair = _stairs(K, ("trim", "base"))
    rail = _blk(K, "rail", "minecraft:iron_bars")
    B = {}
    for u in (0, 1, 2):
        for v in range(-hw, hw + 1):
            B[(u, v, 1)] = slab + "[type=top]"
    for v in range(-hw, hw + 1, 2):
        B[(1, v, 0)] = stair + "[facing={in},half=top]"
    for v in range(-hw, hw + 1):
        B[(2, v, 2)] = rail
    for v in (-hw, hw):
        B[(1, v, 2)] = rail
    return B


def blade_sign(K: dict, glyph: str = "H", **_) -> dict:
    """Projecting blade sign, 1 thick, standing out from the wall (u=1..3): accent field with a glowing letter,
    trim frame top and bottom, two chains up to an iron bracket arm that runs back to the wall.
    y=0..4 board, y=5 chains, y=6 arm."""
    trim = _blk(K, "trim", "minecraft:polished_blackstone")
    accent = _blk(K, "accent", "minecraft:red_concrete")
    glow = _blk(K, "glow", "minecraft:shroomlight")
    B = {}
    for u in (1, 2, 3):
        B[(u, 0, 0)] = trim
        B[(u, 0, 4)] = trim
        for y in (1, 2, 3):
            B[(u, 0, y)] = accent
    lit = {"H": {(1, 1), (1, 2), (1, 3), (3, 1), (3, 2), (3, 3), (2, 2)},
           "I": {(1, 1), (2, 1), (3, 1), (2, 2), (1, 3), (2, 3), (3, 3)},
           "O": {(1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3), (3, 3)}}.get(glyph, set())
    for (u, y) in lit:
        B[(u, 0, y)] = glow
    for u in (1, 3):
        B[(u, 0, 5)] = "minecraft:chain[axis=y]"
    for u in range(0, 4):
        B[(u, 0, 6)] = "minecraft:iron_bars"
    return B


def smokestack(K: dict, h: int = 14, **_) -> dict:
    """Round brick smokestack standing on the ground beside the wall (centre u=3, so u=1..5: touching the edge layer,
    never entering the building). Hollow shell, radius 2 at the base -> 1 above 55% of the height, trim bands every 5,
    a flared cap and a lit campfire in the throat for the smoke. y=0 is the ground (plinth) level; h = stack height."""
    h = max(8, min(40, h))
    brick = _blk({"x": K.get("wall2") if "brick" in (K.get("wall2") or "") else None}, "x", "minecraft:bricks")
    trim = _blk(K, "trim", "minecraft:stone_bricks")
    slab = _slab(K, ("trim", "base"))
    cu = 3
    ring = {2: _disc(2) - _disc(1), 1: _disc(1) - {(0, 0)}}
    B = {}

    def put(cells, y, b):
        for (a, c) in cells:
            B[(cu + a, c, y)] = b
    put(_disc(2), 0, _blk(K, "base", trim))
    cut = int(h * 0.55)
    for y in range(1, h - 3):
        put(ring[2 if y < cut else 1], y, trim if y % 5 == 4 else brick)
    put(ring[2], cut, trim)  # shoulder where the radius steps down
    put(ring[1], h - 3, trim)  # collar under the flare
    B[(cu, 0, h - 3)] = brick  # the throat floor the fire sits on
    put(ring[2], h - 2, trim)  # flare
    put(ring[2], h - 1, slab + "[type=bottom]")  # cap lip
    B[(cu, 0, h - 2)] = "minecraft:campfire[lit=true,signal_fire=true]"
    return B


SIZE = {"clock": lambda p: (min(6, max(2, p.get("r", 4))), 2 * min(6, max(2, p.get("r", 4))) + 4),
        "gear": lambda p: (min(5, max(3, p.get("r", 4))) + 1, 2 * min(5, max(3, p.get("r", 4))) + 3),
        "porch": lambda p: (3, 8),
        "balcony": lambda p: (max(1, min(3, p.get("hw", 2))), 3),
        "blade_sign": lambda p: (1, 7),
        "smokestack": lambda p: (2, max(8, min(40, p.get("h", 14))) + 1)}
WALL = {"clock": clock, "gear": gear, "porch": porch, "balcony": balcony, "blade_sign": blade_sign,
        "smokestack": smokestack}

# How design.py places each wall motif (everything else is "find a blank stretch of wall"):
DOOR = {"porch"}                       # centred on a ground-floor doorway (design._door_spot), never on blank wall
GROUND = {"smokestack"}                # stands on the ground outside the footprint, no wall spot needed
BLANK_ONLY = {"gear"}                  # blank wall or nothing: never a blind panel (a gear over windows reads as a splat)
ON_WINDOW = {"balcony", "blade_sign"}  # may sit over windows (never doorways); windows behind are left alone
SOFT_EDGE = {"balcony", "blade_sign"}  # u=0 cells never overwrite a pier / ledge block of the volume
OVERLAY = {"timber_frame"}             # LINE motif that only REPLACES existing wall blocks (given `existing`)
ON_DECK = {"water_tank", "landing_pad", "crane"}  # TOP motifs that must stand on the deck (cells outside it dropped)


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


def timber_frame(K: dict, n: int, hs: list, existing=None, **_) -> dict:
    """Half-timber overlay for a whole side. It only REPLACES blocks already in the facade (`existing(u, v, y)` ->
    block or None, same frame as the returned cells, y up from the plinth): vertical posts at every pier line (the
    pilaster at u=0 and the wall plane behind it at u=-1), horizontal beams on the floor lines (wall plane) and on the
    ledge band at each floor top (u=0), diagonal braces in blank wall2 panels between posts (alternating direction).
    Glass, doorways, lintels and light bands are never touched. Without `existing` it returns nothing."""
    if existing is None or n < 7:
        return {}
    wall2, trim = K.get("wall2"), K.get("trim")
    pillar = K.get("pillar", trim)
    log = "minecraft:stripped_dark_oak_log" if _light(K) else "minecraft:stripped_spruce_log"
    post, beam, brace = log + "[axis=y]", log + "[axis={axis_v}]", log + "[axis={axis_v}]"
    H = sum(hs)
    floors = [1 + sum(hs[:f]) for f in range(len(hs))]
    tops = [sum(hs[:f + 1]) for f in range(len(hs) - 1)]
    swap = {-1: (wall2, trim, pillar), 0: (trim, pillar)}

    def can(u, v, y):
        return existing(u, v, y) in swap[u]
    # pier line = a pilaster / corner pillar stands at u=0 (the wall plane behind it cannot tell: wall2 is often
    # the same block as the pillar role)
    piers = [v for v in range(n) if existing(0, v, 2) == pillar]
    B = {}
    for y in floors:  # beams first so the posts cross them
        for v in range(n):
            if can(-1, v, y):
                B[(-1, v, y)] = beam
    for y in tops:
        for v in range(n):
            if existing(0, v, y) == trim:
                B[(0, v, y)] = beam
    for v in piers:
        for y in range(1, H + 1):
            for u in (-1, 0):
                if can(u, v, y) and (u, v, y) not in B:
                    B[(u, v, y)] = post
    for f in range(len(hs)):  # braces in blank panels between consecutive posts
        y_lo, y_hi = floors[f] + 1, (tops[f] if f < len(hs) - 1 else H) - 1
        rows = y_hi - y_lo + 1
        if rows < 3:
            continue
        for i, (a, b) in enumerate(zip(piers, piers[1:])):
            wdt = b - a - 1
            if wdt < 2 or b - a > 9:
                continue
            cells = []
            for k in range(rows):
                col = round(k * (wdt - 1) / (rows - 1))
                cells.append((a + 1 + (col if (i + f) % 2 == 0 else wdt - 1 - col), y_lo + k))
            good = [(v, y) for v, y in cells if existing(-1, v, y) == wall2]
            if len(good) >= 0.7 * rows:
                for v, y in good:
                    B[(-1, v, y)] = brace
    return B


LINE = {"pipe_rack": pipe_rack, "timber_frame": timber_frame}


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
        for cx, cz in ((x0 - 1, z0 - 1), (x1 + 1, z0 - 1), (x0 - 1, z1 + 1), (x1 + 1, z1 + 1)):  # upturned corners
            B[(cx, y + 1, cz)] = slab + "[type=bottom]"  # sits on the corner block: no floating tips
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


def water_tank(K: dict, w: int, d: int, size: int = 0, corner: str = "nw", **_) -> dict:
    """Wooden water tank on four stilt legs near a deck corner (centre 5 in from the corner, never the middle): spruce
    barrel body (5 wide disc) with industrial-iron bands, a plus of fence cross bracing between the legs, a ladder up
    the deck-facing side, a conical spruce cap with a lightning rod. size = total height (6-14, default 9)."""
    if w < 11 or d < 11:
        return {}
    H = max(6, min(14, size or 9))
    cx = 5 if "w" in corner else w - 6
    cz = 5 if "n" in corner else d - 6
    legs, bh = 3, H - 5
    planks, logs = "minecraft:spruce_planks", "minecraft:spruce_log"
    band = _blk({"x": "create:industrial_iron_block"}, "x", "minecraft:iron_block")
    B = {}
    for a, c in ((2, 0), (-2, 0), (0, 2), (0, -2)):  # stilts
        for y in range(legs):
            B[(cx + a, y, cz + c)] = "minecraft:stripped_spruce_log[axis=y]"
    for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)):  # plus-shaped bracing between the legs
        B[(cx + a, 1, cz + c)] = "minecraft:spruce_fence"
    disc = _disc(2)
    bands = {legs + 1, legs + bh - 2} if bh >= 6 else {legs + bh // 2}  # iron hoops (one band on a short barrel)
    for y in range(legs, legs + bh):
        edge = y in (legs, legs + bh - 1)
        for a, c in disc:
            if edge or max(abs(a), abs(c)) == 2:
                if y in bands:
                    B[(cx + a, y, cz + c)] = band
                else:
                    B[(cx + a, y, cz + c)] = logs if (a, c) in ((2, 0), (-2, 0), (0, 2), (0, -2)) else planks
    top = legs + bh
    for a, c in disc:
        B[(cx + a, top, cz + c)] = "minecraft:spruce_slab[type=bottom]"
    B[(cx, top + 1, cz)] = planks
    for (a, c), f in (((1, 0), "west"), ((-1, 0), "east"), ((0, 1), "north"), ((0, -1), "south")):
        B[(cx + a, top + 1, cz + c)] = f"minecraft:spruce_stairs[facing={f},half=bottom]"
    B[(cx, top + 2, cz)] = "minecraft:lightning_rod"
    lx, lf = (cx + 3, "east") if "w" in corner else (cx - 3, "west")  # ladder faces the deck, leans on leg then body
    for y in range(legs + bh):
        B[(lx, y, cz)] = f"minecraft:ladder[facing={lf}]"
    return B


def landing_pad(K: dict, w: int, d: int, gap: str = "s", **_) -> dict:
    """Round helipad filling most of the deck (radius = half the short side - 3, capped 9): light-grey concrete disc,
    yellow edge ring with a kit light every 3rd ring cell, a white H, a low rail round the ring with a 3-wide gap on
    the `gap` side for access, and an iron antenna / windsock post just outside the ring on the north side."""
    if min(w, d) < 13:
        return {}
    cx, cz = w // 2, d // 2
    R = min(9, min(cx, w - 1 - cx, cz, d - 1 - cz) - 3)
    if R < 4:
        return {}
    glow = K.get("glow") if (K.get("glow") or "").startswith("minecraft:") else "minecraft:shroomlight"
    rail = _blk(K, "rail", "minecraft:iron_bars")
    B = {}
    ring = []
    for a in range(-R - 1, R + 2):
        for c in range(-R - 1, R + 2):
            r = math.hypot(a, c)
            if r <= R + 0.3:
                if r > R - 0.7:
                    ring.append((math.atan2(c, a), a, c))
                else:
                    B[(cx + a, 0, cz + c)] = "minecraft:light_gray_concrete"
    sx, sz = (2, 3) if R >= 6 else (1, 2)
    for c in range(-sz, sz + 1):  # the H
        for a in (-sx, sx):
            B[(cx + a, 0, cz + c)] = "minecraft:white_concrete"
    for a in range(-sx, sx + 1):
        B[(cx + a, 0, cz)] = "minecraft:white_concrete"
    gx, gz = {"s": (0, 1), "n": (0, -1), "e": (1, 0), "w": (-1, 0)}.get(gap, (0, 1))
    for i, (_, a, c) in enumerate(sorted(ring)):
        B[(cx + a, 0, cz + c)] = glow if i % 3 == 0 else "minecraft:yellow_concrete"
        in_gap = (gz and c * gz > 0 and abs(a) <= 1) or (gx and a * gx > 0 and abs(c) <= 1)
        if not in_gap:
            B[(cx + a, 1, cz + c)] = rail
    px, pz = cx, cz - R - 1
    for y in range(0, 6):
        B[(px, y, pz)] = "minecraft:iron_bars"
    for k, wool in enumerate(("orange_wool", "white_wool", "orange_wool"), 1):
        B[(px + k, 5, pz)] = "minecraft:" + wool
    B[(px, 6, pz)] = "minecraft:lantern[hanging=false]"
    return B


def crane(K: dict, w: int, d: int, size: int = 0, **_) -> dict:
    """Tower crane on the deck, mast near the west end (x=6..7, z=5..6): 2x2 yellow-collared iron-bar lattice mast,
    grey slew ring, a glass operator cab on the north side, a long lattice jib running east with a trolley, chain and
    hopper hook, a short counter-jib running west with a 2x2x2 concrete counterweight, a cathead on top with pendant
    lines to both jib ends and a lantern. size = mast height (8-30, default 14). Needs a deck >= 16 x 11."""
    mx, mz = 6, 5
    H = max(8, min(30, size or 14))
    J = min(14, w - 10)
    if J < 6 or d < 11:
        return {}
    C = 4
    yel, grey = "minecraft:yellow_concrete", "minecraft:gray_concrete"
    bars = "minecraft:iron_bars"
    B = {}
    for y in range(H):  # mast
        for a in (0, 1):
            for c in (0, 1):
                B[(mx + a, y, mz + c)] = yel if y % 3 == 0 else bars
    for a in (0, 1):  # slew ring + cab (glass front, hood on top)
        for c in (0, 1):
            B[(mx + a, H, mz + c)] = grey
        B[(mx + a, H, mz - 1)] = grey
        B[(mx + a, H, mz - 2)] = grey
        B[(mx + a, H + 1, mz - 1)] = yel
        B[(mx + a, H + 1, mz - 2)] = "minecraft:glass"
        B[(mx + a, H + 2, mz - 1)] = "minecraft:smooth_stone_slab[type=bottom]"
        B[(mx + a, H + 2, mz - 2)] = "minecraft:smooth_stone_slab[type=bottom]"
    for x in range(mx - C, mx + J + 2):  # jib + counter-jib truss in the z=mz plane
        B[(x, H + 1, mz)] = bars
        B[(x, H + 3, mz)] = bars
        if (x - mx) % 3 == 0:
            B[(x, H + 2, mz)] = yel
    for y in range(H + 4, H + 8):  # cathead
        B[(mx, y, mz)] = yel
    for k in range(1, J + 2):  # pendants: shallow diagonals from the cathead top to both chord ends
        B[(mx + k, H + 7 - round(4 * k / (J + 1)), mz)] = bars
    for k in range(1, C + 1):
        B[(mx - k, H + 7 - round(4 * k / C), mz)] = bars
    for a in (0, 1):  # counterweight hung under the counter-jib end
        for c in (0, 1):
            for y in (H - 1, H):
                B[(mx - C + a, y, mz + c)] = grey if y == H else "minecraft:black_concrete"
    xt = mx + 2 + round(0.6 * J)  # trolley, hoist chain and hook
    B[(xt, H, mz)] = "minecraft:iron_block"
    n = min(H - 3, 8)
    for y in range(H - n, H):
        B[(xt, y, mz)] = "minecraft:chain[axis=y]"
    B[(xt, H - n - 1, mz)] = "minecraft:hopper[facing=down]"
    B[(mx, H + 8, mz)] = "minecraft:lantern[hanging=false]"
    return B


TOP = {"pagoda": pagoda, "water_tank": water_tank, "landing_pad": landing_pad, "crane": crane}

ALL = sorted(WALL) + sorted(LINE) + sorted(TOP)
