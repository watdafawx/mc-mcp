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


REAL_PARTS = True  # Create emblem from real cogwheels (ghosts draw block-entity parts); False = the fake dark-oak disc


def _create_fake(r=5):
    # fallback when kinetic parts do not draw: dark-oak wheel, andesite-alloy teeth, brass hub
    return disc(r, "minecraft:dark_oak_planks", "create:andesite_alloy_block", "create:brass_block")


def _create(r=5):
    """v26: dark panel (black concrete) with a brass rim, and a diagonal chain of REAL cogwheels standing 1 block proud of it
    (layer 1, axis set per facade by the caller via {AX}): r>=7: large/small/large/small/large (diagonal neighbours mesh),
    r<7: large/small/large. Cells are (u, v, block, layer)."""
    if not REAL_PARTS:
        return [(u, v, b, 0) for (u, v, b) in _create_fake(r)]
    out = []
    for u in range(-r - 1, r + 2):
        for v in range(-r - 1, r + 2):
            d = math.hypot(u, v)
            if d <= r + 0.4:
                rim = d >= r - 1.0
                out.append((u, v, "create:brass_block" if rim else "minecraft:black_concrete", 0))
    L, S = "create:large_cogwheel[axis={AX}]", "create:cogwheel[axis={AX}]"
    k = 2 if r >= 7 else 1
    for t in range(-k, k + 1):
        out.append((t, t, L if t % 2 == k % 2 else S, 1))
    return out


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


def _line(cells, a, b, blk):
    """Rasterise a straight line of blocks from cell a to cell b (u, v)."""
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
    for i in range(n + 1):
        u, v = round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n)
        cells[(u, v)] = blk


def _ars_nouveau():
    # v27: purple disc, gold rim (gilded sourcestone), a six-point source star in source gem blocks, lit hub
    cells = {}
    for (u, v, b) in _ring(5, "minecraft:gold_block", "minecraft:black_concrete"):
        cells[(u, v)] = b
    pts = [(round(4 * math.cos(math.radians(90 + 60 * i))), round(4 * math.sin(math.radians(90 + 60 * i)))) for i in range(6)]
    for i in range(6):
        _line(cells, pts[i], pts[(i + 2) % 6], "ars_nouveau:source_gem_block")
    cells[(0, 0)] = "minecraft:sea_lantern"
    return [(u, v, b) for (u, v), b in cells.items()]


def _occultism():
    # v27: black disc, purple otherstone rim, red pentagram (inverted, point down) with a gold centre
    cells = {}
    for (u, v, b) in _ring(5, "occultism:otherstone_bricks", "minecraft:black_concrete"):
        cells[(u, v)] = b
    pts = [(round(4 * math.cos(math.radians(270 + 72 * i))), round(4 * math.sin(math.radians(270 + 72 * i)))) for i in range(5)]
    for i in range(5):
        _line(cells, pts[i], pts[(i + 2) % 5], "minecraft:red_concrete")
    cells[(0, 0)] = "occultism:iesnium_block"
    return [(u, v, b) for (u, v), b in cells.items()]


def _mysticalagriculture():
    # v27: green disc, inferium rim, a sprout: stem and two leaves in lime on dark green, prosperity hub at the base
    cells = {}
    for (u, v, b) in _ring(5, "mysticalagriculture:inferium_block", "minecraft:green_concrete"):
        cells[(u, v)] = b
    for v in range(-3, 3):
        cells[(0, v)] = "minecraft:lime_concrete"
    for (u, v) in ((1, 0), (2, 0), (2, 1), (3, 1), (3, 2), (1, 1), (2, 2), (1, 2), (2, 3), (1, 3)):  # two leaf blades
        cells[(u, v)] = "minecraft:lime_concrete"
        cells[(-u, v)] = "minecraft:lime_concrete"
    cells[(0, -3)] = "mysticalagriculture:prosperity_block"
    cells[(0, 3)] = "mysticalagriculture:prosperity_block"
    return [(u, v, b) for (u, v), b in cells.items()]


def _productivebees():
    # v27: hexagon of honeycomb with black bee stripes and yellow/orange rim
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = max(abs(v) / 0.866, abs(u) + abs(v) * 0.5)
            if d > 5.2:
                continue
            if d > 4.0:
                b = "minecraft:orange_concrete"
            elif v % 2 == 0:
                b = "minecraft:black_concrete"
            else:
                b = "minecraft:yellow_concrete" if d > 1.0 else "minecraft:honeycomb_block"
            out.append((u, v, b))
    return out


def _enderio():
    # v27: dark steel disc, vibrant (green) ring, black field, end steel cross and a pearl hub (conduit look)
    cells = {}
    for (u, v, b) in _ring(5, "enderio:dark_steel_block", "minecraft:black_concrete"):
        cells[(u, v)] = b
    for (u, v, b) in _ring(3, "enderio:vibrant_alloy_block"):
        cells[(u, v)] = b
    for t in range(-2, 3):
        cells[(t, 0)] = "enderio:end_steel_block"
        cells[(0, t)] = "enderio:end_steel_block"
    cells[(0, 0)] = "enderio:pulsating_alloy_block"
    return [(u, v, b) for (u, v), b in cells.items()]


EMBLEMS = {"create": _create, "mekanism": _mekanism, "powah": _powah, "bigreactors": _bigreactors,
           "industrialforegoing": _industrialforegoing, "ars_nouveau": _ars_nouveau, "occultism": _occultism,
           "mysticalagriculture": _mysticalagriculture, "productivebees": _productivebees, "enderio": _enderio}
# lintel band (three rows) in the mod colours
BANDS = {"create": ("create:brass_block", "create:andesite_alloy_block"),
         "mekanism": ("minecraft:cyan_concrete", "minecraft:black_concrete"),
         "powah": ("minecraft:blue_concrete", "minecraft:sea_lantern"),
         "bigreactors": ("minecraft:yellow_concrete", "minecraft:black_concrete"),
         "industrialforegoing": ("minecraft:orange_concrete", "minecraft:black_concrete"),
         "ars_nouveau": ("minecraft:gold_block", "minecraft:purple_concrete"),
         "occultism": ("minecraft:red_concrete", "minecraft:black_concrete"),
         "mysticalagriculture": ("mysticalagriculture:inferium_block", "minecraft:lime_concrete"),
         "productivebees": ("minecraft:yellow_concrete", "minecraft:black_concrete"),
         "enderio": ("enderio:vibrant_alloy_block", "enderio:dark_steel_block")}
R = 5  # emblem radius of the two door flankers; the single emblem on each of the other three sides is RBIG
RBIG = {"create": 7}


def facade(theme, x0, z0, w, d, y, H, door):
    """[x, y, z, block] cells in absolute coordinates, y = wing base level: a three-row lintel band round all four sides
    (rows H-3..H-1 above y, wider and brass for Create), two r=5 emblems flanking the door at a quarter and three quarters of
    the door side, and ONE big emblem (r=7 for Create) centred on each of the other three sides, so the outward side of a
    wing (the one the judge camera and the visitor see) is signed whichever side the door is on. Emblems stand 1+r above y
    (they may rise above a low wall, like a signboard). Emblem cells override the band."""
    if theme not in EMBLEMS:
        return []
    cells = {}
    a, b = BANDS[theme]
    plane = {"n": z0 - 1, "s": z0 + d, "w": x0 - 1, "e": x0 + w}
    out_ = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}

    def at(sd, t, yy, layer):  # absolute x,y,z of lateral offset t (from the wing's min corner) on side sd, layer 0/1 outwards
        ox, oz = out_[sd]
        if sd in "ns":
            return (x0 + t, yy, plane[sd] + oz * layer)
        return (plane[sd] + ox * layer, yy, z0 + t)

    for sd in "nsew":
        n = w if sd in "ns" else d
        for t in range(-1, n + 1):
            for k, blk in ((H - 3, a), (H - 2, b if t % 2 else a), (H - 1, a)):
                cells[at(sd, t, y + k, 0)] = blk
    for sd in "nsew":
        n = w if sd in "ns" else d
        if sd == door:
            spots = [(n // 4, R), (n - 1 - n // 4, R)]
        else:
            spots = [(n // 2, RBIG.get(theme, R))]
        for (c, r) in spots:
            ax = "z" if sd in "ns" else "x"
            for cell in EMBLEMS[theme](r) if theme == "create" else EMBLEMS[theme]():
                u, v, blk = cell[0], cell[1], cell[2]
                layer = cell[3] if len(cell) > 3 else 0
                t = c + (u if sd in "sw" else -u)  # viewer's right: n -> -x, s -> +x, w -> +z, e -> -z
                cells[at(sd, t, y + 1 + r + v, layer)] = blk.replace("{AX}", ax)
    return [[x, yy, z, blk] for (x, yy, z), blk in cells.items()]
