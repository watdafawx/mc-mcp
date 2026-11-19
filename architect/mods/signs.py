"""Facade signage for mod wings (v24): a colour-coded lintel band plus two emblems flanking the door, so the outside of the
wing says which mod is inside. Emblems are 2D (u, v, block) cell lists, (0, 0) = emblem centre, u to the viewer's right.
Pure python; campus.py stamps them flush against the facade (plane just outside the wall) on the door side, and a band on
all four sides."""
from __future__ import annotations

import math

from .shapes import disc


def _ring(r, rim, fill=None, hub=None, hr=1.0):
    out = []
    for u in range(-r, r + 1):
        for v in range(-r, r + 1):
            d = math.hypot(u, v)
            if hub and d <= hr:
                out.append((u, v, hub))
            elif d <= r + 0.3 and d >= r - 1.0:
                out.append((u, v, rim))
            elif fill and d < r - 1.0:
                out.append((u, v, fill))
    return out


def _create():
    # brass + andesite: a big cogwheel (dark-oak wheel, andesite-alloy teeth, brass hub) on a brass ring
    cells = disc(5, "minecraft:dark_oak_planks", "create:andesite_alloy_block", "create:brass_block")
    cells = [(u, v, b) for (u, v, b) in cells]
    return cells


def _mekanism():
    # cyan atom: ring with a centre dot, two crossing orbits as diagonals
    cells = _ring(5, "minecraft:cyan_concrete", "minecraft:black_concrete", "minecraft:sea_lantern", 1.2)
    for t in range(-4, 5):
        cells += [(t, t, "minecraft:light_blue_concrete"), (t, -t, "minecraft:light_blue_concrete")]
    return cells


def _powah():
    # lightning bolt in lit blue on a dark-blue disc
    cells = _ring(5, "minecraft:blue_concrete", "minecraft:blue_concrete")
    bolt = [(1, 4), (0, 4), (0, 3), (-1, 3), (-1, 2), (0, 2), (1, 2), (0, 1), (-1, 1), (0, 0), (-1, 0), (-1, -1), (-2, -1),
            (-2, -2), (-3, -3), (-1, -2), (0, -3)]
    bolt = [(1, 4), (0, 4), (-1, 4), (0, 3), (-1, 3), (-1, 2), (0, 2), (1, 2), (2, 2), (0, 1), (1, 1), (0, 0), (1, 0),
            (0, -1), (1, -1), (-1, -1), (0, -2), (0, -3), (-1, -3)]
    for (u, v) in bolt:
        cells = [c for c in cells if (c[0], c[1]) != (u, v)] + [(u, v, "minecraft:sea_lantern")]
    return cells


def _bigreactors():
    # yellow/black radiation trefoil: black disc, 3 yellow sectors, hub
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = math.hypot(u, v)
            if d > 5.3:
                continue
            ang = math.degrees(math.atan2(v, u)) % 360
            if d <= 1.2:
                b = "minecraft:yellow_concrete"
            elif d <= 4.8 and (ang + 30) % 120 < 60 and d >= 1.8:
                b = "minecraft:yellow_concrete"
            elif d >= 4.8:
                b = "minecraft:yellow_concrete"
            else:
                b = "minecraft:black_concrete"
            out.append((u, v, b))
    return out


def _industrialforegoing():
    # orange/black gear-and-chevron: black disc with an orange chevron arrow and orange rim
    out = _ring(5, "minecraft:orange_concrete", "minecraft:black_concrete")
    for t in range(-3, 4):
        out = [c for c in out if (c[0], c[1]) not in ((t, 2 - abs(t)), (t, 1 - abs(t)))]
        out += [(t, 2 - abs(t), "minecraft:orange_concrete"), (t, 1 - abs(t), "minecraft:orange_concrete")]
    return out


EMBLEMS = {"create": _create, "mekanism": _mekanism, "powah": _powah, "bigreactors": _bigreactors,
           "industrialforegoing": _industrialforegoing}
# lintel band (two rows) and the pilaster colour beside the emblems
BANDS = {"create": ("create:brass_block", "create:andesite_alloy_block"),
         "mekanism": ("minecraft:cyan_concrete", "minecraft:black_concrete"),
         "powah": ("minecraft:blue_concrete", "minecraft:sea_lantern"),
         "bigreactors": ("minecraft:yellow_concrete", "minecraft:black_concrete"),
         "industrialforegoing": ("minecraft:orange_concrete", "minecraft:black_concrete")}
R = 5  # emblem radius (all emblems fit r=5..6)


def facade(theme, x0, z0, w, d, y, H, door):
    """[x, y, z, block] cells in absolute coordinates: band round all four sides under the roofline (rows H-2, H-1 above y),
    and two emblems flanking the door at a quarter and three quarters of the door side, centre height y+H-8."""
    if theme not in EMBLEMS:
        return []
    out = []
    a, b = BANDS[theme]
    for sd in "nsew":
        plane = {"n": z0 - 1, "s": z0 + d, "w": x0 - 1, "e": x0 + w}[sd]
        n = w if sd in "ns" else d
        for t in range(-1, n + 1):
            for k, blk in ((H - 2, a), (H - 1, b if t % 2 else a)):
                if sd in "ns":
                    out.append([x0 + t, y + k, plane, blk])
                else:
                    out.append([plane, y + k, z0 + t, blk])
    cells = EMBLEMS[theme]()
    n = w if door in "ns" else d
    cy = y + H - 3 - R
    plane = {"n": z0 - 1, "s": z0 + d, "w": x0 - 1, "e": x0 + w}[door]
    for c in (n // 4, n - 1 - n // 4):
        for (u, v, blk) in cells:
            t = c + (u if door in "sw" else -u)  # viewer's right: n -> -x, s -> +x, w -> +z, e -> -z
            if door in "ns":
                out.append([x0 + t, cy + v, plane, blk])
            else:
                out.append([plane, cy + v, z0 + t, blk])
    return out
