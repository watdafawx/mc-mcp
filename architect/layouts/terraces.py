"""Terraces layout: wings climb in garden tiers joined by stairs; the tower stands on the top tier."""
from __future__ import annotations

from .common import RISE, STEPS, _expand, _plan_sizes, with_home
from .site import Site, finish_site

def _stairs_up(out, x0, x1, zs, ty_low, K, rise=RISE):
    """Stairs from tier level ty_low up `rise` blocks to the north: steps in front of a retaining wall at row zs."""
    Yl = STEPS + ty_low
    for i in range(rise):
        z = zs + rise - i
        for x in range(x0, x1 + 1):
            for yy in range(Yl + 1, Yl + 1 + i):
                out.append([x, yy, z, K["base"]])
            out.append([x, Yl + 1 + i, z, "minecraft:stone_brick_stairs[facing=north]"])
        for x in (x0 - 1, x1 + 1):  # balustrade
            for yy in range(Yl + 1, Yl + 2 + i):
                out.append([x, yy, z, K["base"]])
            out.append([x, Yl + 2 + i, z, K["rail"]])


def _plan(kit, wings, landmark, roles, seed):
    S = Site(kit, roles, seed, "terraces")
    K = S.K
    n = len(wings)
    sizes = _plan_sizes(wings)
    R = RISE
    flank = list(range(min(2, n)))
    rest = list(range(len(flank), n))
    half = (len(rest) + 1) // 2
    rows = {1: rest[:half], 2: rest[half:]}
    S.hubs(["e", "w", "n"])
    hall0 = {(0, z) for z in range(-20, -16)}
    for k, i in enumerate(flank):
        w, d = sizes[i]
        if k == 0:
            S.wing(i, wings[i], -23 - w, -(d // 2), w, d, "e")
            hall0 |= {(x, 0) for x in range(-24, -16)}
        else:
            S.wing(i, wings[i], 23, -(d // 2), w, d, "w")
            hall0 |= {(x, 0) for x in range(17, 24)}
    S.levels[0] = _expand(hall0)
    zs = {1: -26}
    tiers, xext, stair_used = [], [50], set()
    two = bool(rows[2]) or landmark == "tower"
    for tk in (1, 2):
        if tk == 2 and not two:
            break
        idx, ty, zsk = rows[tk], tk * R, zs[tk]
        tower_here = tk == 2 and landmark == "tower"
        cut = len(idx) // 2 if tower_here else (len(idx) + 1) // 2
        L, Rr = idx[:cut], idx[cut:]
        walk_x0, walk_x1, zmin_w = -3, 3, zsk - 4
        xl = -6
        for i in L:
            w, d = sizes[i]
            xl -= w
            z0 = zsk - 4 - d
            S.wing(i, wings[i], xl, z0, w, d, "s", ty)
            walk_x0 = min(walk_x0, xl + w // 2 - 3)
            zmin_w = min(zmin_w, z0)
            xl -= 9
        xr = 6
        for i in Rr:
            w, d = sizes[i]
            z0 = zsk - 4 - d
            S.wing(i, wings[i], xr, z0, w, d, "s", ty)
            walk_x1 = max(walk_x1, xr + w // 2 + 3)
            zmin_w = min(zmin_w, z0)
            xr += w + 9
        if tower_here:
            tcz = zsk - 12
            S.tower_at(0, tcz, ty)
            zmin_w = min(zmin_w, tcz - 8)
        S.levels.setdefault(ty, set()).update((x, z) for x in range(walk_x0, walk_x1 + 1) for z in range(zsk - 4, zsk + 1))
        S.gaps.setdefault(ty, set()).update((x, zsk) for x in range(-2, 3))
        xext += [walk_x0 - 14, walk_x1 + 14, xl - 12, xr + 12]
        if tk == 1:
            if two:
                zs[2] = zmin_w - 3 - R
                S.levels[ty].update((x, z) for x in range(-2, 3) for z in range(zs[2] + R + 1, zsk - 4))
                tiers.append((ty, zs[2] + 1, zsk))
            else:
                tiers.append((ty, zmin_w - 8, zsk))
        else:
            tiers.append((ty, zmin_w - 8, zsk))
    X = max(abs(v) for v in xext)
    S.svc_tiers = [{"ty": tk * R, "zsk": zs[tk], "ground_z": zs[1] + R + 3} for tk in (1, 2) if tk in zs and (tk == 1 or two)]
    tiers.insert(0, (0, zs[1] + 1, 34))
    # stairs between tiers, inside the five-wide landings
    for tk in (1, 2):
        if tk in zs and (tk == 1 or two):
            _stairs_up(S.extra, -2, 2, zs[tk], (tk - 1) * R, K)
            stair_used |= {(x, z) for x in range(-4, 5) for z in range(zs[tk] + 1, zs[tk] + R + 1)}
    return S, tiers, X, stair_used


def build(kit, wings, home, landmark, roles, seed):
    S, tiers, X, stair_used = _plan(kit, with_home(wings, home), landmark, roles, seed)
    return finish_site(S, tiers=tiers, X=X, extra_used=stair_used)
