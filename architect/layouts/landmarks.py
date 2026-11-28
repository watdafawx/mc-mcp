"""The landmark tower (per-kit stage profiles), the gothic porch and the hextech airdock."""
from __future__ import annotations

import math

import massing

from .common import TOWER_ROOF
from .facades import _cog

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
