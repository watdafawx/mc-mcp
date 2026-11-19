"""Service infrastructure for campus mod wings (v28): where cables, power, pipes and AE2 interfaces go.

Four parts, all cheap survival blocks by default (AE2 interface / pattern provider / energy acceptor are the exception: they
draw in a ghost and say "ME" at a glance, see README "Service infrastructure"):

  1. size_for(clusters): wing footprint from the machine-cluster count (cluster pitch x clusters + services), not a fixed size.
  2. trench: a 3-wide, 2-deep channel (three coloured lanes: ME purple, power red, fluid teal) from the hub under every mod wing,
     grate / glass hatches in the paving so it can be seen, a junction block where each wing branches off.
  3. ceiling trays (interiors -> install): dark gantry frames with three coloured conduit runs over the room, feed lines
     dropping onto the machine clusters.
  4. port wall (interiors -> install): the wall of the room facing the hub, labelled bays (M = ME interface / pattern provider,
     P = power input, F = fluid in/out, I = item in/out), fed from the trench through floor risers.

Interiors work in wing-local cells; install() records the risers and the manifold line (take() hands them to campus, which
converts them to world cells and routes the trench to them).
"""
from __future__ import annotations

import math
from collections import deque

TOP = 1                      # paving top y at tier 0 (campus.STEPS - 1)
PITCH = 10                   # floor cells one machine cluster needs (7x7 plinth + aisle)
DEFAULT_CLUSTERS = 14
DARK = "minecraft:polished_blackstone_bricks"
LANES = (  # (key, lane floor, conduit block, colour word)
    ("me", "minecraft:purple_concrete", "minecraft:purple_stained_glass", "purple"),
    ("power", "minecraft:red_concrete", "minecraft:waxed_copper_block", "red"),
    ("fluid", "minecraft:light_blue_concrete", "minecraft:waxed_oxidized_copper", "light_blue"),
)
JUNCTION = ("ae2:interface", "ae2:energy_acceptor", "minecraft:light_blue_glazed_terracotta")
HATCH = {"steampunk": "minecraft:waxed_oxidized_copper_grate", "rust_industrial": "minecraft:waxed_oxidized_copper_grate",
         "hextech": "minecraft:waxed_exposed_copper_grate", "gothic": "minecraft:copper_grate",
         "station_white": "minecraft:waxed_weathered_copper_grate", "solarpunk": "minecraft:waxed_weathered_copper_grate"}
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
INWARD = {"n": (0, 1), "s": (0, -1), "w": (1, 0), "e": (-1, 0)}

# ----------------------------------------------------------------------------------------------------- sizing


def machine_count(wing: dict, theme: str | None = None) -> int:
    """Machine clusters a mod wing has to hold: wing['machines'] if given, else the default."""
    try:
        n = int(wing.get("machines") or 0)
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else DEFAULT_CLUSTERS


def size_for(clusters: int) -> tuple[int, int]:
    """(w, d) of a mod wing for `clusters` machine clusters. Area = clusters x PITCH^2 + services (port strip 6 deep over the
    width, 3-wide spine, walls); aspect ~1:1.3, odd sizes, clamped 27..65 x 33..81. Area is monotonic in clusters."""
    c = max(1, int(clusters))
    area = c * PITCH * PITCH + 520 + 14 * c
    w = min(65, max(27, int(math.sqrt(area / 1.3)))) | 1
    d = min(81, max(33, math.ceil(area / w))) | 1
    return w, max(d, w + 2)


# ------------------------------------------------------------------------- interiors side (wing-local cells)
_REC = {"risers": [], "manifold": [], "bays": [], "port": None}


def reset():
    _REC.update(risers=[], manifold=[], bays=[], port=None)


def take() -> dict:
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in _REC.items()}
    reset()
    return out


def _frame(door: str):
    """(nvec, tvec) for a port wall at the `door` side: nvec points from the wall into the room, tvec is the viewer's right."""
    nx, nz = INWARD[door]
    return (nx, nz), (nz, -nx)


def _uv(p, nv, tv):
    return p[0] * nv[0] + p[1] * nv[1], p[0] * tv[0] + p[1] * tv[1]


def _xz(u, v, nv, tv):
    return u * nv[0] + v * tv[0], u * nv[1] + v * tv[1]


def port_zone(cells: set, door: str, depth: int = 5) -> set:
    """Cells within `depth` rows of the room's port wall: kept free of machine plinths so the bays and an aisle fit."""
    nv, tv = _frame(door)
    u0 = min(_uv(p, nv, tv)[0] for p in cells)
    return {p for p in cells if _uv(p, nv, tv)[0] < u0 + depth}


GLYPH = {"M": ("X.X", "XXX", "XXX", "X.X", "X.X"), "P": ("XXX", "X.X", "XXX", "X..", "X.."),
         "F": ("XXX", "X..", "XX.", "X..", "X.."), "I": ("XXX", ".X.", ".X.", ".X.", "XXX")}
# bay kinds, cycled along the wall: letter, lane, wall blocks (centre, side), upper block
BAYS = (
    ("M", "purple", ("ae2:interface", "ae2:pattern_provider[push_direction=all]"), "ae2:interface"),
    ("P", "red", ("ae2:energy_acceptor", "minecraft:redstone_block"), "minecraft:waxed_copper_block"),
    ("F", "light_blue", ("minecraft:light_blue_stained_glass", "minecraft:waxed_oxidized_copper"), "minecraft:light_blue_stained_glass"),
    ("I", "orange", ("minecraft:barrel[facing={f}]", "minecraft:hopper"), "minecraft:orange_concrete"),
)
TRAY = (("power", "minecraft:red_concrete"), ("item", "minecraft:purple_concrete"),   # same colours as the trench lanes
        ("fluid", "minecraft:light_blue_concrete"))
FACING = {(0, 1): "south", (0, -1): "north", (1, 0): "east", (-1, 0): "west"}


def _conduit(kind, axis, theme):
    """Conduit block for a tray run: real Powah power cables / Create fluid pipes when that mod's room is the wing (they draw
    connected with explicit states), else the coloured glass tube."""
    base = dict(TRAY)[kind]
    if theme == "powah" and kind == "power":
        a = {"x": ("east", "west"), "z": ("north", "south"), "y": ("up", "down")}[axis]
        return f"powah:energy_cable_basic[{a[0]}=true,{a[1]}=true]"
    if theme == "create" and kind == "fluid":
        a = {"x": ("east", "west"), "z": ("north", "south"), "y": ("up", "down")}[axis]
        st = ",".join(f"{d}={'true' if d in a else 'false'}" for d in ("down", "up", "north", "south", "east", "west"))
        return f"create:fluid_pipe[{st}]"
    return base


def install(theme, cells, keep, fy, h, K, put, door, pads, seed=0):
    """Port wall + ceiling trays for one registered mod room. cells: room floor cells (local), keep: aisle/doorway cells,
    pads: machine cluster centres, door: side of the wing facing the hub (n/s/e/w). Needs h >= 9 (one tall floor)."""
    if door not in INWARD or h < 9 or len(cells) < 60:
        return
    nv, tv = _frame(door)
    uvs = {p: _uv(p, nv, tv) for p in cells}
    u0 = min(u for u, _ in uvs.values())
    umax = max(u for u, _ in uvs.values())
    row = {v: p for p, (u, v) in uvs.items() if u == u0}
    if len(row) < 8:
        return
    vs = sorted(row)
    cu = lambda u, v: _xz(u, v, nv, tv)
    face = FACING[(-nv[0], -nv[1])]                      # blocks on the port wall face into the room
    # ---- bays: 5 wide on a pitch of 6, along the wall, skipping the doorway and anything not entirely in the room
    bays, k = [], 0
    v = vs[0] + 3
    while v + 3 <= vs[-1]:
        span = [(u0 + du, v + dv) for du in (0, 1, 2) for dv in (-2, -1, 0, 1, 2)]
        pts = [cu(a, b) for a, b in span]
        if all(p in cells for p in pts) and not any(cu(a, b) in keep for a, b in span if a <= u0 + 1):
            bays.append((v, BAYS[k % len(BAYS)]))
            k += 1
            v += 6
        else:
            v += 1
    fy_ = fy
    for v, (letter, col, (blk, side), upper) in bays:
        concrete = f"minecraft:{col}_concrete"
        for dv in (-2, -1, 0, 1, 2):                       # lit floor strip + the riser grate in front of the bay
            x, z = cu(u0 + 1, v + dv)
            put(x, fy_, z, concrete)
        rx, rz = cu(u0 + 1, v)
        put(rx, fy_, rz, "minecraft:waxed_oxidized_copper_grate")
        _REC["risers"].append((rx, rz))
        for dv in (-2, -1, 0, 1, 2):
            for dy in (1, 2):                                # machines on the wall: side pieces and the centre block
                x, z = cu(u0, v + dv)
                b = blk if dv == 0 or (abs(dv) == 1 and dy == 2) else side
                put(x, fy_ + dy, z, b.replace("{f}", face))
        for dv in (-2, -1, 0, 1, 2):                         # coloured panel + white letter
            for dy in range(3, 10):
                x, z = cu(u0, v + dv)
                put(x, fy_ + dy, z, concrete)
        g = GLYPH[letter]
        for r, line in enumerate(g):
            for c, ch in enumerate(line):
                if ch == "X":
                    x, z = cu(u0, v + c - 1)
                    put(x, fy_ + 8 - r, z, "minecraft:white_concrete")
        for dv in (-3, 3):                                    # pilaster between bays
            x, z = cu(u0, v + dv)
            for dy in range(1, 10):
                put(x, fy_ + dy, z, DARK)
        x, z = cu(u0 + 1, v)                                  # conduit stub from the header down to the bay lamp
        for dy in range(10, h):                               # feed stub: header down to the top of the panel
            put(x, fy_ + dy, z, concrete)
    # ---- header beam along the wall under the ceiling, the three tray runs from the header to the far wall, cross beams
    if not bays:
        return
    yt = fy_ + h - 1
    for dv in vs:
        x, z = row[dv]
        put(x, fy_ + h, z, DARK)
    vc = bays[len(bays) // 2][0]
    axis = "x" if nv[0] else "z"
    for u in range(u0 + 1, umax + 1):
        for dv, (kind, _) in zip((-1, 0, 1), TRAY):
            p = cu(u, vc + dv)
            if p in cells:
                put(p[0], yt, p[1], _conduit(kind, axis, theme))
        if (u - u0) % 6 == 3:                                # gantry cross beam, hung from the ceiling, wall to wall
            for p, (uu, vv) in uvs.items():
                if uu == u:
                    put(p[0], fy_ + h, p[1], DARK)
            for dv in (-2, 2):
                p = cu(u, vc + dv)
                if p in cells:
                    put(p[0], yt, p[1], "minecraft:chain[axis=y]")
    # ---- feed lines: from the tray along the cross direction to each cluster, then a drop onto the machines
    drops = 0
    for c in pads:
        u, vv = _uv(c, nv, tv)
        if abs(vv - vc) < 2 or u <= u0 + 4:
            continue
        step = 1 if vv > vc else -1
        kind = TRAY[drops % 3]
        for w in range(vc + 2 * step, vv + step, step):
            p = cu(u, w)
            if p in cells:
                put(p[0], yt, p[1], kind[1] if kind[0] != "power" else _conduit("power", "z" if axis == "x" else "x", theme))
        for dy in range(fy_ + 8, yt):
            put(c[0], dy, c[1], kind[1])
        put(c[0], fy_ + 7, c[1], "minecraft:lightning_rod[facing=down]")
        drops += 1
    # ---- manifold line under the bays' riser row (the trench ends here)
    for dv in vs:
        p = cu(u0 + 1, dv)
        if p in cells:
            _REC["manifold"].append(p)
    _REC["bays"] = [(cu(u0, v), letter) for v, (letter, *_r) in bays]
    _REC["port"] = {"u0": u0, "nv": nv, "door": door, "tray_v": vc}


# ------------------------------------------------------------------------------- campus side (world cells)


def _expand(cells, r):
    return {(x + a, z + b) for (x, z) in cells for a in range(-r, r + 1) for b in range(-r, r + 1)}


def bfs(net: set, a, b):
    if a not in net or b not in net:
        return None
    prev, q = {a: None}, deque([a])
    while q:
        c = q.popleft()
        if c == b:
            out = []
            while c is not None:
                out.append(c)
                c = prev[c]
            return out[::-1]
        for dx, dz in N4:
            n = (c[0] + dx, c[1] + dz)
            if n in net and n not in prev:
                prev[n] = c
                q.append(n)
    return None


def straight(a, b):
    """Axis-aligned cells from a to b, x first then z."""
    out, (x, z) = [a], a
    while x != b[0]:
        x += 1 if b[0] > x else -1
        out.append((x, z))
    while z != b[1]:
        z += 1 if b[1] > z else -1
        out.append((x, z))
    return out


def inward(door_cell, door, manifold):
    """From the cell outside a wing door, straight in to the manifold row, then along it to the nearest manifold cell."""
    if not manifold:
        dx, dz = INWARD[door]
        return [(door_cell[0] + dx * k, door_cell[1] + dz * k) for k in range(8)]
    dx, dz = INWARD[door]
    m0 = next(iter(manifold))
    out, c = [door_cell], door_cell
    for _ in range(120):
        if (dx and c[0] == m0[0]) or (dz and c[1] == m0[1]):
            break
        c = (c[0] + dx, c[1] + dz)
        out.append(c)
    tgt = min(manifold, key=lambda m: abs(m[0] - c[0]) + abs(m[1] - c[1]))
    out += straight(c, tgt)[1:]
    return out


def route(net, door_cell, door, manifold, hub=(0, 0), via=None):
    """Ordered trench centre line hub -> wing manifold. net: hall centre-line cells (BFS), or via: explicit cells hub -> door."""
    head = via if via is not None else bfs(net, door_cell, hub)
    if head is None:
        head = straight(door_cell, hub)
    head = head[::-1] if via is None else head
    if head and head[0] != hub and via is None:
        head = straight(hub, head[0]) + head[1:]
    tail = inward(door_cell, door, manifold)
    return head + [c for c in tail if c != head[-1]]


def _dedupe(cells):
    out, seen = [], set()
    for c in cells:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def apply(info: dict, ghosts: list) -> dict | None:
    """Carve the trench into `ghosts` and append a 'services' ghost. info: kit, K, hub, paths [{name, ty, cells, door_cell,
    risers}], buildings (cell set), halls (cell set), galleries (cell set). Returns the services meta (also on the ghost)."""
    paths = [p for p in info.get("paths", []) if p["cells"]]
    if not paths:
        return None
    K, kit = info["K"], info.get("kit", "")
    hatch = HATCH.get(kit, "minecraft:waxed_oxidized_copper_grate")
    glow = K.get("glow", "minecraft:glowstone")
    buildings = info.get("buildings", set())
    want: dict = {}
    carve: set = set()
    junctions = []
    for ty in sorted({p["ty"] for p in paths}):
        y1 = TOP + ty
        halls = info.get("halls", {}).get(ty, set())
        galleries = info.get("galleries", {}).get(ty, set())
        P, order = set(), []
        seen_union = set()
        for p in (q for q in paths if q["ty"] == ty):
            cs = _dedupe(p["cells"])
            order.append((p, cs))
            for i, c in enumerate(cs):                        # junction where this wing leaves the trunk built so far
                if c not in seen_union:
                    j = cs[i - 1] if i else cs[0]
                    if seen_union or i == 0:
                        junctions.append((j, ty, p.get("name")))
                    break
            seen_union |= set(cs)
            P |= set(cs)
        void = _expand(P, 1)
        ring = _expand(P, 2) - void
        axis = {}
        for q in P:
            axis[q] = "x" if ((q[0] + 1, q[1]) in P or (q[0] - 1, q[1]) in P) else "z"
        for v in void:
            near = [q for q in ((v[0] + a, v[1] + b) for a in (-1, 0, 1) for b in (-1, 0, 1)) if q in P]
            q = min(near, key=lambda q: (abs(q[0] - v[0]) + abs(q[1] - v[1]), q))
            lane = (v[1] - q[1] + 1) if axis[q] == "x" else (v[0] - q[0] + 1)
            lane = max(0, min(2, lane))
            _, floor, cond, _c = LANES[lane]
            want[(v[0], y1 - 3, v[1])] = floor
            want[(v[0], y1 - 2, v[1])] = cond
            carve.add((v[0], y1 - 1, v[1]))
            carve.add((v[0], y1 - 2, v[1]))
            a = v[0] if axis[q] == "x" else v[1]
            kind = "gallery" if v in galleries else "hall" if v in halls else "build" if v in buildings else "ground"
            beam = a % 4 == 0
            lid = DARK if beam else hatch
            if kind == "ground":
                want[(v[0], y1, v[1])] = lid
            elif kind in ("hall", "gallery"):
                carve.add((v[0], y1, v[1]))
                want[(v[0], y1 + 1, v[1])] = lid
        for r in ring:
            for dy, blk in ((-3, DARK), (-2, DARK), (-1, DARK)):
                want[(r[0], y1 + dy, r[1])] = blk
            if (r[0] + r[1]) % 6 == 0:
                want[(r[0], y1 - 1, r[1])] = glow
        for (c, t, nm) in junctions:
            if t != ty:
                continue
            ax = axis.get(c, "x")
            for lane in range(3):
                x, z = (c[0], c[1] + lane - 1) if ax == "x" else (c[0] + lane - 1, c[1])
                want[(x, y1 - 2, z)] = JUNCTION[lane]
                want[(x, y1 - 1, z)] = JUNCTION[lane] if lane == 0 else "minecraft:air"
            kind = "gallery" if c in galleries else "hall" if c in halls else "build" if c in buildings else "ground"
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    cc = (c[0] + a, c[1] + b)
                    if kind == "ground":
                        want[(cc[0], y1, cc[1])] = K.get("glass", "minecraft:glass")
                    elif kind in ("hall", "gallery"):
                        carve.add((cc[0], y1, cc[1]))
                        want[(cc[0], y1 + 1, cc[1])] = K.get("glass", "minecraft:glass")
        for vt in (v for v in info.get("vertical", []) if v["ty"] == ty):   # terrace tiers: conduits climb the retaining wall
            for lane in range(3):
                x = vt["x"] - 1 + lane
                for yy in range(TOP - 2, y1 - 1):
                    want[(x, yy, vt["z"])] = LANES[lane][2]
                want[(x, y1 - 2, vt["z"] - 1)] = LANES[lane][2]
        for p, cs in order:                                   # wing risers (port wall bays): open the paving under the grate
            for c in p.get("risers", []):
                carve.add((c[0], y1, c[1]))
                carve.add((c[0], y1 - 1, c[1]))
                carve.add((c[0], y1 - 2, c[1]))
    # remove carved and re-placed positions from every ghost, then add the services ghost
    kill = carve | set(want)
    for g in ghosts:
        ox, oy, oz = g["origin"]
        g["blocks"] = [b for b in g["blocks"] if (b[0] + ox, b[1] + oy, b[2] + oz) not in kill]
    blocks = [[x, y, z, b] for (x, y, z), b in want.items() if b != "minecraft:air"]
    meta = {"kind": "services",
            "paths": [{"name": p.get("name"), "ty": p["ty"], "cells": [list(c) for c in _dedupe(p["cells"])]} for p in paths],
            "junctions": [[list(c), t, n] for c, t, n in junctions], "hub": list(info.get("hub", (0, 0)))}
    ghosts.append({"id": "services", "origin": [0, 0, 0], "blocks": blocks, "meta": meta})
    return meta
