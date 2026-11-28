"""Cloister layout: a rectangular arcade ring round a garth, wings on three sides, hub and tower to the north."""
from __future__ import annotations

from .common import FLOWERS, HEDGE, _cells, _expand, _plan_sizes, _tree, with_home
from .site import Site, finish_site


def _garth(out, x0, z0, w, d, y, K, seed, wood, kit=""):
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
            _tree(out, cx + sx * (w // 4 + 1), cz + sz * (d // 4 + 1), y + 1, wood, seed + sx + 2 * sz, kit)


def _plan(kit, wings, landmark, roles, seed):
    S = Site(kit, roles, seed, "cloister")
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
    S.landmark_at(landmark)
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
    net = set(centre)
    S.connect(net)
    S.net = net
    return S, garth


def build(kit, wings, home, landmark, roles, seed):
    S, garth = _plan(kit, with_home(wings, home), landmark, roles, seed)
    return finish_site(S, garth=garth, draw_garth=_garth)
