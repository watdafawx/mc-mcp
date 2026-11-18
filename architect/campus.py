"""Horizontal mod campuses with style-specific plans.

Spine uses enclosed galleries; radial, cloister, linear and garden terraces use
level outdoor promenades. Each wing retains its room program. Only landmark
rises above the low working ranges. Returned ghost origins are site offsets.
"""
from __future__ import annotations

import shapes  # noqa: F401  (loads massing in the right order)
import math
import random

import massing

SIZES = {"s": (19, 25), "m": (23, 31), "l": (29, 41)}  # wing width (along the gallery) x depth
GAP = 7  # courtyard between wings
GD = 11  # gallery depth
HUB = 33  # hub octagon size
STEPS = 2  # platform height; buildings stand on y=STEPS


# second roof shape per kit, used on every other wing so the skyline varies
ALT_ROOF = {"steampunk": "flat", "gothic": "flat", "hextech": "flat", "solarpunk": "flat", "station_white": "dome",
            "cyber_dark": "crown"}
# v15: 7 distinct forms per kit (a campus has <= 6-7 wings), so neighbouring wings never share a roof form
ROOF_CYCLE = {"steampunk": ["sawtooth", "gable_low", "mansard", "barrel", "hip_low", "flat", "gable_steep"],
              "gothic": ["gable_steep", "hip", "gable", "mansard", "gable_low", "hip_steep", "flat"],
              "hextech": ["hip_low", "mansard", "gable_low", "flat", "gable", "hip", "barrel"],
              "solarpunk": ["garden", "barrel", "hip_low", "gable_low", "garden", "sawtooth", "dome"],
              "station_white": ["barrel", "gable_low", "flat", "dome", "hip_low", "sawtooth", "gable"]}
# roof material per wing (cycled): every wing gets its own roof colour, the tower keeps the kit roof
# v16 steam: slate, oxidized teal, brick red, dark iron, then one copper-orange and two more cool/dark ones (was mostly copper)
ROOF_MATS = {"steampunk": ["minecraft:deepslate_tiles", "minecraft:oxidized_cut_copper", "minecraft:bricks",
                           "minecraft:cut_copper", "minecraft:polished_blackstone_bricks", "minecraft:red_nether_bricks",
                           "minecraft:weathered_cut_copper"],
             "gothic": ["minecraft:oxidized_cut_copper", "minecraft:deepslate_tiles", "minecraft:tuff_bricks",
                        "minecraft:weathered_cut_copper", "minecraft:blackstone", "minecraft:mossy_stone_bricks",
                        "minecraft:polished_deepslate"],
             "hextech": ["minecraft:deepslate_tiles", "minecraft:purple_terracotta", "minecraft:polished_blackstone_bricks",
                         "minecraft:blackstone", "minecraft:cyan_terracotta", "minecraft:purple_concrete", "minecraft:polished_deepslate"],
             "solarpunk": ["minecraft:moss_block", "create:cut_limestone_bricks", "minecraft:green_terracotta",
                           "minecraft:mossy_cobblestone", "minecraft:moss_block", "minecraft:terracotta", "minecraft:lime_terracotta"],
             "station_white": ["minecraft:white_concrete", "minecraft:light_gray_concrete", "minecraft:smooth_quartz",
                               "minecraft:orange_terracotta", "minecraft:gray_concrete", "minecraft:light_blue_concrete",
                               "minecraft:calcite"]}
TOWER_ROOF = {"steampunk": "mansard", "gothic": "mansard", "hextech": "crown", "solarpunk": "dome",
              "station_white": "dome", "cyber_dark": "crown"}


def _wood(K, kit):
    import interiors
    return K.get("wood") or interiors.WOOD.get(kit if isinstance(kit, str) else "", "oak")


CUR_KIT = [""]


def _tree(out, x, z, y, wood, rnd=0):
    h = 5 + rnd % 2
    thin = CUR_KIT[0] == "solarpunk"
    for dy in range(h):
        out.append([x, y + dy, z, f"minecraft:{wood}_log[axis=y]"])
    leaf = "minecraft:" + {"dark_oak": "dark_oak_leaves", "spruce": "spruce_leaves", "birch": "birch_leaves"}.get(
        wood, "oak_leaves") + "[persistent=true]"
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(h - 1 if thin else h - 2, h + (1 if thin else 2)):
                r = abs(dx) + abs(dz) + max(0, dy - h)
                if r <= (2 if thin else 3) and not (dx == 0 and dz == 0 and dy < h):
                    out.append([x + dx, y + dy, z + dz, leaf])


def _lamp(out, x, z, y, K):
    for dy in range(3):
        out.append([x, y + dy, z, K["rail"]])
    out.append([x, y + 3, z, K["glow"]])
    out.append([x, y + 4, z, K["trim"]])


# ------------------------------------------------------------------------------------------ yards
CROPS = ("minecraft:wheat[age=7]", "minecraft:carrots[age=7]", "minecraft:potatoes[age=7]", "minecraft:beetroots[age=3]")
FLOWERS = ("minecraft:poppy", "minecraft:dandelion", "minecraft:allium", "minecraft:oxeye_daisy", "minecraft:cornflower",
           "minecraft:azure_bluet", "minecraft:lily_of_the_valley")
HEDGE = "minecraft:azalea_leaves[persistent=true]"
BLOOM = "minecraft:flowering_azalea_leaves[persistent=true]"
# yard mix per kit: weights for farm, garden, machine yard, grove
YARD_MIX = {"steampunk": (2, 1, 3, 1), "rust_industrial": (1, 1, 4, 1), "solarpunk": (3, 4, 0, 3),
            "gothic": (2, 3, 1, 2), "hextech": (1, 3, 2, 1), "station_white": (1, 2, 3, 1), "cyber_dark": (1, 1, 4, 1),
            "ae_sky": (1, 2, 3, 1)}


def _farm(out, x0, z0, n, y, K, rnd):
    crop = CROPS[rnd % len(CROPS)]
    for dx in range(n):
        for dz in range(n):
            x, z = x0 + dx, z0 + dz
            if dx in (0, n - 1) or dz in (0, n - 1):
                out.append([x, y, z, K["trim"]])
            elif dz == n // 2:
                out.append([x, y, z, "minecraft:water"])  # irrigation channel
            else:
                out.append([x, y, z, "minecraft:farmland[moisture=7]"])
                out.append([x, y + 1, z, crop])
    out.append([x0, y + 1, z0, "minecraft:composter"])
    out.append([x0 + n - 1, y + 1, z0, "minecraft:hay_block[axis=y]"])
    out.append([x0 + n - 1, y + 1, z0 + n - 1, K["glow"]])


def _garden(out, x0, z0, n, y, K, rnd, wood):
    c = n // 2
    for dx in range(n):
        for dz in range(n):
            x, z = x0 + dx, z0 + dz
            ring = dx in (0, n - 1) or dz in (0, n - 1)
            path = dx == c or dz == c
            if ring and not path:
                out.append([x, y, z, HEDGE if (dx + dz + rnd) % 5 else BLOOM])
            elif not path:
                out.append([x, y, z, "minecraft:grass_block"])
                if (dx * 3 + dz * 5 + rnd) % 4 == 0:
                    out.append([x, y + 1, z, FLOWERS[(dx + dz * 2 + rnd) % len(FLOWERS)]])
    if rnd % 2:  # centre: a fountain or a small tree
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                out.append([x0 + c + dx, y, z0 + c + dz, K["trim"] if (dx or dz) else K["glow"]])
        out.append([x0 + c, y + 1, z0 + c, "minecraft:water"])
    else:
        _tree(out, x0 + c, z0 + c, y, wood, rnd)


def _tank(out, x, z, y, h=3):
    for dy in range(h):
        out.append([x, y + dy, z, f"create:fluid_tank[shape=window,bottom={str(dy == 0).lower()},"
                                  f"top={str(dy == h - 1).lower()}]"])


def _machine_yard(out, x0, z0, n, y, K, rnd):
    for dx in range(n):  # hazard-striped border, open in the middle of two sides for access
        for dz in range(n):
            if (dx in (0, n - 1) or dz in (0, n - 1)) and dz != n // 2:
                out.append([x0 + dx, y, z0 + dz, "chipped:hazard_yellow_concrete" if (dx + dz) % 2
                            else "minecraft:black_concrete"])
    tx = (x0 + 2, x0 + n - 3)  # two tanks with a pipe between them
    for t in tx:
        _tank(out, t, z0 + 2, y, 3 + rnd % 2)
    for x in range(tx[0] + 1, tx[1]):
        out.append([x, y + 2, z0 + 2, "minecraft:lightning_rod[facing=east]"])
    for dx in range(3):  # a machine block
        for dz in range(2):
            for dy in range(2):
                out.append([x0 + 3 + dx, y + dy, z0 + n - 4 + dz, K["detail"] if dy == 0 or dx != 1
                            else "create:industrial_iron_block"])
    out.append([x0 + 4, y + 2, z0 + n - 4, "minecraft:lightning_rod[facing=up]"])
    out.append([x0 + 1, y, z0 + n - 2, K["glow"]])


def _orchard(out, x0, z0, n, y, K, rnd, wood):
    for dx in range(n):
        for dz in range(n):
            out.append([x0 + dx, y, z0 + dz, "minecraft:grass_block"])
    for dx in range(2, n - 1, 4):
        for dz in range(2, n - 1, 4):
            for dy in range(1, 4):
                out.append([x0 + dx, y + dy, z0 + dz, f"minecraft:{wood}_log[axis=y]"])
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    out.append([x0 + dx + a, y + 4, z0 + dz + b, "minecraft:oak_leaves[persistent=true]" if (a or b) else BLOOM])
            out.append([x0 + dx, y + 5, z0 + dz, BLOOM])
    for dx in range(0, n, 4):
        out.append([x0 + dx, y + 1, z0, "minecraft:hay_block[axis=y]"])


def _pond(out, x0, z0, n, y, K, rnd, wood):
    c = n / 2 - 0.5
    for dx in range(n):
        for dz in range(n):
            d = math.hypot(dx - c, (dz - c) * 1.15)
            x, z = x0 + dx, z0 + dz
            if d <= c - 1.2:
                out.append([x, y, z, "minecraft:water"])
                if (dx * 5 + dz * 3 + rnd) % 6 == 0:
                    out.append([x, y + 1, z, "minecraft:lily_pad"])
            elif d <= c - 0.2:
                out.append([x, y, z, K["base"]])
            else:
                out.append([x, y, z, "minecraft:grass_block"])
                if (dx * 3 + dz * 7 + rnd) % 4 == 0:
                    out.append([x, y + 1, z, FLOWERS[(dx + dz + rnd) % len(FLOWERS)]])
    out.append([x0 + 1, y + 1, z0 + 1, K["glow"]])
    _tree(out, x0 + 1, z0 + n - 2, y + 1, wood, rnd)


def _plaza(out, x0, z0, n, y, K, rnd, wood):
    """Paved square with a statue (plinth, column, lit crown), benches and corner lamps."""
    c = n // 2
    for dx in range(n):
        for dz in range(n):
            m = max(abs(dx - c), abs(dz - c))  # calm concentric paving: plain field, two bands
            out.append([x0 + dx, y, z0 + dz, K["wall2"] if m in (c, 3) else K["base"]])
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            out.append([x0 + c + dx, y + 1, z0 + c + dz, K["trim"]])
    for dy in range(2, 6):
        out.append([x0 + c, y + dy, z0 + c, K.get("pillar", K["trim"])])
    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.append([x0 + c + a, y + 4, z0 + c + b, K["trim"]])
    out.append([x0 + c, y + 6, z0 + c, K["glow"]])
    out.append([x0 + c, y + 7, z0 + c, K["antenna"]])
    if n >= 11:
        for sx in (1, n - 2):
            for sz in (1, n - 2):
                _lamp(out, x0 + sx, z0 + sz, y + 1, K)
        for dx in (c - 2, c + 2):
            out.append([x0 + dx, y + 1, z0 + 1, f"minecraft:{wood}_stairs[facing=south]"])
            out.append([x0 + dx, y + 1, z0 + n - 2, f"minecraft:{wood}_stairs[facing=north]"])


MARKET = ("red", "yellow", "white", "blue", "orange", "green")


def _market(out, x0, z0, n, y, K, rnd, wood):
    for dx in range(n):
        for dz in range(n):
            out.append([x0 + dx, y, z0 + dz, K["wall2"] if dx == n // 2 or dz == n // 2 else "minecraft:coarse_dirt"])
    k = 0
    for sx, sz in ((1, 1), (n - 4, 1), (1, n - 4), (n - 4, n - 4)):
        col = MARKET[(rnd + k) % len(MARKET)]
        k += 1
        for a, b in ((0, 0), (2, 0), (0, 2), (2, 2)):
            for dy in range(1, 3):
                out.append([x0 + sx + a, y + dy, z0 + sz + b, f"minecraft:{wood}_fence"])
        for a in range(3):
            for b in range(3):
                out.append([x0 + sx + a, y + 3, z0 + sz + b, f"minecraft:{col}_wool" if (a + b) % 2 else "minecraft:white_wool"])
        out.append([x0 + sx + 1, y + 1, z0 + sz + 1, "minecraft:barrel[facing=up]"])
        out.append([x0 + sx + 1, y + 2, z0 + sz + 1, "minecraft:lantern"])


def _ramp(out, x0, z0, n, y, K, rnd, wood):
    """Station: a white stair ramp with glass balustrades rising to a viewing deck."""
    for dx in range(n):
        for dz in range(n):
            out.append([x0 + dx, y, z0 + dz, K["base"]])
    c = n // 2
    rise = min(7, n - 5)
    for i in range(rise):
        x = x0 + 2 + i
        for dz in range(c - 2, c + 3):
            for yy in range(y + 1, y + 1 + i):
                out.append([x, yy, z0 + dz, K["wall"]])
            out.append([x, y + 1 + i, z0 + dz, "minecraft:quartz_stairs[facing=east]"])
        for dz in (c - 2, c + 2):
            out.append([x, y + 2 + i, z0 + dz, K["glass"]])
            out.append([x, y + 3 + i, z0 + dz, K["glass"]])
    for dx in range(2 + rise, n - 1):
        for dz in range(c - 2, c + 3):
            for yy in range(y + 1, y + 1 + rise):
                out.append([x0 + dx, yy, z0 + dz, K["wall"]])
            out.append([x0 + dx, y + 1 + rise, z0 + dz, K["base"]])
            if dz in (c - 2, c + 2) or dx == n - 2:
                out.append([x0 + dx, y + 2 + rise, z0 + dz, K["glass"]])
    out.append([x0 + n - 3, y + 2 + rise, z0 + c, K["glow"]])


YARD_FUNCS = {"farm": lambda o, x, z, n, y, K, r, w: _farm(o, x, z, n, y, K, r), "garden": _garden,
              "machine": lambda o, x, z, n, y, K, r, w: _machine_yard(o, x, z, n, y, K, r), "orchard": _orchard, "pond": _pond,
              "plaza": _plaza, "market": _market, "ramp": _ramp}
YARD_BAG = {  # weighted yard kinds per kit: variety instead of 13x13 clones
    "steampunk": ("machine", "machine", "market", "plaza", "farm", "garden", "pond"),
    "hextech": ("plaza", "garden", "pond", "garden", "orchard", "plaza", "pond"),
    "gothic": ("orchard", "garden", "pond", "plaza", "farm", "market", "garden"),
    "station_white": ("machine", "plaza", "ramp", "machine", "pond", "market", "garden"),
    "solarpunk": ("orchard", "farm", "pond", "garden", "market", "orchard", "plaza"),
}


def _small_yard(out, x0, z0, n, y, K, rnd, wood):
    """7x7 filler: grove, pocket plaza or flower bed."""
    kind = rnd % 3
    if kind == 1:
        _plaza(out, x0, z0, n, y, K, rnd, wood)
        return
    for dx in range(n):
        for dz in range(n):
            out.append([x0 + dx, y, z0 + dz, "minecraft:grass_block"])
            if kind == 2 and (dx * 3 + dz * 5) % 5 == 0 and 0 < dx < n - 1 and 0 < dz < n - 1:
                out.append([x0 + dx, y + 1, z0 + dz, FLOWERS[(dx + dz * 2 + rnd) % len(FLOWERS)]])
    if kind == 0:
        _tree(out, x0 + n // 2, z0 + n // 2, y + 1, wood, rnd)
        out.append([x0 + 1, y + 1, z0 + 1, K["glow"]])


def _plan_yards(out, x0, x1, zlo, zhi, y, used, K, kit, wood, seed):
    """Fill free space with varied yards: 13x13 on a grid first, then 7x7 fillers in what is left. Returns the set of
    path cells (a one-wide ring round every yard, joining into a network)."""
    bag = YARD_BAG.get(kit if isinstance(kit, str) else "", ("garden", "pond", "plaza", "orchard", "machine"))
    taken = set(used)
    placed = []
    for n, step, small in ((13, 14, False), (7, 8, True)):
        k = 0
        for gx in range(x0 + 2, x1 - n + 1, step):
            for gz in range(zlo + 2, zhi - n + 1, step):
                if any((a, b) in taken for a in range(gx - 1, gx + n + 1) for b in range(gz - 1, gz + n + 1)):
                    continue
                r = (gx * 7 + gz * 13 + seed) % 97
                if small:
                    _small_yard(out, gx, gz, n, y, K, r, wood)
                else:
                    YARD_FUNCS[bag[(r + k) % len(bag)]](out, gx, gz, n, y, K, r, wood)
                k += 1
                taken |= {(a, b) for a in range(gx, gx + n) for b in range(gz, gz + n)}
                placed.append((gx, gz, n))
    path = set()
    for gx, gz, n in placed:
        for i in range(-1, n + 1):
            path |= {(gx + i, gz - 1), (gx + i, gz + n), (gx - 1, gz + i), (gx + n, gz + i)}
    return {c for c in path if c not in used}


def _yards(out, occ, W, D, y, K, kit, wood, seed):
    """Legacy spine: fill the free platform with varied yards. Returns the number placed."""
    before = len(out)
    _plan_yards(out, 3, W - 2, 3, D - 2, y, occ, K, kit, wood, seed)
    return len({(b[0], b[2]) for b in out[before:]}) // 150


# ------------------------------------------------------------------------------------------ style features
def _gear(out, cx, cy, z, r, K):
    """Decorative gear disc on a south facade: rim + teeth in trim, hub + spokes in detail."""
    import math as _m
    for dx in range(-r - 1, r + 2):
        for dy in range(-r - 1, r + 2):
            d = _m.hypot(dx, dy)
            ang = _m.degrees(_m.atan2(dy, dx)) % 45
            b = None
            if r - 0.6 <= d <= r + 0.4:
                b = K["trim"]
            elif r + 0.4 < d <= r + 1.4 and ang < 15:
                b = K["trim"]  # teeth
            elif d < 1.5 or ((dx == 0 or dy == 0 or abs(dx) == abs(dy)) and d < r):
                b = K["detail"]
            if b:
                out.append([cx + dx, cy + dy, z, b])


def _cog(out, a, cy, fixed, r, axis, sign, rim, teeth, spoke, hub, thick=2, spokes=8):
    """Big cogwheel flat on a wall: centre (a, cy) in the wall plane, wall layer index `fixed` along `axis`
    ('x' = wheel in the z-y plane on an east/west face, 'z' = wheel in the x-y plane on a north/south face),
    `thick` layers growing outwards (sign +1/-1). Open between the spokes so the wall shows through."""
    import math as _m
    nt = max(6, int(r * 2))  # teeth count
    for du in range(-r - 2, r + 3):
        for dv in range(-r - 2, r + 3):
            d = _m.hypot(du, dv)
            ang = _m.degrees(_m.atan2(dv, du)) % 360
            b = None
            if d <= 1.9:
                b = hub
            elif r - 0.8 <= d <= r + 0.3:
                b = rim
            elif r + 0.3 < d <= r + 1.5 and (ang % (360 / nt)) < (180 / nt):
                b = teeth
            elif d < r - 0.8:
                step = 360 / spokes
                near = min(ang % step, step - ang % step)
                if near * _m.pi / 180 * d < 0.75:
                    b = spoke
            if not b:
                continue
            for k in range(thick):
                f = fixed + sign * k
                out.append([f, cy + dv, a + du, b] if axis == "x" else [a + du, cy + dv, f, b])


PIPE = "minecraft:waxed_oxidized_copper"  # teal pipe: contrasts with the dark brick walls and the orange copper trim
PIPE_FLANGE = "minecraft:copper_block"        # bright orange collars


def _pipes(out, x0, z0, w, d, H, y, sides, K, i):
    """Copper pipe runs along the wall faces of a wing: one horizontal run (2 blocks thick, teal oxidized copper) near
    the eaves, risers to the ground, bright collars every 6 blocks with a lit joint. Everything sits in the
    footprint-edge layer, against the wall."""
    pipe, flange, lit = PIPE, PIPE_FLANGE, K["glow"]
    ytop = y + max(4, H - 4 - (i % 2))
    ylow = y + 3 + (i % 2)
    for sd in sides:
        if sd in "ns":
            zz = z0 if sd == "n" else z0 + d - 1
            run = [(x, zz) for x in range(x0 + 1, x0 + w - 1)]
        else:
            xx = x0 if sd == "w" else x0 + w - 1
            run = [(xx, z) for z in range(z0 + 1, z0 + d - 1)]
        for n, (px, pz) in enumerate(run):
            col = n % 6 == 3
            out.append([px, ytop, pz, flange if col else pipe])
            out.append([px, ytop + 1, pz, flange if col else pipe])
            if col:
                out.append([px, ytop + 2, pz, flange])
                out.append([px, ytop - 1, pz, flange])
                if n % 12 == 3:
                    out.append([px, ytop + 3, pz, lit])
        if sd == sides[0] or (i % 2 and sd == sides[-1]):
            for frac in (0.25, 0.75):
                px, pz = run[int(len(run) * frac)]
                for yy in range(y + 1, ytop):
                    out.append([px, yy, pz, flange if (yy - y) % 6 == 0 else pipe])
        if len(run) > 20:  # a second, lower run on the long faces
            for n, (px, pz) in enumerate(run[3:-3]):
                out.append([px, ylow, pz, flange if n % 8 == 4 else pipe])
                out.append([px, ylow + 1, pz, flange if n % 8 == 4 else pipe])


def _chimney(out, x, z, y0, h, K):
    for dy in range(h):
        for a in (0, 1):
            for b in (0, 1):
                out.append([x + a, y0 + dy, z + b, K["wall"] if dy % 5 else K["trim"]])
    for a in (0, 1):
        for b in (0, 1):
            out.append([x + a, y0 + h, z + b, "minecraft:copper_grate"])
    out.append([x, y0 + h + 1, z, "minecraft:campfire[lit=true]"])


def _buttresses(out, x0, z0, w, d, H, y, K, sides):
    """Gothic flying buttresses: a tall pier against the wall (pinnacle on top), a lower outer pier three blocks out
    and a stepped rib arching from the outer pier up to the wall pier. Spaced every 6 blocks."""
    for side in sides:
        rng = range(x0 + 4, x0 + w - 3, 6) if side in "ns" else range(z0 + 4, z0 + d - 3, 6)
        for t in rng:
            def at(k, dy):
                return {"n": (t, z0 - k), "s": (t, z0 + d - 1 + k), "w": (x0 - k, t), "e": (x0 + w - 1 + k, t)}[side] + (y + dy,)
            hp = max(5, H // 2)  # outer pier height
            for dy in range(H - 2):  # wall pier, full height
                x, z, yy = at(1, dy)
                out.append([x, yy, z, K["trim"] if dy % 4 else K["wall"]])
            for dy in range(hp):  # outer pier
                x, z, yy = at(3, dy)
                out.append([x, yy, z, K["trim"] if dy % 4 else K["wall"]])
            for k, dy in ((3, hp), (2, hp + 1), (2, hp + 2), (1, hp + 3)):  # the flying rib, rising toward the wall
                x, z, yy = at(k, dy)
                out.append([x, yy, z, K["trim"]])
            for k, dy in ((2, hp - 1), (2, hp)):  # soffit under the rib
                x, z, yy = at(k, dy)
                out.append([x, yy, z, K["wall"]])
            x, z, yy = at(1, H - 2)
            out.append([x, yy, z, K["trim"]])
            out.append([x, yy + 1, z, K["antenna"]])
            out.append([x, yy + 2, z, K["tip"]])
            x, z, yy = at(3, hp)  # small pinnacle on the outer pier
            out.append([x, yy, z, K["antenna"]])
            out.append([x, yy + 1, z, K["tip"]])


def _wing_bays(x0, z0, w, d, y, fh, H, door, K, kit, seed, i):
    """Projecting bays, porches and frontispieces on a wing's facades, in absolute site coordinates at base level y.
    Door side: an entrance frontispiece (pediment block + pilasters, flush to the facade, clear of the 5-wide hall).
    Other sides: one or two 5-wide, 2-deep projecting bays (oriel boxes, full ground-floor height, glazed front,
    corbelled cap), placed off-centre so no two wings repeat."""
    out = []
    glass = K["glass"]
    pier = K.get("pillar", K["trim"])
    sides = [sd for sd in "nsew" if sd != door]
    # frontispiece above the door: pilasters + pediment block just proud of the facade
    off = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}[door]
    mx, mz = x0 + w // 2, z0 + d // 2
    for t in range(-4, 5):
        if door in "ns":
            x, z = mx + t, (z0 - 1 if door == "n" else z0 + d)
        else:
            x, z = (x0 - 1 if door == "w" else x0 + w), mz + t
        edge = abs(t) == 4
        top = min(H - 1, fh + 1)
        if edge:
            for dy in range(1, top + 1):
                out.append([x, y + dy, z, pier])
        if abs(t) <= 4:
            for dy in (top, top + 1):
                out.append([x, y + dy, z, K["trim"]])
            if abs(t) <= 2:
                out.append([x, y + top + 2, z, K["trim"]])
            if t == 0:
                out.append([x, y + top + 3, z, K.get("band", K["glow"])])
    for n_, sd in enumerate(sides):
        long = d if sd in "ew" else w
        if long < 17:
            continue
        for c in ((long // 2 + (3 if (seed + n_) % 2 else -3)), ) if long < 29 else ((long // 3), (2 * long // 3) + 1):
            hb = min(fh - 1, 7 + (seed + n_) % 3)
            for a in range(-2, 3):
                for k in (1, 2):
                    if sd in "ns":
                        x, z = x0 + c + a, (z0 - k if sd == "n" else z0 + d - 1 + k)
                        wall = (x0 + c + a, z0 if sd == "n" else z0 + d - 1)
                    else:
                        x, z = (x0 - k if sd == "w" else x0 + w - 1 + k), z0 + c + a
                        wall = (x0 if sd == "w" else x0 + w - 1, z0 + c + a)
                    if k == 1 and abs(a) == 2:
                        continue
                    for dy in range(1, hb + 1):
                        edge = (abs(a) == 2 and k == 2) or (k == 2 and abs(a) == 2)
                        front = k == 2
                        if front and abs(a) == 2:
                            blk = pier
                        elif front and 2 <= dy <= hb - 1:
                            blk = glass
                        elif front:
                            blk = K["wall2"] if dy == 1 else K["trim"]
                        elif abs(a) == 1 and dy % 4 == 0:
                            blk = K["trim"]
                        else:
                            continue
                        out.append([x, y + dy, z, blk])
                    if k == 2 or abs(a) < 2:  # corbelled cap, one wider than the box
                        out.append([x, y + hb + 1, z, K["trim"]])
            # side returns joining the front to the wall
            for dy in range(1, hb + 1):
                for a in (-2, 2):
                    if sd in "ns":
                        x, z = x0 + c + a, (z0 - 1 if sd == "n" else z0 + d)
                    else:
                        x, z = (x0 - 1 if sd == "w" else x0 + w), z0 + c + a
                    out.append([x, y + dy, z, pier if dy % 3 else K["trim"]])
    return out


def _greenwall(out, x0, z0, w, d, H, y, sides, rnd):
    """Vertical greenery: leaf curtains hanging down the outer faces, staggered, with flowering patches."""
    for side in sides:
        rng = range(x0 + 1, x0 + w - 1) if side in "ns" else range(z0 + 1, z0 + d - 1)
        for t in rng:
            if (t + rnd) % 5 in (0, 1):
                continue  # keep some window bays readable
            length = 3 + (t * 7 + rnd) % max(1, H - 2)
            x, z = {"n": (t, z0 - 1), "s": (t, z0 + d), "w": (x0 - 1, t), "e": (x0 + w, t)}[side]
            for dy in range(length):
                out.append([x, y + H - dy, z, BLOOM if (t + dy) % 7 == 0 else HEDGE])


def _ring(out, cx, cz, R, y, K, skip):
    """Sci-fi halo: a 2-wide ring deck with a lit underside on four pylons."""
    import math as _m
    for x in range(cx - R - 2, cx + R + 3):
        for z in range(cz - R - 2, cz + R + 3):
            dd = _m.hypot(x - cx, z - cz)
            if R - 1 <= dd <= R + 0.9 and (x, z) not in skip:
                out.append([x, y, z, K["wall"]])
                out.append([x, y - 1, z, K["glow"] if (x + z) % 3 == 0 else K["trim"]])
                if dd > R + 0.2:
                    out.append([x, y + 1, z, K["rail"]])
    for a in (45, 135, 225, 315):
        px = cx + round(R * _m.cos(_m.radians(a)))
        pz = cz + round(R * _m.sin(_m.radians(a)))
        if (px, pz) in skip:
            continue
        for dy in range(STEPS, y - 1):
            out.append([px, dy, pz, K["trim"] if dy % 4 else K.get("band", K["glow"])])


def _tower_trim(K, cx, cz, r, r2, y, hs1):
    """Silhouette for the landmark: corbelled balcony rings (base roof, mid band, upper stage), four pinnacles on
    the base terrace and flying ribs from them to the upper stage."""
    import math as _m
    out = []

    def ring(R, yy, rail=True, glow=False):
        for x in range(cx - R - 1, cx + R + 2):
            for z in range(cz - R - 1, cz + R + 2):
                if R - 0.5 < _m.hypot(x - cx, z - cz) <= R + 0.5:
                    out.append([x, yy, z, K.get("band", K["glow"]) if glow and (x + z) % 4 == 0 else K["trim"]])
                    if rail:
                        out.append([x, yy + 1, z, K["rail"]])
    H1 = sum(hs1) + 1
    ring(r + 1, y + H1, rail=True)  # terrace balcony
    ring(r + 1, y + H1 - 1, rail=False, glow=True)  # corbel band under it
    ring(r + 1, y + hs1[0] + 1, rail=True)  # balcony above the ground hall
    ring(r2 + 1, y + H1 + 1 + 12, rail=True)  # upper-stage balcony
    for a in (45, 135, 225, 315):  # pinnacles on the terrace
        px = cx + round((r - 1) * _m.cos(_m.radians(a)))
        pz = cz + round((r - 1) * _m.sin(_m.radians(a)))
        for dy in range(1, 7):
            out.append([px, y + H1 + dy, pz, K.get("pillar", K["trim"]) if dy < 5 else K["trim"]])
        out.append([px, y + H1 + 7, pz, K["antenna"]])
        out.append([px, y + H1 + 8, pz, K["tip"]])
    return out


def _legacy_build(kit: str = "hextech", wings: list | None = None, home: bool = True, landmark: str = "tower",
          roles: dict | None = None, seed: int = 1) -> list:
    K = massing._kit(kit, roles)
    K_style = kit if isinstance(kit, str) else ""
    wings = list(wings or [])
    if home:
        wings.insert(0, {"name": "home", "rooms": ["living", "living", "workshop", "storage"], "size": "m",
                         "floor_h": 6})
    if not wings:
        wings = [{"name": "machines", "rooms": ["mod_room", "expansion"]}]
    sizes = [SIZES.get(str(w.get("size", "m"))[:1], SIZES["m"]) for w in wings]
    ww = max(s[0] for s in sizes)
    pitch = ww + GAP
    # slots: east-north, east-south, west-north, west-south, then the next ring out
    slots = []
    for i in range(len(wings)):
        k, r = divmod(i, 4)
        slots.append(("e" if r < 2 else "w", "n" if r % 2 == 0 else "s", k))
    ke = max([k for s, _, k in slots if s == "e"], default=-1) + 1
    kw = max([k for s, _, k in slots if s == "w"], default=-1) + 1
    depth_n = max([sizes[i][1] for i, s in enumerate(slots) if s[1] == "n"], default=0)
    depth_s = max([sizes[i][1] for i, s in enumerate(slots) if s[1] == "s"], default=0)
    margin = 8
    # site frame: x from 0, gallery z band in the middle
    west = margin + kw * pitch
    hx0 = west + (GAP if kw else 0)  # hub min x
    hx1 = hx0 + HUB
    east = hx1 + (GAP if ke else 0) + ke * pitch
    tower_d = 16 if landmark == "tower" else 0
    gz = margin + max(depth_n, HUB // 2 - GD // 2 + tower_d)  # gallery min z
    hz0 = gz + GD // 2 - HUB // 2
    W = east + margin
    D = gz + GD + max(depth_s, HUB // 2 - GD // 2 + 12) + margin
    y = STEPS  # building level
    ghosts = []

    def add(gid, origin, blocks):
        ghosts.append({"id": gid, "origin": origin, "blocks": blocks})

    add("platform", [0, 0, 0], massing.platform("rect", w=W, d=D, kit=kit, roles=roles, steps=STEPS, rail=True))

    # wings, and the gallery doors that face them
    gdoors = {"w": [], "e": []}  # (side n|s, x in site coords)
    grounds = []
    foot = []  # wing footprints: (x0, z0, w, d, height, side, roof)
    bays_legacy = []
    for i, (wing, (side_ew, side_ns, k)) in enumerate(zip(wings, slots)):
        w_, d_ = sizes[i]
        x0 = hx1 + GAP + k * pitch if side_ew == "e" else hx0 - GAP - ww - k * pitch
        x0 += (ww - w_) // 2
        if side_ns == "n":
            z0 = gz - d_ + 1  # outer rings shared with the gallery
        else:
            z0 = gz + GD - 1
        rooms = wing.get("rooms") or ["mod_room", "expansion"]
        fh = int(wing.get("floor_h") or (9 + 2 * ((i + seed) % 3)))  # 9 / 11 / 13: varied skyline
        floors = int(wing.get("floors") or 1)
        hs = [fh] + [6] * (floors - 1)
        prog = [rooms] + [wing.get("upper") or ["expansion"]] * (floors - 1)
        roof = _roof_for(wing, K_style, i)
        wing_roles = dict(roles or {})
        wing_roles.update(wing.get("roles") or {})
        wing_roles.setdefault("glass", "minecraft:" + ("cyan", "light_blue", "gray")[i % 3] + "_stained_glass")
        wing_roles.setdefault("wall2", (K["wall2"], K["base"], K["wall"])[i % 3])
        _mats = ROOF_MATS.get(K_style)
        if _mats and "roof" not in (wing.get("roles") or {}):  # v16: a model-wide roles.roof must not flatten every wing to one hue
            wing_roles["roof"] = _mats[i % len(_mats)]
        blocks = massing.structure("rect", w=w_, d=d_, floor_hs=hs, program=prog, kit=kit, roles=wing_roles,
                                   entrances=["s" if side_ns == "n" else "n"], roof=roof, bay=4+i%3, windows=_windows(K_style, i),
                                   accent_floor=0, seed=seed + i, core="auto", rhythm=1 + i % 3, finial=1)
        add("wing_" + str(wing.get("name", i)), [x0, y, z0], blocks)
        bays_legacy += _wing_bays(x0, z0, w_, d_, y, hs[0], sum(hs) + 1, "s" if side_ns == "n" else "n", K, kit, seed + i, i)
        foot.append((x0, z0, w_, d_, sum(hs) + 1, side_ns, roof or massing.ROOF_DEFAULT.get(K_style, "flat")))
        gdoors[side_ew].append((side_ns, x0 + w_ // 2))
        # courtyard trees and lamps beside the wing, on the far end from the gallery
        zt = z0 + 4 if side_ns == "n" else z0 + d_ - 5
        for xt in (x0 - GAP // 2 - 1, x0 + w_ + GAP // 2):
            _tree(grounds, xt, zt, y, _wood(K, kit), seed + i)
            _lamp(grounds, xt, zt + (6 if side_ns == "n" else -6), y, K)

    # gallery: west and east halves, each sharing an outer ring with the hub
    for half, x0, x1 in (("w", margin, hx0), ("e", hx1 - 1, W - margin)):
        if x1 - x0 < 8:
            continue
        ents = ["e" if half == "w" else "w", half]  # into the hub, and the outside end
        ents += [f"{s}@{x - x0}" for s, x in gdoors[half]]
        blocks = massing.structure("rect", w=x1 - x0 + 1, d=GD, floor_hs=[7], program=["hall"], kit=kit,
                                   roles=roles, entrances=ents, roof="flat", windows="band", accent_floor=0,
                                   roof_details=0, antennas=0, seed=seed + 50)
        add("gallery_" + half, [x0, y, gz], blocks)

    # hub: the big showcase hall (for the AE2 controller / quantum computer) under a dome
    hub = massing.structure("octagon", w=HUB, d=HUB, c=9, floor_hs=[12], program=["hall"], kit=kit, roles=roles,
                            entrances=["e", "w", "s"] + (["n"] if landmark == "tower" else []), roof="dome",
                            windows="grid", accent_floor=0, seed=seed + 60)
    add("hub", [hx0, y, hz0], hub)

    # landmark: the one tall volume, north of the hub, a lift inside
    tcx, tcz, r = hx0 + HUB // 2, hz0 - 5, 7
    if landmark == "tower":
        for gid, org, bl in _tower(K, kit, roles, seed, tcx, tcz, y):
            add(gid, org, bl)
    elif landmark == "spire":
        add("spire", [hx0 + HUB // 2 - 4, y, hz0 - 10], massing.spire(h=45, base=9, kit=kit, roles=roles))

    # front plaza south of the hub: lamp avenue and two trees
    cx = hx0 + HUB // 2
    pz0 = hz0 + HUB
    for j in range(0, D - margin - pz0, 5):
        for sx in (-5, 5):
            _lamp(grounds, cx + sx, pz0 + 2 + j, y, K)
    for sx in (-10, 10):
        _tree(grounds, cx + sx, pz0 + 5, y, _wood(K, kit), seed)
    # yards on the free platform: buildings + clearance, the gallery, hub, tower, front avenue, grounds are taken
    occ = set()

    def take(x0, z0, w, d, pad=2):
        occ.update((x, z) for x in range(x0 - pad, x0 + w + pad) for z in range(z0 - pad, z0 + d + pad))
    for (x0, z0, w_, d_, *_rest) in foot:
        take(x0, z0, w_, d_, 4 if K_style in ("gothic", "solarpunk") else 2)
    take(margin, gz, W - 2 * margin, GD)
    take(hx0, hz0, HUB, HUB)
    if landmark != "none":
        take(tcx - r, tcz - r, 2 * r + 1, 2 * r + 1)
    take(cx - 7, pz0, 15, D - pz0)
    occ.update((b[0] + dx, b[2] + dz) for b in grounds for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    occ_halls = set()
    yards = []
    _yards(yards, occ, W, D, y, K, kit, _wood(K, kit), seed)
    add("grounds", [0, 0, 0], grounds + yards)

    # signature features per style
    feat = []
    solid = None
    if K_style in ("steampunk", "rust_industrial"):
        for i, (x0, z0, w_, d_, H, side, roof) in enumerate(foot):
            zc = z0 + 1 if side == "n" else z0 + d_ - 3  # far wall, away from the gallery
            for xc in (x0 + 2, x0 + w_ - 4):
                _chimney(feat, xc, zc, y + H - 2, 6 + (i + xc) % 4, K)
            if K_style == "steampunk":  # copper pipe runs on the three wall faces that are not the door face
                if solid is None:
                    solid = {(b[0] + g["origin"][0], b[1] + g["origin"][1], b[2] + g["origin"][2])
                             for g in ghosts for b in g["blocks"]}
                pl = []
                _pipes(pl, x0, z0, w_, d_, H, y, ("n", "e", "w") if side == "n" else ("s", "e", "w"), K, i)
                feat += [b for b in pl if (b[0], b[1], b[2]) not in solid]
                if roof in ("flat", "mansard"):
                    _roofworks(K, seed, ghosts, x0, z0, i, feat)
        _gear(feat, hx0 + HUB // 2, y + 17, hz0 + HUB - 3, 5, K)  # big gear over the hub's front door
        for zz in (gz + 1, gz + GD - 2):  # pipe runs along the gallery roofs
            for x in range(margin + 1, W - margin - 1):
                if not hx0 <= x < hx0 + HUB:
                    feat.append([x, y + 10, zz, "minecraft:lightning_rod[facing=east]"])
    elif K_style == "gothic":
        for (x0, z0, w_, d_, H, side, roof) in foot:
            _buttresses(feat, x0, z0, w_, d_, H, y, K, ("n" if side == "n" else "s", "e", "w"))
    elif K_style == "solarpunk":
        for i, (x0, z0, w_, d_, H, side, roof) in enumerate(foot):
            _greenwall(feat, x0, z0, w_, d_, H, y, ("n" if side == "n" else "s", "e", "w"), seed + i)
            if roof == "flat":  # roof garden: trees on the deck
                for (a, b) in ((4, 4), (w_ - 5, d_ - 5), (w_ // 2, d_ // 2)):
                    _tree(feat, x0 + a, z0 + b, y + H + 1, _wood(K, kit), i + a)
    elif K_style in ("station_white", "cyber_dark", "ae_sky"):
        skip = {(x, z) for x in range(tcx - r - 1, tcx + r + 2) for z in range(tcz - r - 1, tcz + r + 2)}
        _ring(feat, hx0 + HUB // 2, hz0 + HUB // 2, HUB // 2 + 5, y + 18, K, skip)
    feat += bays_legacy
    if feat:
        add("features", [0, 0, 0], feat)
    # Keep paving only under buildings, yards and the entrance avenue.
    for b in ghosts[0]["blocks"]:
        if b[1] == STEPS - 1 and (b[0], b[2]) not in occ:
            b[3] = "minecraft:grass_block"
    return ghosts


def summary(ghosts: list, wings: list) -> dict:
    xs = [g["origin"][0] for g in ghosts]
    return {"ghosts": [g["id"] for g in ghosts], "blocks": sum(len(g["blocks"]) for g in ghosts)}



# ================================================================================================ v8 archetypes
# Covered halls link every wing to the hub; cloister has a real arcade ring round a garth; terraces climb in tiers
# with retaining walls and stairs; station has a curved habitat-ring wing. Spine keeps its enclosed gallery.
LAYOUTS = {"steampunk": "spine", "hextech": "radial", "gothic": "cloister",
           "station_white": "linear", "solarpunk": "terraces"}
LAYOUT_NAMES = {"spine", "radial", "cloister", "linear", "terraces"}
GLASS = {"hextech": ["purple", "light_blue", "purple"], "gothic": ["orange", "yellow", "red"],
         "solarpunk": ["green", "light_blue", "white"], "station_white": ["light_blue", "cyan", "gray"]}
HUB_ROOF = {"hextech": "crown", "gothic": "hip_steep", "steampunk": "dome", "solarpunk": "dome", "station_white": "dome"}
HALL_STYLE = {"gothic": "open"}
RISE = 5  # terrace tier height
N4 = massing.N4


def _cells(x, z, w, d):
    return {(a, b) for a in range(x, x + w) for b in range(z, z + d)}


def _expand(centres, r=2):
    return {(a + i, b + j) for a, b in centres for i in range(-r, r + 1) for j in range(-r, r + 1)}


def _hall(mask, ty, blocked, K, kit, style="glass", gaps=()):
    """A roofed hall over `mask` (cells, ~5 wide): floor, pier + glass (or open pointed arches) on every open side,
    lintel beam, roof with a raised glazed ridge down the middle and glow lamps. Walls are skipped where a building
    already stands. gaps: edge cells left fully open (stair landings)."""
    Y = STEPS + ty
    out = []
    mask, blocked = set(mask), set(blocked)
    solid = mask | blocked
    pier = K.get("pillar", K["trim"])
    gothic = kit == "gothic"
    nb = lambda c: [(c[0] + a, c[1] + b) for a, b in N4]
    edge = {c for c in mask if any(n not in solid for n in nb(c))}
    rim = {c for c in mask if any(n not in mask for n in nb(c))}
    d1 = mask - rim
    d2 = {c for c in d1 if all(n in d1 for n in nb(c))}
    for c in mask:
        x, z = c
        out.append([x, Y, z, K["base"]])
        t = x + z
        if c in edge and c not in gaps:
            corner = sum(n not in solid for n in nb(c)) >= 2
            if style == "open":
                if t % 4 == 0 or corner:
                    for dy in range(1, 5):
                        out.append([x, Y + dy, z, pier])
                else:
                    if gothic and t % 4 in (1, 3):
                        out.append([x, Y + 3, z, K["trim"]])  # pointed arch shoulders
                    out.append([x, Y + 4, z, K["trim"]])
            else:
                door = t % 19 in (8, 9, 10) and not corner  # side opening every ~19 cells
                if (t % 3 == 0 or corner) and not door:
                    for dy in range(1, 5):
                        out.append([x, Y + dy, z, pier])
                else:
                    if not door:
                        for dy in range(1, 4):
                            out.append([x, Y + dy, z, K["glass"]])
                    out.append([x, Y + 4, z, K["trim"]])
        if c in rim:
            out.append([x, Y + 5, z, K["trim"]])
        elif c in d2:
            out.append([x, Y + 6, z, K["glass"]])
            if t % 6 == 0:
                out.append([x, Y + 5, z, K["glow"]])
        else:
            out.append([x, Y + 5, z, K["roof"]])
    return out


def _stairs_up(out, x0, x1, zs, ty_low, K, rise=RISE):
    """Stairs from tier level ty_low up `rise` blocks to the north: steps in front of a retaining wall at row zs."""
    Yl = STEPS + ty_low
    for i in range(rise):
        z = zs + rise - i
        for x in range(x0, x1 + 1):
            for yy in range(Yl + 1, Yl + 1 + i):
                out.append([x, yy, z, K["base"]])
            out.append([x, Yl + 1 + i, z, "minecraft:stone_brick_stairs[facing=north]"])
        for x in (x0 - 1, x1 + 1):  # balustrade
            for yy in range(Yl + 1, Yl + 2 + i):
                out.append([x, yy, z, K["base"]])
            out.append([x, Yl + 2 + i, z, K["rail"]])


def _garth(out, x0, z0, w, d, y, K, seed, wood):
    """Cloister garth: cross paths, a fountain, four hedged beds with a tree each."""
    cx, cz = x0 + w // 2, z0 + d // 2
    for x in range(x0, x0 + w):
        for z in range(z0, z0 + d):
            ax, az = abs(x - cx), abs(z - cz)
            if ax <= 1 or az <= 1:
                out.append([x, y, z, K["base"]])
            else:
                out.append([x, y, z, "minecraft:grass_block"])
                if max(ax, az) in (4,) and (ax + az) % 2 == 0:
                    out.append([x, y + 1, z, HEDGE])
                elif (ax * 3 + az * 5 + seed) % 5 == 0:
                    out.append([x, y + 1, z, FLOWERS[(ax + az * 2 + seed) % len(FLOWERS)]])
    for ax in range(-3, 4):
        for az in range(-3, 4):
            m = max(abs(ax), abs(az))
            if m == 3:
                out.append([cx + ax, y + 1, cz + az, K["trim"]])
            elif m < 3:
                out.append([cx + ax, y, cz + az, K["trim"] if m == 2 else "minecraft:water"])
    for dy in (1, 2):
        out.append([cx, y + dy, cz, K["trim"]])
    out.append([cx, y + 3, cz, K["glow"]])
    for sx in (-1, 1):
        for sz in (-1, 1):
            _tree(out, cx + sx * (w // 4 + 1), cz + sz * (d // 4 + 1), y + 1, wood, seed + sx + 2 * sz)


def _carve(blocks, ox, oy, oz, box):
    (x0, x1), (y0, y1), (z0, z1) = box
    return [b for b in blocks if not (x0 <= b[0] + ox <= x1 and y0 <= b[1] + oy <= y1 and z0 <= b[2] + oz <= z1)]


def _ring_origin(r, r_in, a0, a1):
    """Site offset so a fp_ring built from (r, r_in, a0, a1) is centred on (0, 0)."""
    import math as _m
    span = (a1 - a0) % 360 or 360
    pts = []
    for x in range(2 * r + 1):
        for z in range(2 * r + 1):
            dx, dz = x - r, z - r
            dd = _m.hypot(dx, dz)
            if r_in - 0.45 <= dd <= r + 0.45 and (_m.degrees(_m.atan2(dz, dx)) % 360 - a0) % 360 <= span:
                pts.append((x, z))
    return -(r - min(p[0] for p in pts)), -(r - min(p[1] for p in pts))


# towers: one profile per kit
TOWER_STAGES = {
    # stage: (shape, size, floor heights, roof, corner cut[, role overrides])
    "hextech": [("octagon", 19, [12, 6, 6, 6], "flat", 6), ("octagon", 15, [6, 6, 6], "flat", 5),
                ("octagon", 11, [6, 6], "flat", 4),
                ("octagon", 9, [6, 6], "spire", 3, {"wall": "minecraft:purple_stained_glass", "wall2": "minecraft:purple_stained_glass",
                                                   "glass": "minecraft:light_blue_stained_glass"})],
    "gothic": [("rect", 15, [12, 6, 6, 6], "flat", 0), ("rect", 11, [6, 6, 6], "flat", 0), ("rect", 7, [6, 6, 6], "flat", 0)],
    "steampunk": [("rect", 15, [12, 6, 6], "flat", 0), ("rect", 11, [6, 6, 6], "flat", 0), ("rect", 7, [6, 6], "hip_steep", 0)],
    "solarpunk": [("round", 7, [12, 6, 6, 6], "garden", 0), ("round", 5, [6, 6, 6], "dome", 0)],
}


def _tower(K, kit, roles, seed, cx, cz, y):
    """The landmark, centred on (cx, cz), base plinth at y. Returns [(ghost id, origin, blocks)]."""
    stages = TOWER_STAGES.get(kit) or [("round", 7, [12, 6, 6, 6, 6], "flat", 0),
                                       ("round", 5, [6, 6, 6, 6], TOWER_ROOF.get(kit, "crown"), 0)]
    parts, yy = [], y
    for k, stage in enumerate(stages):
        shape, sz, hs, roof, c = stage[:5]
        ro = dict(roles or {})
        ro.update(stage[5] if len(stage) > 5 else {})
        prog = (["hall", "lab", "storage", "lab", "living"] if k == 0 else ["lab", "living", "lab", "hall"])[:len(hs)]
        kw = {"r": sz} if shape == "round" else {"w": sz, "d": sz, "c": c}
        half = sz if shape == "round" else sz // 2
        last = k == len(stages) - 1
        bl = massing.structure(shape, floor_hs=hs, program=prog, kit=kit, roles=ro, entrances=["s"], roof=roof,
                               bay=6 if kit == "gothic" else 4,
                               windows="lancet" if kit == "gothic" else ("slit" if k == 0 else "band"),
                               accent_floor=1 if k == 0 else 0, core="elevator", roof_details=0,
                               antennas=1 if last and kit != "gothic" else 0, seed=seed + 70 + k, **kw)
        gid = "tower" if k == 0 else ("tower_top" if last else ("tower_mid" if k == 1 else f"tower_mid{k}"))
        parts.append((gid, [cx - half, yy, cz - half], bl))
        yy += sum(hs) + 1
    if kit == "steampunk":  # big copper cogwheels on the tower walls (east/west of the base, front of the second stage)
        gears = []
        h0 = stages[0][1] // 2
        H0 = sum(stages[0][2]) + 1
        rim, teeth, spoke, hub_ = "minecraft:copper_block", "minecraft:cut_copper", "minecraft:waxed_exposed_copper", "minecraft:iron_block"
        for sd in (1, -1):
            _cog(gears, cz, y + 14, cx + sd * h0, 6, "x", sd, rim, teeth, spoke, hub_)
        if len(stages) > 1:
            h1 = stages[1][1] // 2
            y1 = y + H0
            _cog(gears, cx, y1 + 9, cz + h1, 4, "z", 1, "minecraft:waxed_weathered_copper", teeth, spoke, hub_)
            _cog(gears, cz, y1 + 9, cx + h1, 4, "x", 1, "minecraft:waxed_weathered_copper", teeth, spoke, hub_)
        parts.append(("tower_gears", [0, 0, 0], gears))
    if stages[0][0] == "round" and kit != "solarpunk":
        hs1 = stages[0][2]
        parts.append(("tower_trim", [0, 0, 0], _tower_trim(K, cx, cz, 7, stages[-1][1], y, hs1)))
    if kit == "hextech":  # gold fins up the shaft corners, lit finials, lightning-rod crown
        trim = []
        H1 = sum(stages[0][2]) + 1
        Htot = sum(sum(st[2]) + 1 for st in stages[:3])
        for sx in (-1, 1):
            for sz in (-1, 1):
                px, pz = cx + sx * 9, cz + sz * 9
                for dy in range(0, H1 + 6):
                    trim.append([px, y + dy, pz, K["trim"] if dy % 6 else K["detail"]])
                trim.append([px, y + H1 + 6, pz, K["glow"]])
                trim.append([px, y + H1 + 7, pz, K["antenna"]])
                trim.append([px, y + H1 + 8, pz, K["antenna"]])
        # v16: the halo posts used to float (radius 7 is outside the tower). Each post is now joined to the tower by a thin
        # rod at the same height, stepping inwards until it touches a tower block; no contact -> the post is dropped.
        solid = {}
        for _gid, _o, _bl in parts:
            for b_ in _bl:
                if not str(b_[3]).split("[")[0].endswith("air"):
                    solid[(_o[0] + b_[0], _o[1] + b_[1], _o[2] + b_[2])] = 1
        hy = y + Htot
        for ang in range(0, 360, 45):  # gold ring halo under the glass crown
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            rod, hit = [], False
            for r_ in range(70, 20, -1):  # r_/10 from 7.0 down to 2.1
                hx, hz = round(cx + r_ / 10 * ca), round(cz + r_ / 10 * sa)
                if (hx, hz) in [(q[0], q[2]) for q in rod]:
                    continue
                if any((hx + d[0], hy + d[1], hz + d[2]) in solid for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0))):
                    hit = True
                    if (hx, hy, hz) not in solid:
                        rod.append([hx, hy, hz])
                    break
                if (hx, hy, hz) in solid:
                    hit = True
                    break
                rod.append([hx, hy, hz])
            if not hit:
                continue
            for hx, _hy, hz in rod:
                trim.append([hx, hy, hz, K["trim"]])
            trim.append([rod[0][0], hy + 1, rod[0][2], K["antenna"]])
        parts.append(("tower_trim", [0, 0, 0], trim))
    if kit == "gothic":  # corner pinnacles on the first setback, a 30-high needle spire on the top stage
        trim = []
        H1 = sum(stages[0][2]) + 1
        ytop = y + sum(sum(st[2]) + 1 for st in stages)  # deck level of the top stage
        for dy in range(1, 31):
            hw = 2 if dy <= 9 else (1 if dy <= 20 else 0)
            for a in range(-hw, hw + 1):
                for b in range(-hw, hw + 1):
                    shell = hw == 0 or abs(a) == hw or abs(b) == hw or dy in (9, 20)  # solid cap where the needle narrows
                    if shell:
                        edge_ = hw and abs(a) == hw and abs(b) == hw
                        blk = K.get("band", K["glow"]) if dy in (4, 5) and not edge_ else (K.get("pillar", K["trim"]) if edge_ or dy % 6 == 0 else K["roof"])
                        trim.append([cx + a, ytop + dy, cz + b, blk])
        for dy in range(31, 35):
            trim.append([cx, ytop + dy, cz, K["antenna"]])
        trim.append([cx, ytop + 35, cz, K["tip"]])
        for sx in (-1, 1):  # four small pinnacles at the needle foot
            for sz in (-1, 1):
                for dy in range(1, 5):
                    trim.append([cx + sx * 3, ytop + dy, cz + sz * 3, K.get("pillar", K["trim"])])
                trim.append([cx + sx * 3, ytop + 5, cz + sz * 3, K["tip"]])
        for sx in (-1, 1):
            for sz in (-1, 1):
                px, pz = cx + sx * 6, cz + sz * 6
                for dy in range(1, 8):
                    trim.append([px, y + H1 + dy, pz, K.get("pillar", K["trim"])])
                trim.append([px, y + H1 + 8, pz, K["antenna"]])
                trim.append([px, y + H1 + 9, pz, K["tip"]])
        parts.append(("tower_trim", [0, 0, 0], trim))
    return parts


def _porch(K):
    """Gothic pointed-arch porch with a pediment and rose window (v15: 9 wide x 9 high opening, lit tympanum, pinnacles,
    entry step). Local frame: u outward from the wing's edge layer (u=0), v sideways (door centre = 0), y above the
    wing plinth (y=0). Returns {(u, v, y): block}."""
    body = "minecraft:stone_bricks"
    trim = K.get("trim", "minecraft:smooth_stone")
    glass, glow = K["glass"], K["glow"]
    hw = {1: 4, 2: 4, 3: 4, 4: 4, 5: 3, 6: 3, 7: 2, 8: 2, 9: 1, 10: 0}  # pointed arch opening half-width per row
    opening = {(v, y) for y, h in hw.items() for v in range(-h, h + 1)}
    ring = set()
    for (v, y) in opening:
        for dv in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = (v + dv, y + dy)
                if c not in opening and c[1] >= 0:
                    ring.add(c)
    B = {}
    for u in range(1, 6):
        for (v, y) in ring:
            front = u == 5 or u == 1
            B[(u, v, y)] = trim if front and (abs(v) + y) % 2 == 0 else body
        for v in range(-4, 5):
            B[(u, v, 0)] = "minecraft:smooth_stone"  # porch floor
    for (v, y) in opening:  # lit stained tympanum at the back of the arch above the door (door stays open below y=5)
        if y >= 5 and (v, y) not in ring:
            B[(1, v, y)] = trim if (v == 0 or y == 5) else glass
    B[(1, 0, 9)] = glow
    for v in range(-4, 5):  # entry step
        B[(6, v, 0)] = "minecraft:stone_brick_slab[type=bottom]"
    for y in range(1, 10):  # buttress-pier either side of the front arch, topped with a pinnacle
        for v in (-6, 6):
            B[(5, v, y)] = trim if y % 3 == 0 else body
            B[(4, v, y)] = body
    for v in (-6, 6):
        B[(5, v, 10)] = trim
        B[(5, v, 11)] = trim
        B[(5, v, 12)] = K.get("tip", "minecraft:lantern")
    # pediment on the front plane: stepped gable with a rose window
    rows = {11: 5, 12: 5, 13: 4, 14: 3, 15: 2, 16: 1, 17: 0}
    for y, h in rows.items():
        for v in range(-h, h + 1):
            edge = abs(v) == h
            B[(5, v, y)] = trim if edge or y == 11 else body
    for v in range(-5, 6):
        B[(5, v, 10)] = trim if abs(v) in (2, 4) else body  # springing course closes the gap under the pediment
    for dv in range(-3, 4):
        for dy in range(-3, 4):
            r2 = dv * dv + dy * dy
            if r2 <= 3:
                B[(5, dv, 14 + dy)] = glass
            elif r2 <= 7:
                B[(5, dv, 14 + dy)] = trim
    B[(5, 0, 14)] = glow
    for dy in (-1, 0, 1):
        B[(5, 0, 14 + dy)] = B.get((5, 0, 14 + dy), trim) if dy else glow
    B[(5, 0, 18)] = K.get("tip", "minecraft:lantern")
    return B


def _airdock(K, y_g, hwall):
    """Hextech skybridge: a gangway off the tower wall into an airship dock with a moored airship. Local frame:
    u = outward from the wall layer (u=0 is the tower's edge layer), v = sideways, y absolute. Returns {(u, v, y): block}."""
    B = {}
    q, qs, pil = K["trim"], "minecraft:quartz_slab[type=top]", K.get("pillar", K["trim"])
    base, rail, glow = K["wall2"], K["rail"], K["glow"]

    def put(u, v, y, b):
        B[(u, v, y)] = b
    # gangway u 0..11, 3 wide, deck at y_g with rails and a dark spine beam beneath
    for u in range(0, 12):
        for v in (-1, 0, 1):
            put(u, v, y_g, q)
        put(u, 0, y_g - 1, base)
        for v in (-2, 2):
            put(u, v, y_g, base)
            put(u, v, y_g + 1, rail)
        if u % 4 == 3:
            put(u, 0, y_g - 2, base)
            put(u, -2, y_g - 1, glow)
            put(u, 2, y_g - 1, glow)
    for dy in (1, 2, 3):  # door frame hugging the wall
        for v in (-2, 2):
            put(0, v, y_g + dy, pil)
    for v in (-1, 0, 1):
        put(0, v, y_g + 4, pil)
    # dock deck u 12..26, v -14..14, two courses thick, glow edge strip, rail
    for u in range(12, 27):
        for v in range(-14, 15):
            put(u, v, y_g, q if (u + v) % 6 else base)
            put(u, v, y_g - 1, base)
            if u in (12, 26) or abs(v) == 14:
                put(u, v, y_g + 1, rail)
                if (u + v) % 4 == 0:
                    put(u, v, y_g, glow)
    # four pylons (3x3 quartz pillar) to the ground, braced by a cross beam under the deck
    for u in (14, 24):
        for v in (-12, 12):
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for y in range(2, y_g - 1):
                        put(u + dx, v + dz, y, pil if (dx, dz) == (0, 0) or y % 8 else base)
    for v in (-12, 12):
        for u in range(14, 25):
            put(u, v, y_g - 2, base)
    for u in (14, 24):
        for v in range(-12, 13):
            put(u, v, y_g - 2, base)
    # airship moored on the deck: gondola (u 17..22, v -9..9), tapered ends
    gy = y_g + 1
    for v in range(-9, 10):
        taper = 0 if abs(v) <= 6 else (1 if abs(v) <= 8 else 2)
        for u in range(17 + taper, 23 - taper):
            for dy in range(0, 4):
                edge = u in (17 + taper, 22 - taper) or abs(v) == 9 - 0
                wallb = "minecraft:dark_oak_planks" if dy < 2 else "minecraft:spruce_planks"
                if dy == 3:
                    put(u, v, gy + dy, "minecraft:dark_oak_slab[type=bottom]" if not edge else "minecraft:dark_oak_planks")
                elif edge or dy == 0:
                    if dy == 2 and v % 3 == 0 and abs(v) < 8:
                        put(u, v, gy + dy, "minecraft:light_blue_stained_glass")
                    else:
                        put(u, v, gy + dy, wallb)
    # envelope: ellipsoid, white concrete with purple bands
    cu, cy_, a, b_, c_ = 19.5, gy + 9, 12.5, 4.6, 5.0  # v semi-axis a, u semi-axis b_, y semi-axis c_
    for v in range(-13, 14):
        for u in range(13, 27):
            for y in range(int(cy_ - c_ - 1), int(cy_ + c_ + 2)):
                t = (v / a) ** 2 + ((u - cu) / b_) ** 2 + ((y - cy_) / c_) ** 2
                if 0.55 <= t <= 1.0:
                    band = abs(v) % 6 == 0
                    put(u, v, y, "minecraft:purple_concrete" if band else "minecraft:white_concrete")
    # struts from gondola roof to envelope belly
    for v in (-6, -2, 2, 6):
        for u in (18, 21):
            for y in range(gy + 4, int(cy_ - c_) + 2):
                put(u, v, y, "minecraft:iron_bars")
    # tail fins (v = -13..-10) and propeller at the stern (v=-10)
    for dv in range(0, 4):
        for dy in range(0, 5 - dv):
            put(19, -10 - dv, int(cy_) + 3 + dy, base)
            put(19, -10 - dv, int(cy_) - 3 - dy, base)
    for du in (-2, -1, 1, 2):
        put(19 + du, -11, gy + 2, "minecraft:iron_bars")
    # nose mooring mast at v=+13 up to the envelope tip + chain line, gangplank from the dock walkway
    for y in range(y_g + 1, int(cy_) + 1):
        put(20, 13, y, pil if y % 5 else K.get("band", glow))
    for v in range(10, 13):
        put(20, v, int(cy_), "minecraft:chain[axis=x]" if False else "minecraft:iron_bars")
    for u in (13, 14, 15, 16):  # plank walkway from the gangway end to the gondola door
        for v in (-1, 0, 1):
            put(u, v, gy, "minecraft:spruce_slab[type=bottom]")
    return B


def _roof_for(wing, kit, i):
    cyc = ROOF_CYCLE.get(kit if isinstance(kit, str) else "", ["flat", "crown"])
    return wing.get("roof") or cyc[i % len(cyc)]


def _windows(kit, i):
    return "lancet" if kit in ("gothic", "hextech") else ("grid" if i % 2 else "band")


class _Site:
    def __init__(self, kit, roles, seed, layout):
        self.kit, self.roles, self.seed, self.layout = kit, roles, seed, layout
        self.K = massing._kit(kit, roles)
        self.ghosts, self.foot, self.doors = [], [], []
        self.blocked, self.occupied = set(), set()
        self.levels, self.gaps = {}, {}  # ty -> hall cells / stair-landing gaps
        self.grounds, self.extra = [], []
        self.obstacles = set()
        self.meta = {}
        self.bays = []
        self.porch_cells = set()

    def add(self, gid, x, y, z, blocks, meta=None):
        self.ghosts.append({"id": gid, "origin": [x, y, z], "blocks": blocks, "meta": meta or {}})

    def reserve(self, cells, pad=3):
        self.occupied |= _expand(cells, pad) if pad else cells

    def wing(self, i, wing, x, z, w, d, door, ty=0):
        K, kit = self.K, self.kit
        wr = dict(self.roles or {})
        wr.update(wing.get("roles") or {})
        wr.setdefault("glass", "minecraft:" + GLASS.get(kit, ["cyan", "light_blue", "gray"])[i % 3] + "_stained_glass")
        if kit == "gothic":  # light stone wings: pale walls, smooth-stone tracery/buttress, orange lancets glow against them
            wr.setdefault("wall", "minecraft:stone_bricks")
            wr.setdefault("wall2", "minecraft:polished_andesite")
            wr.setdefault("trim", "minecraft:smooth_stone")
            wr.setdefault("ridge", "minecraft:smooth_stone")
        wr.setdefault("wall2", [K["wall2"], K["wall"], K["base"]][i % 3])
        mats = ROOF_MATS.get(kit if isinstance(kit, str) else "")
        if mats and "roof" not in (wing.get("roles") or {}):  # v16: per-wing hue wins over a model-wide roles.roof
            wr["roof"] = mats[i % len(mats)]
        roof = _roof_for(wing, kit, i)
        hs = [int(wing.get("floor_h") or (8 + 2 * (i % 3)))] + [6] * (int(wing.get("floors") or 1) - 1)
        prog = [wing.get("rooms") or ["expansion"]] + [wing.get("upper") or ["expansion"]] * (len(hs) - 1)
        blocks = massing.structure("rect", w=w, d=d, kit=kit, roles=wr, floor_hs=hs, program=prog,
                                   entrances=[door], roof=roof, bay=6 if kit in ("gothic", "hextech") else 4 + i % 3,
                                   windows=_windows(kit, i), rhythm=1 + i % 3, finial=1,
                                   seed=self.seed + i)
        H = sum(hs) + 1
        name = str(wing.get("name", i))
        self.bays += _wing_bays(x, z, w, d, STEPS + ty, hs[0], H, door, K, kit, self.seed + i, i)
        self.add("wing_" + name, x, STEPS + ty, z, blocks,
                 {"kind": "wing", "floor_y": STEPS + ty + 1, "deck_y": STEPS + ty + H + 1, "door": door,
                  "roof": roof, "rooms": wing.get("rooms")})
        self.foot.append({"x": x, "z": z, "w": w, "d": d, "H": H, "door": door, "ty": ty, "roof": roof, "i": i})
        cells = _cells(x, z, w, d)
        self.blocked |= cells
        self.obstacles |= _expand(cells, 3)
        self.occupied |= _expand(cells, 3)
        ex, ez = {"n": (x + w // 2, z - 1), "s": (x + w // 2, z + d), "w": (x - 1, z + d // 2),
                  "e": (x + w, z + d // 2)}[door]
        self.doors.append((ex, ez, door, ty))

    def connect(self, net, ty=0, bound=260):
        """BFS from every wing door to the nearest hall centre line; adds 5-wide halls along each route."""
        from collections import deque
        for ex, ez, door, t in self.doors:
            if t != ty:
                continue
            dx, dz = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}[door]
            start = (ex + dx * 4, ez + dz * 4)
            queue, prev, end = deque([start]), {start: None}, None
            while queue:
                q = queue.popleft()
                if q in net:
                    end = q
                    break
                for a, b in N4:
                    r = (q[0] + a, q[1] + b)
                    if r in prev or r in self.obstacles or abs(r[0]) > bound or abs(r[1]) > bound:
                        continue
                    prev[r] = q
                    queue.append(r)
            if end is None:
                raise ValueError("unreachable wing entrance")
            route = []
            while end is not None:
                route.append(end)
                end = prev[end]
            route += [(ex + dx * k, ez + dz * k) for k in range(5)]
            net.update(route)
            self.levels.setdefault(ty, set()).update(_expand(route))

    def hubs(self, entrances, roof=None):
        K, kit = self.K, self.kit
        roof = roof or HUB_ROOF.get(kit, "crown")
        hub = massing.structure("octagon", w=33, d=33, c=6, kit=kit, roles=self.roles, floor_hs=[12],
                                program=["hall"], entrances=entrances, roof=roof, windows=_windows(kit, 1), seed=self.seed + 60)
        self.add("hub", -16, STEPS, -16, hub, {"kind": "hub", "floor_y": STEPS + 1, "deck_y": STEPS + 13, "roof": roof})
        cells = massing.fp_octagon(33, 33, 6)
        cells = {(x - 16, z - 16) for x, z in cells}
        self.blocked |= cells
        self.obstacles |= _expand(cells, 2)
        self.occupied |= _expand(cells, 3)

    def tower_at(self, cx, cz, ty=0):
        for gid, org, bl in _tower(self.K, self.kit, self.roles, self.seed, cx, cz, STEPS + ty):
            self.add(gid, org[0], org[1], org[2], bl, {"kind": "tower", "floor_y": STEPS + ty + 1})
        if self.kit == "hextech":
            self.airdock(cx, cz, STEPS + ty)
        h0 = TOWER_STAGES.get(self.kit, [("", 15)])[0][1] // 2 + 1
        cells = _cells(cx - h0, cz - h0, 2 * h0 + 1, 2 * h0 + 1)
        self.blocked |= {(x, z) for x, z in cells if (x - cx) ** 2 + (z - cz) ** 2 <= (h0 + 1) ** 2 + h0}
        self.obstacles |= _expand(cells, 2)
        self.occupied |= _expand(cells, 3)

    def airdock(self, cx, cz, y):  # noqa: D401
        """Hextech airship dock + gangway off the tower: pick the free side (east, west, north) and reserve its cells."""
        hw = TOWER_STAGES["hextech"][0][1] // 2
        y_g = y + sum(TOWER_STAGES["hextech"][0][2][:3]) + 3  # fourth floor line
        L, V = 27, 15

        def rect(side, V=V):
            if side in "ew":
                x0 = cx + hw if side == "e" else cx - hw - L
                return _cells(x0, cz - V, L + 1, 2 * V + 1)
            if side == "s":
                return _cells(cx - V, cz + hw + 1, 2 * V + 1, L + 1)
            return _cells(cx - V, cz - hw - L - 1, 2 * V + 1, L + 1)
        # v15: test the deck footprint (+-14) against real obstacles only (not the soft padding), east/west first: they stay
        # visible from the front shot (the hub is lower than the airship); north (behind the tower) is the last resort
        taken = self.obstacles | self.blocked
        side = next((sd for sd in "ewsn" if not (rect(sd, 14) & taken)), None)
        if side is None:
            side = min("ewsn", key=lambda sd: len(rect(sd, 14) & taken))
        B = _airdock(self.K, y_g, hw)
        out = []
        for (u, v, yy), b in B.items():
            if side == "e":
                x, z = cx + hw + u, cz + v
            elif side == "w":
                x, z = cx - hw - u, cz - v
            elif side == "s":
                x, z = cx + v, cz + hw + u
            else:
                x, z = cx - v, cz - hw - u
            out.append([x, yy, z, b])
        self.add("airdock", 0, 0, 0, out, {"kind": "airdock", "side": side})
        self.reserve(rect(side), pad=1)
        self.obstacles |= rect(side)  # halls route round the dock
        self.meta["airdock"] = side

    def finish(self, extra_cells=None):
        """Halls, platform, gardens and per-wing style features, then shift to a (0,0) min corner."""
        K, kit = self.K, self.kit
        style = HALL_STYLE.get(kit, "glass")
        halls = []
        allhall = set()
        for ty, mask in self.levels.items():
            mask = mask - self.blocked
            allhall |= mask
            halls += _hall(mask, ty, self.blocked, K, kit, style, self.gaps.get(ty, ()))
        self.add("halls", 0, 0, 0, halls, {"kind": "halls"})
        used = self.occupied | allhall | (extra_cells or set())
        # per-wing style features
        feat = []
        y = STEPS
        for f in self.foot:
            x0, z0, w_, d_, H, door, ty = f["x"], f["z"], f["w"], f["d"], f["H"], f["door"], f["ty"]
            sides = tuple(s for s in "nsew" if s != door)
            if kit in ("steampunk", "rust_industrial"):
                zc = z0 + 1 if door == "s" else z0 + d_ - 3
                for xc in (x0 + 2, x0 + w_ - 4):
                    _chimney(feat, xc, zc, y + ty + H - 2, 6 + (f["i"] + xc) % 4, K)
                if kit == "steampunk":
                    _pipes(feat, x0, z0, w_, d_, H, y + ty, sides, K, f["i"])
                    if f["roof"] in ("flat", "mansard"):
                        _roofworks(K, self.seed, self.ghosts, x0, z0, f["i"], feat)
            elif kit == "gothic":
                _gothic_porch(self, f)
                _buttresses(feat, x0, z0, w_, d_, H, y + ty, dict(K, wall="minecraft:stone_bricks", trim="minecraft:smooth_stone"), sides)
            elif kit == "solarpunk":
                _greenwall(feat, x0, z0, w_, d_, H, y + ty, sides, self.seed + f["i"])
        if kit == "station_white":
            _radar(self)
        elif kit == "solarpunk":
            _roof_terraces(self, allhall)
        feat = [b for b in feat if (b[0], b[2]) not in allhall and (b[0], b[1], b[2]) not in self.porch_cells]
        feat += [b for b in self.bays if (b[0], b[1], b[2]) not in self.porch_cells]
        if feat:
            self.add("features", 0, 0, 0, feat, {"kind": "features"})
        return used, allhall


def _roofworks(K, seed, ghosts, x0, z0, i, feat):
    """Steam: structure on a flat wing roof (flat or mansard plateau): copper ridge ring, glazed skylight strips, a raised
    pipe run on posts, boiler tanks, vent stacks. All of it stands on the deck (y+1) so nothing floats."""
    wg = next((g for g in ghosts if g["id"].startswith("wing_") and g["origin"][0] == x0 and g["origin"][2] == z0), None)
    if not wg:
        return
    ox, oy, oz = wg["origin"]
    top = {}
    for bx, by, bz, _b in wg["blocks"]:
        if top.get((bx, bz), -1) < by:
            top[(bx, bz)] = by
    import collections as _c
    my = _c.Counter(top.values()).most_common(1)[0][0]  # the deck level (parapets/vents/antennas are rarer)
    plate = {p for p, v in top.items() if v == my}
    if len(plate) < 30:
        return
    ero = {p for p in plate if all((p[0] + a, p[1] + c) in plate for a in range(-2, 3) for c in range(-2, 3))}
    if len(ero) < 12:
        return
    rim = {p for p in plate if any((p[0] + a, p[1] + c) not in plate for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    Y = oy + my + 1
    used = set()

    def put(x, y, z, b):
        feat.append([ox + x, y, oz + z, b])
    for (x, z) in rim:  # copper ridge line round the deck edge
        put(x, Y, z, "minecraft:cut_copper_slab[type=bottom]" if (x + z) % 4 else "minecraft:copper_block")
    xs = [p[0] for p in ero]
    zs = [p[1] for p in ero]
    xa, xb, za, zb = min(xs), max(xs), min(zs), max(zs)
    along_x = (xb - xa) >= (zb - za)
    lo, hi, c0, c1 = (xa, xb, za, zb) if along_x else (za, zb, xa, xb)
    mid = (c0 + c1) // 2

    def P(u, v):
        return (u, v) if along_x else (v, u)
    rnd = (seed + i) % 3
    # raised pipe run down the middle on posts every 4
    for u in range(lo, hi + 1):
        pt = P(u, mid)
        if pt in ero:
            put(pt[0], Y + 1, pt[1], "minecraft:waxed_oxidized_cut_copper" if u % 6 else "minecraft:copper_block")
            if (u - lo) % 4 == 0:
                put(pt[0], Y, pt[1], K["trim"])
            used.add(pt)
    # two glazed skylight strips (glass over a copper frame) either side of the pipe
    for v0 in (mid - 4, mid + 3):
        for u in range(lo + 2, hi - 1):
            for dv in (0, 1):
                pt = P(u, v0 + dv)
                if pt in ero and pt not in used:
                    put(pt[0], Y, pt[1], K["glass"])
                    used.add(pt)
            for dv in (-1, 2):
                pt = P(u, v0 + dv)
                if pt in ero and pt not in used and (u - lo) % 2 == 0:
                    put(pt[0], Y, pt[1], "minecraft:waxed_cut_copper")
                    used.add(pt)
    # boilers (windowed tank columns with a copper cap) and vent stacks at the ends
    spots = [P(lo + 2, mid - 2), P(lo + 2, mid + 2), P(hi - 3, mid - 2), P(hi - 3, mid + 2)]
    for n_, pt in enumerate(spots):
        if not all((pt[0] + a, pt[1] + c) in ero and (pt[0] + a, pt[1] + c) not in used for a in (0, 1) for c in (0, 1)):
            continue
        h = 3 + (n_ + rnd) % 2
        if n_ % 2 == 0:
            for a in (0, 1):
                for c in (0, 1):
                    for dy in range(h):
                        put(pt[0] + a, Y + dy, pt[1] + c, f"create:fluid_tank[shape=window,bottom={str(dy == 0).lower()},top={str(dy == h - 1).lower()}]")
                    put(pt[0] + a, Y + h, pt[1] + c, "minecraft:copper_block")
                    used.add((pt[0] + a, pt[1] + c))
        else:
            _chimney(feat, ox + pt[0], oz + pt[1], Y, h + 2, K)
            for a in (0, 1):
                for c in (0, 1):
                    used.add((pt[0] + a, pt[1] + c))


def _radar(S):
    """Sci feature: a radar dish on a mast from the hub dome's apex plus four antenna arrays standing on the dome.
    Every part starts on a hub block (mast on the apex, arrays on the dome surface). Ghost id "radar"."""
    hub = next((g for g in S.ghosts if g["id"] == "hub"), None)
    if not hub:
        return
    ox, oy, oz = hub["origin"]
    top = {}
    for x, y, z, b in hub["blocks"]:
        if top.get((x, z), -1) < y:
            top[(x, z)] = y
    c0 = 16  # hub 33x33 local centre
    cand = [(c0 + a, c0 + c) for a in range(-3, 4) for c in range(-3, 4) if (c0 + a, c0 + c) in top]
    if not cand:
        return
    ax, az = max(cand, key=lambda p_: (top[p_], -abs(p_[0] - c0) - abs(p_[1] - c0)))
    base = top[(ax, az)]
    out = []

    def put(x, y, z, b):
        out.append([ox + x, oy + y, oz + z, b])
    white, grey, rim = "minecraft:white_concrete", "minecraft:light_gray_concrete", "minecraft:orange_concrete"
    bar = "minecraft:iron_bars"
    # base platform 9x9 (grey rim, white deck) whose footprint is filled down to the dome surface, so it sits on the hub
    for dx in range(-4, 5):
        for dz in range(-4, 5):
            if abs(dx) == 4 and abs(dz) == 4:
                continue
            px, pz = ax + dx, az + dz
            t = top.get((px, pz))
            if t is None:
                continue
            for yy in range(t + 1, base + 2):
                put(px, yy, pz, grey)
            put(px, base + 2, pz, rim if max(abs(dx), abs(dz)) == 4 else white)
    for dx in (-2, -1, 0, 1, 2):  # equipment plinth + 3x3 mast core, 8 high, banded
        for dz in (-2, -1, 0, 1, 2):
            put(ax + dx, base + 3, az + dz, grey)
    for dy in range(4, 11):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                put(ax + dx, base + dy, az + dz, rim if dy % 4 == 0 else (white if dy % 2 else grey))
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # diagonal buttress struts from platform edge up to the mast
        for k in range(1, 5):
            put(ax + sx * (4 - k), base + 2 + k, az + sz * (4 - k), grey)
            put(ax + sx * (4 - k) + sz, base + 2 + k, az + sz * (4 - k) + sx, grey)
    y0 = base + 11
    R = 7
    for dx in range(-R, R + 1):  # parabolic bowl, white with an orange rim
        for dz in range(-R, R + 1):
            r = math.hypot(dx, dz)
            if r <= R + 0.3:
                h = int(r * r / 11)
                b = rim if r >= R - 0.9 else (grey if int(r) % 3 == 0 and r > 1.5 else white)
                put(ax + dx, y0 + h, az + dz, b)
                if h > 0 and r >= 2.5:
                    put(ax + dx, y0 + h - 1, az + dz, white)  # second layer so the bowl reads solid from the side
    for dy in range(1, 7):  # feed horn
        put(ax, y0 + dy, az, bar if dy < 6 else "minecraft:end_rod")
    put(ax, y0 + 7, az, "minecraft:lightning_rod")
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # struts: rim -> feed horn, riding above the bowl surface
        for k in range(1, 6):
            rr = R - 1 - k
            put(ax + sx * rr, y0 + int(rr * rr / 11) + k, az + sz * rr, bar)
    # antenna arrays: lightning-rod masts with cross bars, standing on the dome surface
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        px, pz = ax + sx * 10, az + sz * 10
        if (px, pz) not in top:
            continue
        b0 = top[(px, pz)]
        for dy in range(1, 9):
            put(px, b0 + dy, pz, bar if dy < 8 else "minecraft:lightning_rod")
        for dv in (-2, -1, 1, 2):
            put(px + dv, b0 + 5, pz, bar)
        for dv in (-1, 1):
            put(px, b0 + 3, pz + dv, bar)
        put(px, b0 + 9, pz, "minecraft:end_rod")
    S.add("radar", 0, 0, 0, list({(b[0], b[1], b[2]): b for b in out}.values()), {"kind": "radar"})


def _roof_terraces(S, allhall):
    """Solar feature: on up to two garden-roofed wings build a raised rooftop pond with a stepped planting terrace behind
    it and a 3-wide waterfall down the wall face into a ground pool. Cells are cut out of the wing ghost first so nothing
    z-fights; the waterfall column sits in the edge layer against the wall. Ghost id "roofgarden"."""
    out, done = [], 0
    for f in sorted(S.foot, key=lambda f_: f_["roof"] != "garden"):
        if done >= 2 or f["roof"] not in ("garden", "flat"):
            continue
        x0, z0, w, d, H, door, ty = f["x"], f["z"], f["w"], f["d"], f["H"], f["door"], f["ty"]
        wg = next((g for g in S.ghosts if g["meta"].get("kind") == "wing" and g["origin"][0] == x0 and g["origin"][2] == z0), None)
        if not wg:
            continue
        D = wg["meta"]["deck_y"]
        gy = STEPS + ty  # standing level
        cxw, czw = x0 + w // 2, z0 + d // 2
        chosen = None
        for sd in [s_ for s_ in "snew" if s_ != door]:
            def uv(u, v, sd=sd):
                return {"n": (cxw + v, z0 + u), "s": (cxw + v, z0 + d - 1 - u), "w": (x0 + u, czw + v),
                        "e": (x0 + w - 1 - u, czw + v)}[sd]
            if (d if sd in "ns" else w) < 18:
                continue
            outside = {uv(u, v) for u in range(-5, 0) for v in range(-6, 7)}
            if outside & (allhall | S.blocked):
                continue
            chosen = uv
            break
        if chosen is None:
            continue
        uv = chosen
        cells = {}

        def put(u, v, y, b):
            cells[(uv(u, v), y)] = b
        rim, water = S.K["base"], "minecraft:water"
        # raised pond: rim 2 high around u 2..9, v -6..6; water inside
        for u in range(2, 10):
            for v in range(-6, 7):
                if u in (2, 9) or abs(v) == 6:
                    put(u, v, D + 1, rim)
                    put(u, v, D + 2, rim if (u + v) % 3 else S.K.get("band", S.K["glow"]))
                else:
                    put(u, v, D + 1, water)
                    if (u * 5 + v * 3) % 7 == 0:
                        put(u, v, D + 2, "minecraft:lily_pad")
        for u in range(0, 3):  # spout channel through the rim and the roof edge
            for v in (-1, 0, 1):
                put(u, v, D + 1, water)
                cells.pop((uv(u, v), D + 2), None)
        for v in (-2, 2):
            for u in range(0, 3):
                put(u, v, D + 1, rim)
                put(u, v, D + 2, rim)
        # stepped planting terrace behind the pond: two raised moss steps with flowering bushes
        for u in range(10, 17):
            for v in range(-6, 7):
                step = 1 if u < 13 else 2
                for yy in range(1, step + 1):
                    put(u, v, D + yy, "minecraft:moss_block" if yy == step else rim)
                if (u + v) % 3 == 0:
                    put(u, v, D + step + 1, BLOOM)
                elif (u * 3 + v) % 5 == 0:
                    put(u, v, D + step + 1, FLOWERS[(u + v) % len(FLOWERS)])
        # waterfall: 3-wide column in the edge layer from the spout to the ground pool, stone cheeks either side
        for v in (-1, 0, 1):  # water reads pale in a ghost: a light-blue core with white foam bands makes the fall visible
            for yy in range(gy + 1, D + 1):
                put(0, v, yy, "minecraft:white_concrete" if yy % 4 == 0 else ("minecraft:light_blue_concrete" if v == 0 else water))
            put(0, v, gy, water)
        for v in (-2, 2):
            for yy in range(gy, D + 1):
                put(0, v, yy, rim if yy % 4 else S.K.get("band", S.K["glow"]))
        # ground pool + rim
        for u in range(-1, -4, -1):
            for v in range(-4, 5):
                put(u, v, gy, water)
        for u in range(-1, -5, -1):
            for v in range(-5, 6):
                if u == -4 or abs(v) == 5:
                    put(u, v, gy, rim)
        for v in range(-4, 5):
            if abs(v) >= 2:
                put(0, v, gy, rim)
        # cut the wing blocks under the new cells (roof plants, edge plinth) so the ghosts do not overlap
        ox, oy, oz = wg["origin"]
        cut = {(x, y, z) for (x, z), y in cells}
        wg["blocks"] = [b for b in wg["blocks"] if (b[0] + ox, b[1] + oy, b[2] + oz) not in cut]
        S.porch_cells |= cut  # also cuts the wall-greenery features ghost (filtered by porch_cells in finish)
        out += [[x, y, z, b] for ((x, z), y), b in cells.items()]
        done += 1
    if out:
        S.add("roofgarden", 0, 0, 0, out, {"kind": "roofgarden"})


def _gothic_porch(S, f):
    x0, z0, w, d, door, ty = f["x"], f["z"], f["w"], f["d"], f["door"], f["ty"]
    B = _porch(S.K)
    y = STEPS + ty
    out = []
    for (u, v, yy), b in B.items():
        if door == "s":
            x, z = x0 + w // 2 + v, z0 + d - 1 + u
        elif door == "n":
            x, z = x0 + w // 2 - v, z0 - u
        elif door == "e":
            x, z = x0 + w - 1 + u, z0 + d // 2 - v
        else:
            x, z = x0 - u, z0 + d // 2 + v
        out.append([x, y + yy, z, b])
    S.porch_cells |= {(x, yy, z) for x, yy, z, _ in out}
    for g in S.ghosts:  # the promenade runs up to the door: cut its blocks where the porch stands, no overlap
        if g["id"] == "halls":
            g["blocks"] = [b for b in g["blocks"] if (b[0], b[1], b[2]) not in S.porch_cells]
    S.add("porch_" + str(f["i"]), 0, 0, 0, out, {"kind": "porch"})


def _finish_site(S, garth=None, tiers=None, X=0, extra_used=None):
    """Halls, features, platform (or terrace tiers), gardens; shift so the site's min corner is (0, 0)."""
    K, kit = S.K, S.kit
    used, allhall = S.finish()
    used = used | (extra_used or set())
    pave = S.occupied | allhall
    wood = _wood(K, kit)
    grounds = S.grounds
    platform, tier_blocks = [], []
    if tiers:
        regions = [(ty, zlo, zhi, -X, X) for ty, zlo, zhi in tiers]
        top_ty = max(t[0] for t in tiers)
    else:
        cells = pave | (extra_used or set())
        if garth:
            cells |= _cells(*garth)
        regions = [(0, min(z for x, z in cells) - 2, max(z for x, z in cells) + 2,
                    min(x for x, z in cells) - 2, max(x for x, z in cells) + 2)]
        top_ty = 0
    pathcells = {}
    for ty, zlo, zhi, x0, x1 in regions:
        pathcells[ty] = _plan_yards(grounds, x0, x1, zlo, zhi, STEPS + ty, used | (_cells(*garth) if garth else set()),
                                    K, kit, wood, (S.seed + ty * 5))
    pathblk = K["wall2"]
    for ty, zlo, zhi, x0, x1 in regions:
        yg = STEPS - 1 + ty
        for x in range(x0, x1 + 1):
            for z in range(zlo, zhi + 1):
                top = K["base"] if (x, z) in pave else (pathblk if (x, z) in pathcells[ty] else "minecraft:grass_block")
                (platform if ty == 0 else tier_blocks).append([x, yg, z, top])
                if ty and (z == zhi or abs(x) == X or (ty == top_ty and z == zlo)):
                    for yy in range(STEPS, yg):  # retaining wall, leaf pockets in the top two courses
                        leaf = z == zhi and yy >= yg - 2 and x % 3 == 0
                        tier_blocks.append([x, yy, z, LEAFWALL if leaf else (K["wall2"] if yy % 3 == 0 else K["base"])])
    if garth:
        _garth(grounds, garth[0], garth[1], garth[2], garth[3], STEPS, K, S.seed, wood)
    S.add("grounds", 0, 0, 0, grounds, {"kind": "grounds"})
    if tier_blocks:
        S.add("tiers", 0, 0, 0, tier_blocks, {"kind": "tiers"})
    if S.extra:
        S.add("stairs", 0, 0, 0, S.extra, {"kind": "stairs"})
    ghosts = [{"id": "platform", "origin": [0, 0, 0], "blocks": platform, "meta": {"kind": "platform"}}] + S.ghosts
    xmin = min(r[3] for r in regions)
    zmin = min(r[1] for r in regions)
    for g in ghosts:
        g["origin"][0] -= xmin
        g["origin"][2] -= zmin
    return [g for g in ghosts if g["blocks"]]


LEAFWALL = "minecraft:azalea_leaves[persistent=true]"


def _plan_sizes(wings):
    return [SIZES.get(str(w.get("size", "m"))[:1], SIZES["m"]) for w in wings]


def _build_radial_linear(kit, wings, landmark, roles, seed, layout):
    S = _Site(kit, roles, seed, layout)
    n = len(wings)
    sizes = _plan_sizes(wings)
    place = []
    maxw = max(s[0] for s in sizes)
    for i, wing in enumerate(wings):
        w, d = sizes[i]
        if layout == "radial":
            side, ring = ("e", "s", "w")[i % 3], i // 3
            if side == "s":
                place.append((i, -w // 2 + ring * 40, 32 + ring * 48, w, d, "n"))
            else:
                w, d = d, w
                x = 32 + ring * 48 if side == "e" else -32 - w - ring * 48
                place.append((i, x, -d // 2 + ring * 40, w, d, "w" if side == "e" else "e"))
        elif i > 0:  # linear: wing 0 is the habitat ring round the hub
            j = i - 1
            place.append((i, 36 + (j // 2) * (maxw + 12), -d - 12 if j % 2 == 0 else 12, w, d,
                          "s" if j % 2 == 0 else "n"))
    S.hubs(["e", "w", "s"] + (["n"] if landmark == "tower" else []))
    if landmark == "tower":
        S.tower_at(0, -33)
    elif landmark == "spire":
        S.add("spire", -4, STEPS, -35, massing.spire(h=45, base=9, kit=kit, roles=roles))
    net = {(0, z) for z in range(-26 if landmark == "tower" else 17, 23)}
    if layout == "radial":
        net |= {(x, 0) for x in range(-22, 23)}
    else:
        r_out, r_in, a0, a1 = 44, 30, 60, 250
        ox, oz = _ring_origin(r_out, r_in, a0, a1)
        w0 = wings[0]
        rr = dict(roles or {})
        rr.update(w0.get("roles") or {})
        rr.setdefault("glass", "minecraft:light_blue_stained_glass")
        blocks = massing.structure("ring", r=r_out, r_in=r_in, a0=a0, a1=a1, kit=kit, roles=rr, floor_hs=[9, 6],
                                   program=[w0.get("rooms") or ["living", "workshop"],
                                            w0.get("upper") or ["living", "storage"]], entrances=[],
                                   roof="flat", windows="band", accent_floor=0, seed=seed, core="elevator")
        Y = STEPS
        K = S.K
        for box in (((-r_in - 3, -r_in + 3), (Y + 1, Y + 3), (-1, 1)), ((-1, 1), (Y + 1, Y + 3), (r_in - 3, r_in + 3))):
            blocks = _carve(blocks, ox, Y, oz, box)
            (bx0, bx1), _, (bz0, bz1) = box
            for x in range(bx0, bx1 + 1):
                for z in range(bz0, bz1 + 1):
                    blocks.append([x - ox, 4, z - oz, K["glow"]])
        S.add("wing_" + str(w0.get("name", 0)), ox, Y, oz, blocks,
              {"kind": "wing", "floor_y": Y + 1, "deck_y": Y + 17, "door": "ring", "roof": "flat",
               "rooms": w0.get("rooms"), "shape": "ring"})
        cells = {(x + ox, z + oz) for x, z in massing.fp_ring(r_out, r_in, a0, a1)}
        S.blocked |= cells
        S.obstacles |= _expand(cells, 3)
        S.occupied |= _expand(cells, 3)
        xend = max([x + w for (_, x, z, w, d, dr) in place] or [20])
        net |= {(x, 0) for x in range(-r_in - 1, xend)} | {(0, z) for z in range(17, r_in + 2)}
    S.levels[0] = _expand(net)
    for (i, x, z, w, d, door) in place:
        S.wing(i, wings[i], x, z, w, d, door)
    S.connect(net)
    return S


def _build_cloister(kit, wings, landmark, roles, seed):
    S = _Site(kit, roles, seed, "cloister")
    n = len(wings)
    sizes = _plan_sizes(wings)
    sides = [("w", "e", "s")[i % 3] for i in range(n)]
    by = {s: [i for i in range(n) if sides[i] == s] for s in "wes"}
    stack = lambda idx, k: sum(sizes[i][k] for i in idx) + 10 * max(0, len(idx) - 1)
    Wr = max(64, stack(by["s"], 0) + 4)
    Dr = max(52, stack(by["w"], 1) + 4, stack(by["e"], 1) + 4)
    rx0, rz0 = -Wr // 2, 24
    rx1, rz1 = rx0 + Wr, rz0 + Dr
    S.hubs(["s"] + (["n"] if landmark == "tower" else []))
    if landmark == "tower":
        S.tower_at(0, -33)
    elif landmark == "spire":
        S.add("spire", -4, STEPS, -35, massing.spire(h=45, base=9, kit=kit, roles=roles))
    centre = set()
    for x in range(rx0 + 2, rx1 - 1):
        centre |= {(x, rz0 + 2), (x, rz1 - 2)}
    for z in range(rz0 + 2, rz1 - 1):
        centre |= {(rx0 + 2, z), (rx1 - 2, z)}
    centre |= {(0, z) for z in range(-26 if landmark == "tower" else 17, rz0 + 3)}
    garth = (rx0 + 5, rz0 + 5, Wr - 9, Dr - 9)
    S.levels[0] = _expand(centre)
    S.obstacles |= _cells(*garth)
    S.occupied |= _cells(rx0 - 2, rz0 - 2, Wr + 5, Dr + 5)
    zc = (rz0 + rz1) // 2
    for sd in "we":
        z = zc - stack(by[sd], 1) // 2
        for i in by[sd]:
            w, d = sizes[i]
            S.wing(i, wings[i], rx0 - 9 - w if sd == "w" else rx1 + 10, z, w, d, "e" if sd == "w" else "w")
            z += d + 10
    x = -stack(by["s"], 0) // 2
    for i in by["s"]:
        w, d = sizes[i]
        S.wing(i, wings[i], x, rz1 + 10, w, d, "n")
        x += w + 10
    S.connect(set(centre))
    return S, garth


def _build_terraces(kit, wings, landmark, roles, seed):
    S = _Site(kit, roles, seed, "terraces")
    K = S.K
    n = len(wings)
    sizes = _plan_sizes(wings)
    R = RISE
    flank = list(range(min(2, n)))
    rest = list(range(len(flank), n))
    half = (len(rest) + 1) // 2
    rows = {1: rest[:half], 2: rest[half:]}
    S.hubs(["e", "w", "n"])
    hall0 = {(0, z) for z in range(-20, -16)}
    for k, i in enumerate(flank):
        w, d = sizes[i]
        if k == 0:
            S.wing(i, wings[i], -23 - w, -(d // 2), w, d, "e")
            hall0 |= {(x, 0) for x in range(-24, -16)}
        else:
            S.wing(i, wings[i], 23, -(d // 2), w, d, "w")
            hall0 |= {(x, 0) for x in range(17, 24)}
    S.levels[0] = _expand(hall0)
    zs = {1: -26}
    tiers, xext, stair_used = [], [50], set()
    two = bool(rows[2]) or landmark == "tower"
    for tk in (1, 2):
        if tk == 2 and not two:
            break
        idx, ty, zsk = rows[tk], tk * R, zs[tk]
        tower_here = tk == 2 and landmark == "tower"
        cut = len(idx) // 2 if tower_here else (len(idx) + 1) // 2
        L, Rr = idx[:cut], idx[cut:]
        walk_x0, walk_x1, zmin_w = -3, 3, zsk - 4
        xl = -6
        for i in L:
            w, d = sizes[i]
            xl -= w
            z0 = zsk - 4 - d
            S.wing(i, wings[i], xl, z0, w, d, "s", ty)
            walk_x0 = min(walk_x0, xl + w // 2 - 3)
            zmin_w = min(zmin_w, z0)
            xl -= 9
        xr = 6
        for i in Rr:
            w, d = sizes[i]
            z0 = zsk - 4 - d
            S.wing(i, wings[i], xr, z0, w, d, "s", ty)
            walk_x1 = max(walk_x1, xr + w // 2 + 3)
            zmin_w = min(zmin_w, z0)
            xr += w + 9
        if tower_here:
            tcz = zsk - 12
            S.tower_at(0, tcz, ty)
            zmin_w = min(zmin_w, tcz - 8)
        S.levels.setdefault(ty, set()).update((x, z) for x in range(walk_x0, walk_x1 + 1) for z in range(zsk - 4, zsk + 1))
        S.gaps.setdefault(ty, set()).update((x, zsk) for x in range(-2, 3))
        xext += [walk_x0 - 14, walk_x1 + 14, xl - 12, xr + 12]
        if tk == 1:
            if two:
                zs[2] = zmin_w - 3 - R
                S.levels[ty].update((x, z) for x in range(-2, 3) for z in range(zs[2] + R + 1, zsk - 4))
                tiers.append((ty, zs[2] + 1, zsk))
            else:
                tiers.append((ty, zmin_w - 8, zsk))
        else:
            tiers.append((ty, zmin_w - 8, zsk))
    X = max(abs(v) for v in xext)
    tiers.insert(0, (0, zs[1] + 1, 34))
    # stairs between tiers, inside the five-wide landings
    for tk in (1, 2):
        if tk in zs and (tk == 1 or two):
            _stairs_up(S.extra, -2, 2, zs[tk], (tk - 1) * R, K)
            stair_used |= {(x, z) for x in range(-4, 5) for z in range(zs[tk] + 1, zs[tk] + R + 1)}
    return S, tiers, X, stair_used


def build(kit="hextech", wings=None, home=True, landmark="tower", roles=None, seed=1, layout=None):
    """Style-specific horizontal campuses. layout overrides the kit's default archetype."""
    layout = layout or LAYOUTS.get(kit, "spine")
    CUR_KIT[0] = kit if isinstance(kit, str) else ""
    if layout not in LAYOUT_NAMES:
        raise ValueError("unknown layout: " + str(layout))
    if layout == "spine":
        return _legacy_build(kit, wings, home, landmark, roles, seed)
    wings = list(wings or [])
    if home:
        wings.insert(0, {"name": "home", "rooms": ["living", "living", "workshop", "storage"]})
    wings = wings or [{"name": "machines", "rooms": ["mod_room", "expansion"]}]
    if layout in ("radial", "linear"):
        return _finish_site(_build_radial_linear(kit, wings, landmark, roles, seed, layout))
    if layout == "cloister":
        S, garth = _build_cloister(kit, wings, landmark, roles, seed)
        return _finish_site(S, garth=garth)
    S, tiers, X, stair_used = _build_terraces(kit, wings, landmark, roles, seed)
    return _finish_site(S, tiers=tiers, X=X, extra_used=stair_used)
