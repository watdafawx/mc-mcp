"""Per-wing style features that scan the finished wing blocks: gothic roof/crowns/porch, steam roofworks, solar deck,
station radar and the solarpunk roof terraces."""
from __future__ import annotations

import math
import random

from .common import BLOOM, FLOWERS, LEAF, STEPS
from .facades import _chimney
from .landmarks import _porch

def _gothic_roof(ghosts, x0, z0, feat):
    """v21 gothic roof crown: dark lead-look roofs get ridge cresting (blackstone wall comb), spirelets (stone-brick wall +
    lightning rod) on the ridge ends, every 7th ridge cell and the four eave corners. All stand on roof blocks."""
    wg = next((g for g in ghosts if g["id"].startswith("wing_") and g["origin"][0] == x0 and g["origin"][2] == z0), None)
    if not wg:
        return
    ox, oy, oz = wg["origin"]
    top = {}
    for bx, by, bz, _b in wg["blocks"]:
        if top.get((bx, bz), -1) < by:
            top[(bx, bz)] = by
    if not top:
        return
    mx = max(top.values())
    ridge = sorted(p for p, v in top.items() if v == mx)
    # v22: light stone trim lines IN the roof surface: every 4th height band and the eave row become stone bricks / slate
    # (same cells, no new blocks); the ridge row is stone brick slab-free full block (smooth stone already), gable ends stay stone.
    lo_ = min(top.values())
    for bl in wg["blocks"]:
        px_, py_, pz_ = bl[0], bl[1], bl[2]
        if top.get((px_, pz_)) != py_ or py_ <= lo_ - 1 or ":" not in bl[3]:
            continue
        nm = bl[3].split("[")[0]
        if nm in ("minecraft:deepslate_tiles", "minecraft:polished_blackstone_bricks", "minecraft:blackstone", "minecraft:polished_deepslate",
                  "minecraft:deepslate_bricks", "minecraft:cobbled_deepslate"):
            band = (mx - py_) % 4
            if py_ == lo_ or band == 0 and py_ != mx:
                bl[3] = "minecraft:stone_bricks" if (px_ + pz_) % 2 else "minecraft:andesite"
            elif band == 2 and len(ridge) < len(top) * 0.6:
                bl[3] = "minecraft:cobbled_deepslate"
    xs = [p[0] for p in top]
    zs = [p[1] for p in top]
    def put(x, y, z, b):
        feat.append([ox + x, oy + y, oz + z, b])
    def spire(x, z, h):
        y = top[(x, z)] + 1
        for k in range(h):
            put(x, y + k, z, "minecraft:stone_brick_wall")
        put(x, y + h, z, "minecraft:lightning_rod")
    if len(ridge) < len(top) * 0.6:  # a real ridge, not a plateau
        for n, (x, z) in enumerate(ridge):
            if n % 7 == 3:
                spire(x, z, 3)
            else:
                put(x, mx + 1, z, "minecraft:polished_blackstone_brick_wall")
        for (x, z) in (ridge[0], ridge[-1]):
            spire(x, z, 5)
    for c in {(min(xs), min(zs)), (min(xs), max(zs)), (max(xs), min(zs)), (max(xs), max(zs))}:
        base_y = top.get(c)
        for q in [c] + [(c[0] + a, c[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]:
            if q in top and (base_y is None or top[q] >= base_y - 1):
                spire(q[0], q[1], 4)
                break


def _gothic_crowns(ghosts, feat):
    """v22: real forms for the gothic hub dome roof and the tower roof (light stone, cheap): hub = octagonal glazed lantern
    drum + stepped cap + spire + 8 corner pinnacles; tower = stepped stone pyramid spire with light bands + corner pinnacles."""
    def lay(g):
        d = {}
        for bx, by, bz, _b in g["blocks"]:
            d.setdefault(by, set()).add((bx, bz))
        return d
    hub = next((g for g in ghosts if g["id"] == "hub"), None)
    if hub:
        ox, oy, oz = hub["origin"]
        ly = lay(hub)
        ty = max((y for y, c in ly.items() if len(c) >= 80), default=None)
        if ty is not None:
            hub["blocks"] = [b for b in hub["blocks"] if b[1] <= ty]  # drop the old chain / lantern finial
            pl = ly[ty]
            cx = round(sum(p[0] for p in pl) / len(pl))
            cz = round(sum(p[1] for p in pl) / len(pl))
            def put(x, y, z, b):
                feat.append([ox + x, oy + y, oz + z, b])
            def oct_(r, c):
                return {(cx + a, cz + b_) for a in range(-r, r + 1) for b_ in range(-r, r + 1) if abs(a) + abs(b_) <= c}
            Y = ty + 1
            drum = oct_(4, 6)
            ring = {p for p in drum if any(q not in drum for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)))}
            for dy in range(5):
                for (x, z) in ring:
                    corner = abs(x - cx) + abs(z - cz) == 6 or abs(x - cx) == 4 and abs(z - cz) <= 0 or abs(z - cz) == 4 and abs(x - cx) <= 0
                    glass = 1 <= dy <= 3 and not corner and (x + z) % 2 == 0
                    put(x, Y + dy, z, "minecraft:orange_stained_glass" if glass else ("minecraft:stone_bricks" if dy in (0, 4) or corner else "minecraft:smooth_stone"))
            for (x, z) in drum - ring:
                put(x, Y + 4, z, "minecraft:stone_bricks")
            for lvl, (r, c, blk) in enumerate(((4, 6, "minecraft:stone_bricks"), (3, 4, "minecraft:deepslate_tiles"), (2, 3, "minecraft:stone_bricks"), (1, 2, "minecraft:deepslate_tiles"))):
                for (x, z) in oct_(r, c):
                    put(x, Y + 5 + lvl, z, blk)
            for k in range(7):
                put(cx, Y + 9 + k, cz, "minecraft:stone_brick_wall")
            put(cx, Y + 16, cz, "minecraft:lightning_rod")
            for ang in range(8):
                import math as _m
                dx_, dz_ = _m.cos(ang * _m.pi / 4), _m.sin(ang * _m.pi / 4)
                p = max(pl, key=lambda q: (q[0] - cx) * dx_ + (q[1] - cz) * dz_)
                for dy in range(2):
                    put(p[0], Y + dy, p[1], "minecraft:stone_bricks")
                for dy in range(2, 5):
                    put(p[0], Y + dy, p[1], "minecraft:stone_brick_wall")
                put(p[0], Y + 5, p[1], "minecraft:lightning_rod")
    tw = next((g for g in ghosts if g["id"] == "tower_top"), None)
    if tw:
        ox, oy, oz = tw["origin"]
        ly = lay(tw)
        ty = max(ly)
        pl = ly[ty]
        xs = [p[0] for p in pl]
        zs = [p[1] for p in pl]
        if len(pl) >= 16 and max(xs) - min(xs) >= 4:
            cx, cz = (min(xs) + max(xs)) // 2, (min(zs) + max(zs)) // 2
            hw = (max(xs) - min(xs)) // 2
            def put(x, y, z, b):
                feat.append([ox + x, oy + y, oz + z, b])
            Y = ty + 1
            lvl = 0
            for r in range(hw, 0, -1):
                for step in range(2):
                    mat = "minecraft:stone_bricks" if (lvl % 4 in (0, 1)) else "minecraft:deepslate_tiles"
                    for a in range(-r, r + 1):
                        for b_ in range(-r, r + 1):
                            if max(abs(a), abs(b_)) == r or lvl == 0:
                                put(cx + a, Y + lvl, cz + b_, mat if max(abs(a), abs(b_)) == r else "minecraft:deepslate_tiles")
                    lvl += 1
            for k in range(6):
                put(cx, Y + lvl + k, cz, "minecraft:stone_brick_wall")
            put(cx, Y + lvl + 6, cz, "minecraft:lightning_rod")
            for sx in (-hw, hw):
                for sz in (-hw, hw):
                    for dy in range(3):
                        put(cx + sx, Y + dy, cz + sz, "minecraft:stone_bricks" if dy < 2 else "minecraft:stone_brick_wall")
                    put(cx + sx, Y + 3, cz + sz, "minecraft:lightning_rod")


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


def _wing_tops(ghosts, x0, z0):
    wg = next((g for g in ghosts if g["id"].startswith("wing_") and g["origin"][0] == x0 and g["origin"][2] == z0), None)
    if not wg:
        return None
    top = {}
    for bx, by, bz, _b in wg["blocks"]:
        if top.get((bx, bz), -1) < by:
            top[(bx, bz)] = by
    return wg["origin"], top


def _slopeworks(K, seed, ghosts, x0, z0, i, feat):
    """Steam v19: structure on SLOPED roofs (hip/gable/barrel/sawtooth): copper seam bands across the slope, dormers on
    the lower rows, a ridge line with lightning rods and two chimney stacks. Everything stands on the roof surface."""
    r = _wing_tops(ghosts, x0, z0)
    if not r:
        return
    (ox, oy, oz), top = r
    eave = min(top.values())
    R = {p: t for p, t in top.items() if t >= eave + 1}
    if len(R) < 40:
        return
    xs, zs = [p[0] for p in R], [p[1] for p in R]
    xa, xb, za, zb = min(xs), max(xs), min(zs), max(zs)
    along_x = (xb - xa) >= (zb - za)
    mx = max(R.values())

    def U(p):
        return p[0] - xa if along_x else p[1] - za

    def nb(p, d):
        return (p[0] + d, p[1]) if along_x else (p[0], p[1] + d)

    def put(p, y, b):
        feat.append([ox + p[0], oy + y, oz + p[1], b])
    seam = "minecraft:waxed_weathered_cut_copper_slab[type=bottom]"
    for p, t in R.items():  # panelling seams every 5 cells + ridge line
        if U(p) % 5 == 0 and t < mx:
            put(p, t + 1, seam)
        if t == mx:
            put(p, t + 1, "minecraft:copper_block" if U(p) % 2 else K["trim"])
            if U(p) % 7 == 3:
                put(p, t + 2, "minecraft:lightning_rod")
    used = set()
    for p, t in sorted(R.items(), key=lambda kv: (kv[0][1], kv[0][0])):  # dormers on the low rows, every 9 along the ridge
        if t > eave + 2 or U(p) % 9 != 4 or p in used:
            continue
        tri = [nb(p, -1), p, nb(p, 1)]
        if not all(c in R and R[c] == t for c in tri) or any(c in used for c in tri):
            continue
        for c in tri:
            used.add(c)
            put(c, t + 1, K["glass"] if c == p else K["trim"])
            put(c, t + 2, K["trim"] if c == p else "minecraft:cut_copper_slab[type=bottom]")
    cand = [p for p, t in R.items() if eave + 2 <= t < mx and all(R.get(q) == t for q in
            ((p[0] + a, p[1] + c) for a in (0, 1) for c in (0, 1)))]
    cand.sort()
    rnd = random.Random(seed + i)
    rnd.shuffle(cand)
    placed = []
    for p in cand:
        if len(placed) >= 2:
            break
        if any(abs(p[0] - q[0]) + abs(p[1] - q[1]) < 12 for q in placed):
            continue
        _chimney(feat, ox + p[0], oz + p[1], oy + R[p] + 1, 4, K)
        placed.append(p)


def _solar_deck(K, seed, ghosts, x0, z0, i, feat):
    """Solar v19: structure on a bare flat wing roof: hedge planters round the rim, a timber pergola over a seating bay,
    raised garden beds with flowers and small trees, glass skylight strips. Cheap survival blocks, all on the deck."""
    r = _wing_tops(ghosts, x0, z0)
    if not r:
        return
    (ox, oy, oz), top = r
    import collections as _c
    my = _c.Counter(top.values()).most_common(1)[0][0]
    plate = {p for p, v in top.items() if v == my}
    ero = {p for p in plate if all((p[0] + a, p[1] + c) in plate for a in range(-2, 3) for c in range(-2, 3))}
    if len(plate) < 60 or len(ero) < 20:
        return
    Y = oy + my + 1
    rnd = random.Random(seed * 7 + i)
    used = set()

    def put(p, y, b):
        feat.append([ox + p[0], y, oz + p[1], b])
    xs, zs = [p[0] for p in ero], [p[1] for p in ero]
    xa, xb, za, zb = min(xs), max(xs), min(zs), max(zs)
    for p in plate:  # planter hedge boxes on the rim cells
        if any((p[0] + a, p[1] + c) not in plate for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))) and (p[0] + p[1]) % 3:
            put(p, Y, "minecraft:moss_block")
            put(p, Y + 1, LEAF if (p[0] + p[1]) % 2 else BLOOM)
    zm = (za + zb) // 2  # skylight strips down the middle, spruce log frame
    for x in range(xa + 2, xb - 1):
        for dz in (0, 1):
            p = (x, zm + dz)
            if p in ero:
                put(p, Y, K["glass"])
                used.add(p)
        for dz in (-1, 2):
            p = (x, zm + dz)
            if p in ero and x % 2 == 0:
                put(p, Y, "minecraft:stripped_spruce_log[axis=x]")
                used.add(p)
    cands = sorted(p for p in ero if p not in used and all((p[0] + a, p[1] + c) in ero and (p[0] + a, p[1] + c) not in used
                                                          for a in range(7) for c in range(5)))
    if cands:  # pergola 7x5: plank pad, fence posts at the corners, slat beams on top
        p0 = cands[len(cands) // 3]
        for a in range(7):
            for c in range(5):
                q = (p0[0] + a, p0[1] + c)
                used.add(q)
                put(q, Y, "minecraft:spruce_planks")
                if a in (0, 6) and c in (0, 4):
                    for dy in range(1, 4):
                        put(q, Y + dy, "minecraft:spruce_fence")
                if c in (0, 4) or a % 2 == 0:
                    put(q, Y + 4, "minecraft:spruce_slab[type=bottom]")
        put((p0[0] + 3, p0[1] + 2), Y + 1, "minecraft:spruce_stairs[facing=east]")
    beds = 0  # garden beds 4x3 with flowers + a few small trees
    for p in sorted(ero, key=lambda q: rnd.random()):
        if beds >= 5:
            break
        cells = [(p[0] + a, p[1] + c) for a in range(4) for c in range(3)]
        if not all(q in ero and all((q[0] + a, q[1] + c) not in used for a in (-1, 0, 1) for c in (-1, 0, 1)) for q in cells):
            continue
        for q in cells:
            used.add(q)
            edge = q[0] in (p[0], p[0] + 3) or q[1] in (p[1], p[1] + 2)
            put(q, Y, K["trim"] if edge else "minecraft:dirt")
            if not edge:
                put(q, Y + 1, BLOOM if rnd.random() < 0.4 else FLOWERS[rnd.randrange(len(FLOWERS))])
        if beds % 2 == 0:
            c = (p[0] + 1, p[1] + 1)
            for dy in range(1, 4):
                put(c, Y + dy, "minecraft:oak_log")
            for a in range(-1, 2):
                for b in range(-1, 2):
                    put((c[0] + a, c[1] + b), Y + 4, LEAF)
        beds += 1


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
