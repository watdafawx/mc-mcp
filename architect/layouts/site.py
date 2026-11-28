"""The shared _Site accumulator (wings, hub, tower, halls, services) and the finishing pass every non-spine layout uses."""
from __future__ import annotations

import massing
import services

from .common import (HALL_STYLE, HUB_ROOF, LEAFWALL, N4, ROOF_MATS, STEPS, WING_ROLES, GLASS, _cells, _expand,
                     _roof_for, _rooms_door_first, _windows, _wing_mod, _wood)
from .facades import _chimney, _gothic_variety, _greenwall, _pipes, _wing_bays, _wing_massing
from .features import (_gothic_crowns, _gothic_porch, _gothic_roof, _radar, _roof_terraces, _roofworks, _slopeworks,
                       _solar_deck)
from .landmarks import TOWER_STAGES, _airdock, _tower
from .yards import _plan_yards

def _hall(mask, ty, blocked, K, kit, style="glass", gaps=()):
    """A roofed hall over `mask` (cells, ~5 wide): floor, pier + glass (or open pointed arches) on every open side,
    lintel beam, roof with a raised glazed ridge down the middle and glow lamps. Walls are skipped where a building
    already stands. gaps: edge cells left fully open (stair landings)."""
    Y = STEPS + ty
    out = []
    mask, blocked = set(mask), set(blocked)
    solid = mask | blocked
    pier = K.get("pillar", K["trim"])
    gothic = kit == "gothic"
    nb = lambda c: [(c[0] + a, c[1] + b) for a, b in N4]
    edge = {c for c in mask if any(n not in solid for n in nb(c))}
    rim = {c for c in mask if any(n not in mask for n in nb(c))}
    d1 = mask - rim
    d2 = {c for c in d1 if all(n in d1 for n in nb(c))}
    for c in mask:
        x, z = c
        out.append([x, Y, z, K["base"]])
        t = x + z
        if c in edge and c not in gaps:
            corner = sum(n not in solid for n in nb(c)) >= 2
            if style == "open":
                if t % 4 == 0 or corner:
                    for dy in range(1, 5):
                        out.append([x, Y + dy, z, pier])
                else:
                    if gothic and t % 4 in (1, 3):
                        out.append([x, Y + 3, z, K["trim"]])  # pointed arch shoulders
                    out.append([x, Y + 4, z, K["trim"]])
            else:
                door = t % 19 in (8, 9, 10) and not corner  # side opening every ~19 cells
                if (t % 3 == 0 or corner) and not door:
                    for dy in range(1, 5):
                        out.append([x, Y + dy, z, pier])
                else:
                    if not door:
                        for dy in range(1, 4):
                            out.append([x, Y + dy, z, K["glass"]])
                    out.append([x, Y + 4, z, K["trim"]])
        if c in rim:
            out.append([x, Y + 5, z, K["trim"]])
        elif c in d2:
            out.append([x, Y + 6, z, K["glass"]])
            if t % 6 == 0:
                out.append([x, Y + 5, z, K["glow"]])
        else:
            out.append([x, Y + 5, z, K["roof"]])
    return out


class Site:
    def __init__(self, kit, roles, seed, layout):
        self.kit, self.roles, self.seed, self.layout = kit, roles, seed, layout
        self.K = massing._kit(kit, roles)
        self.ghosts, self.foot, self.doors = [], [], []
        self.blocked, self.occupied = set(), set()
        self.levels, self.gaps = {}, {}  # ty -> hall cells / stair-landing gaps
        self.grounds, self.extra = [], []
        self.obstacles = set()
        self.meta = {}
        self.bays = []
        self.porch_cells = set()
        self.svc = []        # v28: mod wings that need services (trench, port wall)
        self.net = None      # hall centre-line cells (BFS for the trench)
        self.svc_tiers = []  # terraces: tier risers

    def add(self, gid, x, y, z, blocks, meta=None):
        self.ghosts.append({"id": gid, "origin": [x, y, z], "blocks": blocks, "meta": meta or {}})

    def reserve(self, cells, pad=3):
        self.occupied |= _expand(cells, pad) if pad else cells

    def wing(self, i, wing, x, z, w, d, door, ty=0):
        K, kit = self.K, self.kit
        wr = dict(self.roles or {})
        wr.update(wing.get("roles") or {})
        wr.setdefault("glass", "minecraft:" + GLASS.get(kit, ["cyan", "light_blue", "gray"])[i % 3] + "_stained_glass")
        for role, block in WING_ROLES.get(kit, {}).items():  # gothic: pale stone wings, orange lancets glow against them
            wr.setdefault(role, block)
        wr.setdefault("wall2", [K["wall2"], K["wall"], K["base"]][i % 3])
        mats = ROOF_MATS.get(kit if isinstance(kit, str) else "")
        if mats and "roof" not in (wing.get("roles") or {}):  # v16: per-wing hue wins over a model-wide roles.roof
            wr["roof"] = mats[i % len(mats)]
        roof = _roof_for(wing, kit, i)
        hs = [int(wing.get("floor_h") or (8 + 2 * (i % 3)))] + [6] * (int(wing.get("floors") or 1) - 1)
        th = _wing_mod(wing)
        rooms0 = _rooms_door_first(wing.get("rooms") or ["expansion"], door, w, d) if th else (wing.get("rooms") or ["expansion"])
        prog = [rooms0] + [wing.get("upper") or ["expansion"]] * (len(hs) - 1)
        services.reset()
        blocks = massing.structure("rect", w=w, d=d, kit=kit, roles=wr, floor_hs=hs, program=prog,
                                   entrances=[door], roof=roof, bay=6 if kit in ("gothic", "hextech") else 4 + i % 3,
                                   windows=wing.get("windows") or _windows(kit, i), rhythm=1 + i % 3, finial=1,
                                   seed=self.seed + i)
        H = sum(hs) + 1
        name = str(wing.get("name", i))
        self.bays += _wing_bays(x, z, w, d, STEPS + ty, hs[0], H, door, K, kit, self.seed + i, i)
        rec = services.take()
        if th:  # v24: facade signage so the outside says which mod is inside
            import mods.signs as _signs
            self.bays += _signs.facade(th, x, z, w, d, STEPS + ty, H, door)
        self.add("wing_" + name, x, STEPS + ty, z, blocks,
                 {"kind": "wing", "floor_y": STEPS + ty + 1, "deck_y": STEPS + ty + H + 1, "door": door,
                  "roof": roof, "rooms": wing.get("rooms")})
        self.foot.append({"x": x, "z": z, "w": w, "d": d, "H": H, "door": door, "ty": ty, "roof": roof, "i": i})
        cells = _cells(x, z, w, d)
        self.blocked |= cells
        self.obstacles |= _expand(cells, 3)
        self.occupied |= _expand(cells, 3)
        ex, ez = {"n": (x + w // 2, z - 1), "s": (x + w // 2, z + d), "w": (x - 1, z + d // 2),
                  "e": (x + w, z + d // 2)}[door]
        self.doors.append((ex, ez, door, ty))
        if th and rec["manifold"]:
            self.svc.append({"name": name, "theme": th, "door": door, "door_cell": (ex, ez), "ty": ty, "i": i,
                             "centre": (x + w // 2, z + d // 2), "w": w, "d": d,
                             "manifold": {(x + a, z + b) for a, b in rec["manifold"]},
                             "risers": [(x + a, z + b) for a, b in rec["risers"]],
                             "bays": [(x + a, z + b, l) for (a, b), l in rec["bays"]]})

    def connect(self, net, ty=0, bound=260):
        """BFS from every wing door to the nearest hall centre line; adds 5-wide halls along each route."""
        from collections import deque
        for ex, ez, door, t in self.doors:
            if t != ty:
                continue
            dx, dz = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}[door]
            start = (ex + dx * 4, ez + dz * 4)
            queue, prev, end = deque([start]), {start: None}, None
            while queue:
                q = queue.popleft()
                if q in net:
                    end = q
                    break
                for a, b in N4:
                    r = (q[0] + a, q[1] + b)
                    if r in prev or r in self.obstacles or abs(r[0]) > bound or abs(r[1]) > bound:
                        continue
                    prev[r] = q
                    queue.append(r)
            if end is None:
                raise ValueError("unreachable wing entrance")
            route = []
            while end is not None:
                route.append(end)
                end = prev[end]
            route += [(ex + dx * k, ez + dz * k) for k in range(5)]
            net.update(route)
            self.levels.setdefault(ty, set()).update(_expand(route))

    def hubs(self, entrances, roof=None):
        K, kit = self.K, self.kit
        roof = roof or HUB_ROOF.get(kit, "crown")
        hub = massing.structure("octagon", w=33, d=33, c=6, kit=kit, roles=self.roles, floor_hs=[12],
                                program=["hall"], entrances=entrances, roof=roof, windows=_windows(kit, 1), seed=self.seed + 60)
        self.add("hub", -16, STEPS, -16, hub, {"kind": "hub", "floor_y": STEPS + 1, "deck_y": STEPS + 13, "roof": roof})
        cells = massing.fp_octagon(33, 33, 6)
        cells = {(x - 16, z - 16) for x, z in cells}
        self.blocked |= cells
        self.obstacles |= _expand(cells, 2)
        self.occupied |= _expand(cells, 3)

    def tower_at(self, cx, cz, ty=0):
        for gid, org, bl in _tower(self.K, self.kit, self.roles, self.seed, cx, cz, STEPS + ty):
            self.add(gid, org[0], org[1], org[2], bl, {"kind": "tower", "floor_y": STEPS + ty + 1})
        if self.kit == "hextech":
            self.airdock(cx, cz, STEPS + ty)
        h0 = TOWER_STAGES.get(self.kit, [("", 15)])[0][1] // 2 + 1
        cells = _cells(cx - h0, cz - h0, 2 * h0 + 1, 2 * h0 + 1)
        self.blocked |= {(x, z) for x, z in cells if (x - cx) ** 2 + (z - cz) ** 2 <= (h0 + 1) ** 2 + h0}
        self.obstacles |= _expand(cells, 2)
        self.occupied |= _expand(cells, 3)

    def landmark_at(self, landmark):
        """The one tall volume north of the hub: a tower with a lift, a spire, or nothing."""
        if landmark == "tower":
            self.tower_at(0, -33)
        elif landmark == "spire":
            self.add("spire", -4, STEPS, -35, massing.spire(h=45, base=9, kit=self.kit, roles=self.roles))

    def airdock(self, cx, cz, y):  # noqa: D401
        """Hextech airship dock + gangway off the tower: pick the free side (east, west, north) and reserve its cells."""
        hw = TOWER_STAGES["hextech"][0][1] // 2
        y_g = y + sum(TOWER_STAGES["hextech"][0][2][:3]) + 3  # fourth floor line
        L, V = 27, 15

        def rect(side, V=V):
            if side in "ew":
                x0 = cx + hw if side == "e" else cx - hw - L
                return _cells(x0, cz - V, L + 1, 2 * V + 1)
            if side == "s":
                return _cells(cx - V, cz + hw + 1, 2 * V + 1, L + 1)
            return _cells(cx - V, cz - hw - L - 1, 2 * V + 1, L + 1)
        # v15: test the deck footprint (+-14) against real obstacles only (not the soft padding), east/west first: they stay
        # visible from the front shot (the hub is lower than the airship); north (behind the tower) is the last resort
        taken = self.obstacles | self.blocked
        side = next((sd for sd in "ewsn" if not (rect(sd, 14) & taken)), None)
        if side is None:
            side = min("ewsn", key=lambda sd: len(rect(sd, 14) & taken))
        B = _airdock(self.K, y_g, hw)
        out = []
        for (u, v, yy), b in B.items():
            if side == "e":
                x, z = cx + hw + u, cz + v
            elif side == "w":
                x, z = cx - hw - u, cz - v
            elif side == "s":
                x, z = cx + v, cz + hw + u
            else:
                x, z = cx - v, cz - hw - u
            out.append([x, yy, z, b])
        self.add("airdock", 0, 0, 0, out, {"kind": "airdock", "side": side})
        self.reserve(rect(side), pad=1)
        self.obstacles |= rect(side)  # halls route round the dock
        self.meta["airdock"] = side

    def service_info(self, allhall):
        """Trench centre lines hub -> every mod wing's port manifold (see services.apply)."""
        hub = (0, 0)
        paths, vertical, done = [], [], set()
        for r in self.svc:
            ty = r["ty"]
            if ty == 0:
                cells = services.route(self.net or set(), r["door_cell"], r["door"], r["manifold"], hub)
            else:
                tr = next(t for t in self.svc_tiers if t["ty"] == ty)
                zs, X = tr["zsk"], 7
                if ty not in done:
                    done.add(ty)
                    g = services.straight(hub, (0, tr["ground_z"])) + services.straight((0, tr["ground_z"]), (X, tr["ground_z"]))[1:]                         + services.straight((X, tr["ground_z"]), (X, zs + 1))[1:]
                    paths.append({"name": f"riser{ty}", "ty": 0, "cells": g, "risers": []})
                    vertical.append({"ty": ty, "x": X, "z": zs + 1})
                dc = r["door_cell"]
                via = services.straight((X, zs), (dc[0], zs)) + services.straight((dc[0], zs), dc)[1:]
                cells = services.route(None, dc, r["door"], r["manifold"], hub, via=via)
            paths.append({"name": r["name"], "ty": ty, "cells": cells, "risers": r["risers"]})
        halls = {ty: set(m) - self.blocked for ty, m in self.levels.items()}
        hubc = {(x - 16, z - 16) for x, z in massing.fp_octagon(33, 33, 6)}
        hubc = {c for c in hubc if max(abs(c[0]), abs(c[1])) > 3 and max(abs(c[0]), abs(c[1])) < 14}  # grates in the hub floor, centre free
        halls.setdefault(0, set()).update(hubc)
        return {"kit": self.kit, "K": self.K, "hub": hub, "paths": paths, "buildings": set(self.blocked) - hubc, "halls": halls,
                "vertical": vertical}

    def finish(self, extra_cells=None):
        """Halls, platform, gardens and per-wing style features, then shift to a (0,0) min corner."""
        K, kit = self.K, self.kit
        style = HALL_STYLE.get(kit, "glass")
        halls = []
        allhall = set()
        for ty, mask in self.levels.items():
            mask = mask - self.blocked
            allhall |= mask
            halls += _hall(mask, ty, self.blocked, K, kit, style, self.gaps.get(ty, ()))
        self.add("halls", 0, 0, 0, halls, {"kind": "halls"})
        used = self.occupied | allhall | (extra_cells or set())
        # per-wing style features
        feat = []
        y = STEPS
        for f in self.foot:
            x0, z0, w_, d_, H, door, ty = f["x"], f["z"], f["w"], f["d"], f["H"], f["door"], f["ty"]
            sides = tuple(s for s in "nsew" if s != door)
            if kit in ("steampunk", "rust_industrial"):
                zc = z0 + 1 if door == "s" else z0 + d_ - 3
                for xc in (x0 + 2, x0 + w_ - 4):
                    _chimney(feat, xc, zc, y + ty + H - 2, 6 + (f["i"] + xc) % 4, K)
                if kit == "steampunk":
                    _pipes(feat, x0, z0, w_, d_, H, y + ty, sides, K, f["i"])
                    if f["roof"] in ("flat", "mansard"):
                        _roofworks(K, self.seed, self.ghosts, x0, z0, f["i"], feat)
                    else:
                        _slopeworks(K, self.seed, self.ghosts, x0, z0, f["i"], feat)
            elif kit == "gothic":
                _gothic_porch(self, f)
                _gothic_roof(self.ghosts, x0, z0, feat)
                _gothic_variety(feat, x0, z0, w_, d_, H, y + ty, dict(K, wall=WING_ROLES[kit]["wall"], trim=WING_ROLES[kit]["trim"]), sides, f["i"])
            elif kit in ("hextech", "station_white"):
                _wing_massing(feat, x0, z0, w_, d_, H, y + ty, K, sides, f["i"], kit)
            elif kit == "solarpunk":
                _greenwall(feat, x0, z0, w_, d_, H, y + ty, sides, self.seed + f["i"])
                if f["roof"] == "flat":
                    _solar_deck(K, self.seed, self.ghosts, x0, z0, f["i"], feat)
        if kit == "gothic":
            _gothic_crowns(self.ghosts, feat)
        if kit == "station_white":
            _radar(self)
        elif kit == "solarpunk":
            _roof_terraces(self, allhall)
        feat = [b for b in feat if (b[0], b[2]) not in allhall and (b[0], b[1], b[2]) not in self.porch_cells]
        feat += [b for b in self.bays if (b[0], b[1], b[2]) not in self.porch_cells]
        if feat:
            self.add("features", 0, 0, 0, feat, {"kind": "features"})
        return used, allhall


def finish_site(S, garth=None, draw_garth=None, tiers=None, X=0, extra_used=None):
    """Halls, features, platform (or terrace tiers), gardens; shift so the site's min corner is (0, 0).
    garth is the (x, z, w, d) cloister court kept free of yards; draw_garth(out, x, z, w, d, y, K, seed, wood, kit) fills it."""
    K, kit = S.K, S.kit
    used, allhall = S.finish()
    used = used | (extra_used or set())
    pave = S.occupied | allhall
    wood = _wood(K, kit)
    grounds = S.grounds
    platform, tier_blocks = [], []
    if tiers:
        regions = [(ty, zlo, zhi, -X, X) for ty, zlo, zhi in tiers]
        top_ty = max(t[0] for t in tiers)
    else:
        cells = pave | (extra_used or set())
        if garth:
            cells |= _cells(*garth)
        regions = [(0, min(z for x, z in cells) - 2, max(z for x, z in cells) + 2,
                    min(x for x, z in cells) - 2, max(x for x, z in cells) + 2)]
        top_ty = 0
    pathcells = {}
    for ty, zlo, zhi, x0, x1 in regions:
        pathcells[ty] = _plan_yards(grounds, x0, x1, zlo, zhi, STEPS + ty, used | (_cells(*garth) if garth else set()),
                                    K, kit, wood, (S.seed + ty * 5))
    pathblk = K["wall2"]
    for ty, zlo, zhi, x0, x1 in regions:
        yg = STEPS - 1 + ty
        for x in range(x0, x1 + 1):
            for z in range(zlo, zhi + 1):
                top = K["base"] if (x, z) in pave else (pathblk if (x, z) in pathcells[ty] else "minecraft:grass_block")
                (platform if ty == 0 else tier_blocks).append([x, yg, z, top])
                if ty and (z == zhi or abs(x) == X or (ty == top_ty and z == zlo)):
                    for yy in range(STEPS, yg):  # retaining wall, leaf pockets in the top two courses
                        leaf = z == zhi and yy >= yg - 2 and x % 3 == 0
                        tier_blocks.append([x, yy, z, LEAFWALL if leaf else (K["wall2"] if yy % 3 == 0 else K["base"])])
    if garth and draw_garth:
        draw_garth(grounds, garth[0], garth[1], garth[2], garth[3], STEPS, K, S.seed, wood, kit)
    S.add("grounds", 0, 0, 0, grounds, {"kind": "grounds"})
    if tier_blocks:
        S.add("tiers", 0, 0, 0, tier_blocks, {"kind": "tiers"})
    if S.extra:
        S.add("stairs", 0, 0, 0, S.extra, {"kind": "stairs"})
    ghosts = [{"id": "platform", "origin": [0, 0, 0], "blocks": platform, "meta": {"kind": "platform"}}] + S.ghosts
    xmin = min(r[3] for r in regions)
    zmin = min(r[1] for r in regions)
    meta = None
    if S.svc:  # v28: service trench from the hub under every mod wing
        meta = services.apply(S.service_info(allhall), ghosts)
        if meta:
            meta["wings"] = [{"name": r["name"], "theme": r["theme"], "door": r["door"], "ty": r["ty"], "centre": list(r["centre"]),
                              "bays": [[a, b, l] for a, b, l in r["bays"]], "manifold": [list(m) for m in sorted(r["manifold"])]}
                             for r in S.svc]
    for g in ghosts:
        g["origin"][0] -= xmin
        g["origin"][2] -= zmin
    if meta:
        sh = lambda c: [c[0] - xmin, c[1] - zmin]
        meta["hub"] = sh(meta["hub"])
        for p in meta["paths"]:
            p["cells"] = [sh(c) for c in p["cells"]]
        meta["junctions"] = [[sh(c), t, n] for c, t, n in meta["junctions"]]
        for w in meta["wings"]:
            w["centre"] = sh(w["centre"])
            w["bays"] = [sh(b) + [b[2]] for b in w["bays"]]
            w["manifold"] = [sh(m) for m in w["manifold"]]
    return [g for g in ghosts if g["blocks"]]
