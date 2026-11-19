"""Small 2D shape helpers shared by interiors.py (mod-room pieces) and campus.py (facade emblems).

Ghost note: Create's rotating parts (shaft, cogwheel, large cogwheel, water wheel, flywheel, belt, ...) are drawn by block
entity renderers, so the ghost mesh (baked block models only) shows nothing for them. The substitutes below are built from
blocks that do render. Cells are (u, v, block): u horizontal, v up, (0, 0) the centre.
"""
from __future__ import annotations

import math


def disc(r, body, teeth, hub, spokes=True, ring=None):
    """Cogwheel disc: hub in the middle, rim ring (`ring`, default `body`), teeth outside the rim (alternating sectors),
    and for r >= 3 open gaps between 8 spokes so it reads as a wheel, not a plate."""
    ring = ring or body
    nt = max(6, int(r * 2))
    out = []
    for u in range(-r - 1, r + 2):
        for v in range(-r - 1, r + 2):
            d = math.hypot(u, v)
            ang = math.degrees(math.atan2(v, u)) % 360
            b = None
            if d <= 0.6 or (r >= 3 and d <= 1.5):
                b = hub
            elif d <= r - 0.4:
                if r <= 2 or d >= r - 1.4:
                    b = ring if d >= r - 1.4 else body
                else:
                    near = min(ang % 45, 45 - ang % 45)
                    if near * math.pi / 180 * d < 0.8:
                        b = body
            elif d <= r + 0.7 and (ang % (360 / nt)) < (180 / nt):
                b = teeth
            if b:
                out.append((u, v, b))
    return out


def put_plane(put, cells, cx, cy, cz, plane="z", thick=1):
    """Stamp (u, v, block) cells around (cx, cy, cz): plane 'z' = x-y wheel, 'x' = z-y wheel, 'y' = flat x-z wheel.
    `thick` layers centred on the plane (1: just it, 2: it and +1, 3: -1..+1)."""
    ks = {1: (0,), 2: (0, 1), 3: (-1, 0, 1)}[thick]
    for (u, v, b) in cells:
        for k in ks:
            if plane == "z":
                put(cx + u, cy + v, cz + k, b)
            elif plane == "x":
                put(cx + k, cy + v, cz + u, b)
            else:
                put(cx + u, cy + k, cz + v, b)
