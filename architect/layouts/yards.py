"""Yard generators (farm, garden, machine yard, orchard, pond, plaza, market, ramp) and the yard picker/placer."""
from __future__ import annotations

import math

from .common import BLOOM, FLOWERS, HEDGE, _lamp, _tree

CROPS = ("minecraft:wheat[age=7]", "minecraft:carrots[age=7]", "minecraft:potatoes[age=7]", "minecraft:beetroots[age=3]")
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


def _garden(out, x0, z0, n, y, K, rnd, wood, kit=""):
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
        _tree(out, x0 + c, z0 + c, y, wood, rnd, kit)


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


def _pond(out, x0, z0, n, y, K, rnd, wood, kit=""):
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
    _tree(out, x0 + 1, z0 + n - 2, y + 1, wood, rnd, kit)


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


# every yard generator is called as f(out, x0, z0, n, y, K, rnd, wood, kit); kit only reaches the ones that plant trees
YARD_FUNCS = {"farm": lambda o, x, z, n, y, K, r, w, kit: _farm(o, x, z, n, y, K, r),
              "garden": lambda o, x, z, n, y, K, r, w, kit: _garden(o, x, z, n, y, K, r, w, kit),
              "machine": lambda o, x, z, n, y, K, r, w, kit: _machine_yard(o, x, z, n, y, K, r),
              "orchard": lambda o, x, z, n, y, K, r, w, kit: _orchard(o, x, z, n, y, K, r, w),
              "pond": lambda o, x, z, n, y, K, r, w, kit: _pond(o, x, z, n, y, K, r, w, kit),
              "plaza": lambda o, x, z, n, y, K, r, w, kit: _plaza(o, x, z, n, y, K, r, w),
              "market": lambda o, x, z, n, y, K, r, w, kit: _market(o, x, z, n, y, K, r, w),
              "ramp": lambda o, x, z, n, y, K, r, w, kit: _ramp(o, x, z, n, y, K, r, w)}
YARD_BAG = {  # weighted yard kinds per kit: variety instead of 13x13 clones
    "steampunk": ("machine", "machine", "market", "plaza", "farm", "garden", "pond"),
    "hextech": ("plaza", "garden", "pond", "garden", "orchard", "plaza", "pond"),
    "gothic": ("orchard", "garden", "pond", "plaza", "farm", "market", "garden"),
    "station_white": ("machine", "plaza", "ramp", "machine", "pond", "market", "garden"),
    "solarpunk": ("orchard", "farm", "pond", "garden", "market", "orchard", "plaza"),
}


def _small_yard(out, x0, z0, n, y, K, rnd, wood, kit=""):
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
        _tree(out, x0 + n // 2, z0 + n // 2, y + 1, wood, rnd, kit)
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
                    _small_yard(out, gx, gz, n, y, K, r, wood, kit)
                else:
                    YARD_FUNCS[bag[(r + k) % len(bag)]](out, gx, gz, n, y, K, r, wood, kit)
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
