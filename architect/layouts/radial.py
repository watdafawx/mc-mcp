"""Radial layout: wings on spokes round the hub (east, south, west, then outer rings) joined by covered halls."""
from __future__ import annotations

from .common import GAP, _expand, _plan_sizes, with_home
from .site import Site, finish_site


def _plan(kit, wings, landmark, roles, seed):
    S = Site(kit, roles, seed, "radial")
    sizes = _plan_sizes(wings)
    place = []
    pitch = max(48, max(max(s) for s in sizes) + GAP)  # v28: big mod wings push the next ring out
    for i in range(len(wings)):
        w, d = sizes[i]
        side, ring = ("e", "s", "w")[i % 3], i // 3
        if side == "s":
            place.append((i, -w // 2 + ring * (pitch - 8), 32 + ring * pitch, w, d, "n"))
        else:
            w, d = d, w
            x = 32 + ring * pitch if side == "e" else -32 - w - ring * pitch
            place.append((i, x, -d // 2 + ring * (pitch - 8), w, d, "w" if side == "e" else "e"))
    S.hubs(["e", "w", "s"] + (["n"] if landmark == "tower" else []))
    S.landmark_at(landmark)
    net = {(0, z) for z in range(-26 if landmark == "tower" else 17, 23)}
    net |= {(x, 0) for x in range(-22, 23)}
    S.levels[0] = _expand(net)
    for (i, x, z, w, d, door) in place:
        S.wing(i, wings[i], x, z, w, d, door)
    S.connect(net)
    S.net = net
    return S


def build(kit, wings, home, landmark, roles, seed):
    return finish_site(_plan(kit, with_home(wings, home), landmark, roles, seed))
