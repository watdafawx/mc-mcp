"""Linear layout: a curved habitat ring round the hub (wing 0) and wings in two rows along an eastern spine."""
from __future__ import annotations

import massing

from .common import STEPS, _expand, _plan_sizes, with_home
from .site import Site, finish_site


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


def _plan(kit, wings, landmark, roles, seed):
    S = Site(kit, roles, seed, "linear")
    sizes = _plan_sizes(wings)
    place = []
    maxw = max(s[0] for s in sizes)
    for i in range(1, len(wings)):  # wing 0 is the habitat ring round the hub
        w, d = sizes[i]
        j = i - 1
        place.append((i, 36 + (j // 2) * (maxw + 12), -d - 12 if j % 2 == 0 else 12, w, d, "s" if j % 2 == 0 else "n"))
    S.hubs(["e", "w", "s"] + (["n"] if landmark == "tower" else []))
    S.landmark_at(landmark)
    net = {(0, z) for z in range(-26 if landmark == "tower" else 17, 23)}
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
    S.net = net
    return S


def build(kit, wings, home, landmark, roles, seed):
    return finish_site(_plan(kit, with_home(wings, home), landmark, roles, seed))
