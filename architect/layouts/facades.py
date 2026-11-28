"""Facade and skyline decoration helpers: gears, pipes, chimneys, buttresses, bays, green walls, halo ring."""
from __future__ import annotations

from .common import BLOOM, HEDGE, STEPS

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
    """v22 thick pipe runs: a 3 high x 2 deep teal run (inner layer on the wall ring, outer layer one block off the wall)
    near the eaves, 2 thick risers with elbows, bright copper flanges every 6, wall brackets under the run, valve blocks
    with a lit lamp every 12. Everything touches the wall."""
    pipe, flange, lit = PIPE, PIPE_FLANGE, K["glow"]
    bracket = "minecraft:polished_blackstone_wall"
    ytop = y + max(5, H - 5 - (i % 2))
    ylow = y + 4 + (i % 2)
    for sd in sides:
        if sd in "ns":
            zz = z0 if sd == "n" else z0 + d - 1
            o = -1 if sd == "n" else 1
            run = [(x, zz, 0, o) for x in range(x0 + 1, x0 + w - 1)]
        else:
            xx = x0 if sd == "w" else x0 + w - 1
            o = -1 if sd == "w" else 1
            run = [(xx, z, o, 0) for z in range(z0 + 1, z0 + d - 1)]

        def lay(px, pz, ox_, oz_, yy, b_, both=True):
            out.append([px, yy, pz, b_])
            if both:
                out.append([px + ox_, yy, pz + oz_, b_])

        def horiz(rows, ymid, run_):
            for n, (px, pz, ox_, oz_) in enumerate(run_):
                col = n % 6 == 3
                for dy in (-1, 0, 1):
                    lay(px, pz, ox_, oz_, ymid + dy, flange if col or (dy == 0 and n % 12 == 9) else pipe)
                if col:
                    for dy in (-2, 2):
                        lay(px, pz, ox_, oz_, ymid + dy, flange)
                if n % 12 == 9:  # valve: lamp on top, wheel block on the outer face
                    lay(px, pz, ox_, oz_, ymid + 2, lit, False)
                    out.append([px + ox_ * 2, ymid, pz + oz_ * 2, flange])
                if n % 4 == 1:  # bracket post under the run, down to the plinth
                    for yy in range(max(y + 1, ymid - 4), ymid - 1):
                        out.append([px, yy, pz, bracket])
        horiz(2, ytop, run)
        if sd == sides[0] or (i % 2 and sd == sides[-1]):
            for frac in (0.2, 0.5, 0.8):
                px, pz, ox_, oz_ = run[int(len(run) * frac)]
                for yy in range(y + 1, ytop - 1):
                    lay(px, pz, ox_, oz_, yy, flange if (yy - y) % 6 == 0 else pipe)
                # elbow: bright collar under the run where the riser joins it
                lay(px, pz, ox_, oz_, ytop - 2, flange)
        if len(run) > 20:  # a second, lower run on the long faces
            horiz(1, ylow, run[3:-3])


def _chimney(out, x, z, y0, h, K):
    for dy in range(h):
        for a in (0, 1):
            for b in (0, 1):
                out.append([x + a, y0 + dy, z + b, K["wall"] if dy % 5 else K["trim"]])
    for a in (0, 1):
        for b in (0, 1):
            out.append([x + a, y0 + h, z + b, "minecraft:copper_grate"])
    out.append([x, y0 + h + 1, z, "minecraft:campfire[lit=true]"])


def _gothic_variety(out, x0, z0, w, d, H, y, K, sides, i):
    """v20 gothic facade rhythm, varies per wing i: a = flying buttresses every 6 with a blind pointed arch (tracery panel,
    glass + mullion) on every 2nd bay; b = heavy stepped piers every 5 with an arch in EVERY bay; c = tall flying buttresses
    every 8 with a wide 7-high rose-topped arch every bay. Cheap survival blocks, all against the wall faces."""
    v = i % 3
    step = (6, 5, 8)[v]
    for side in sides:
        L = w if side in "ns" else d
        if L < 17:
            continue
        ts = list(range(4, L - 3, step))
        def at(t, k, dy):
            if side == "n":
                return x0 + t, y + dy, z0 - k
            if side == "s":
                return x0 + t, y + dy, z0 + d - 1 + k
            if side == "w":
                return x0 - k, y + dy, z0 + t
            return x0 + w - 1 + k, y + dy, z0 + t
        for n, t in enumerate(ts):
            if v == 1:  # stepped pier: 2 wide at the foot, 1 wide above a third of the height
                for dy in range((H - 2) // 3):
                    out.append(list(at(t + 1, 1, dy)) + [K["wall"]])
                for dy in range(H - 2):
                    out.append(list(at(t, 1, dy)) + [K["trim"] if dy % 4 else K["wall"]])
                out.append(list(at(t, 1, H - 2)) + [K["trim"]])
                for r in range(1 + n % 2 + 1):
                    out.append(list(at(t, 1, H - 1 + r)) + [K["antenna"] if r else K["trim"]])
                out.append(list(at(t, 1, H + 2 + n % 2)) + [K["tip"]])
            else:
                hp = max(5, H // 2) if v == 0 else max(7, (H * 2) // 3)
                for dy in range(H - 2):
                    out.append(list(at(t, 1, dy)) + [K["trim"] if dy % 4 else K["wall"]])
                for dy in range(hp):
                    out.append(list(at(t, 3, dy)) + [K["trim"] if dy % 4 else K["wall"]])
                for k, dy in ((3, hp), (2, hp + 1), (2, hp + 2), (1, hp + 3)):
                    out.append(list(at(t, k, dy)) + [K["trim"]])
                for k, dy in ((2, hp - 1), (2, hp)):
                    out.append(list(at(t, k, dy)) + [K["wall"]])
                out.append(list(at(t, 1, H - 2)) + [K["trim"]])
                out.append(list(at(t, 1, H - 1)) + [K["antenna"]])
                for r in range(n % 3):
                    out.append(list(at(t, 1, H + r)) + [K["antenna"]])
                out.append(list(at(t, 1, H + n % 3)) + [K["tip"]])
                out.append(list(at(t, 3, hp)) + [K["antenna"]])
                out.append(list(at(t, 3, hp + 1)) + [K["tip"]])
            # blind tracery arch in the bay after this pier
            every = (2, 1, 1)[v]
            if n % every == 0 and n + 1 < len(ts):
                c = t + step // 2
                ha = min(H - 3, (9, 8, 7)[v] + n % 2)
                hw = 2 if v != 2 else 3
                for dy in range(2, ha + 1):
                    top = ha - dy
                    half = hw if top > 2 else max(0, top - (1 if hw == 2 else 0))
                    for a in range(-hw, hw + 1):
                        if abs(a) > half:
                            continue
                        edge = abs(a) == half
                        if edge or dy == 2:
                            blk = K["trim"]
                        elif a == 0 and dy % 3 == 0:
                            blk = K["trim"]
                        else:
                            blk = K["glass"]
                        out.append(list(at(c + a, 1, dy)) + [blk])
                if v == 2:  # rose window over the arch: ring of trim round a glass disc, radius 2
                    cy_ = ha + 3
                    for ddx in range(-2, 3):
                        for ddy in range(-2, 3):
                            r2 = ddx * ddx + ddy * ddy
                            if r2 <= 5 and cy_ + ddy < H - 1:
                                out.append(list(at(c + ddx, 1, cy_ + ddy)) + [K["trim"] if r2 >= 4 else K["glass"]])


def _wing_massing(out, x0, z0, w, d, H, y, K, sides, i, kit):
    """v21 hextech / station_white wing massing variety, per wing i%3, so wings stop reading as one repeated box.
    hextech: 0 pillared colonnade + lintel, 1 corner turrets (3x3 quartz, capped), 2 cornice ledge + glazed oriel bays.
    station_white: 0 full-height fins + stripe, 1 module pods on legs, 2 corner towers + ring ledge. Cheap blocks, all touching walls."""
    v = i % 3
    P = K.get("pillar", K["trim"])
    for side in sides:
        L = w if side in "ns" else d
        if L < 17:
            continue
        def at(t, k, dy, side=side):
            if side == "n":
                return x0 + t, y + dy, z0 - k
            if side == "s":
                return x0 + t, y + dy, z0 + d - 1 + k
            if side == "w":
                return x0 - k, y + dy, z0 + t
            return x0 + w - 1 + k, y + dy, z0 + t
        def put(t, k, dy, b):
            out.append(list(at(t, k, dy)) + [b])
        if kit == "hextech" and v == 0:
            for t in range(3, L - 2, 4):
                for dy in range(0, 7):
                    put(t, 2, dy, P)
                for k in (0, 1):
                    put(t, k, 3, P)
                put(t, 2, 7, K["trim"])
                put(t, 2, 8, K["tip"])
            for t in range(3, L - 2):
                for k in (0, 1, 2):
                    put(t, k, 7, K["trim"])
        elif kit == "hextech" and v == 2:
            for t in range(1, L - 1):
                put(t, 1, H - 2, K["trim"])
            mid = L // 2
            for t in range(mid - 3, mid + 4):
                for dy in range(2, H - 3):
                    edge = abs(t - mid) == 3 or dy in (2, H - 4)
                    put(t, 1, dy, K["trim"] if edge else K["glass"])
                    put(t, 2, dy, K["trim"] if edge else K["glass"])
                put(t, 2, H - 3, K["trim"])
        elif kit == "station_white" and v == 0:
            for t in range(3, L - 2, 4):
                for dy in range(H - 1):
                    put(t, 1, dy, K["trim"])
                    if dy % 6 == 3:
                        put(t, 2, dy, K["accent"])
                put(t, 1, H - 1, K["accent"])
        elif kit == "station_white" and v == 1:
            for t in (L // 4, (3 * L) // 4):
                for a in range(-2, 2):
                    for k in range(1, 5):
                        for dy in range(H - 8, H - 3):
                            edge = a in (-2, 1) or k == 4 or dy in (H - 8, H - 4)
                            put(t + a, k, dy, K["wall"] if edge else (K["glass"] if k == 4 or a in (-1, 0) and dy == H - 6 else K["trim"]))
                for dy in range(H - 8):
                    put(t - 2, 4, dy, K["trim"])
                    put(t + 1, 4, dy, K["trim"])
                put(t, 4, H - 3, K["accent"])
    if (kit == "hextech" and v == 1) or (kit == "station_white" and v == 2):
        tall = H + (3 if kit == "hextech" else 4)
        for cx_, cz_ in ((x0 - 1, z0 - 1), (x0 + w - 2, z0 - 1), (x0 - 1, z0 + d - 2), (x0 + w - 2, z0 + d - 2)):
            for a in range(3):
                for b in range(3):
                    for dy in range(tall):
                        ring = a != 1 or b != 1
                        if not ring and dy < tall - 1:
                            continue
                        glass = (a == 1 or b == 1) and (a != b) and dy % 5 in (2, 3) and dy < tall - 2
                        out.append([cx_ + a, y + dy, cz_ + b, K["glass"] if glass else (P if dy % 4 else K["trim"])])
            out.append([cx_ + 1, y + tall, cz_ + 1, K["tip"]])
            out.append([cx_ + 1, y + tall + 1, cz_ + 1, K["antenna"]])
        if kit == "station_white":
            for t in range(0, w):
                for z_ in (z0 - 1, z0 + d):
                    out.append([x0 + t, y + H - 2, z_, K["accent"]])


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
