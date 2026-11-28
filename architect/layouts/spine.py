"""Spine layout: a covered gallery axis with wings on both sides, a hub in the middle and the tower north of it."""
from __future__ import annotations

import massing
import services

from .common import (GAP, GD, HUB, ROOF_MATS, STEPS, _dims, _lamp, _roof_for, _rooms_door_first, _tree, _windows,
                     _wing_mod, _wood)
from .facades import (_buttresses, _chimney, _gear, _greenwall, _pipes, _ring, _wing_bays)
from .features import _roofworks, _slopeworks
from .landmarks import _tower
from .yards import _yards

def build(kit="hextech", wings=None, home=True, landmark="tower", roles=None, seed=1):
    """The spine campus (the enclosed-gallery plan): returns the ghost list."""
    K = massing._kit(kit, roles)
    K_style = kit if isinstance(kit, str) else ""
    wings = list(wings or [])
    if home:
        wings.insert(0, {"name": "home", "rooms": ["living", "living", "workshop", "storage"], "size": "m",
                         "floor_h": 6})
    if not wings:
        wings = [{"name": "machines", "rooms": ["mod_room", "expansion"]}]
    sizes = [_dims(w) for w in wings]
    ww = max(s[0] for s in sizes)
    pitch = ww + GAP
    # slots: east-north, east-south, west-north, west-south, then the next ring out
    slots = []
    for i in range(len(wings)):
        k, r = divmod(i, 4)
        slots.append(("e" if r < 2 else "w", "n" if r % 2 == 0 else "s", k))
    ke = max([k for s, _, k in slots if s == "e"], default=-1) + 1
    kw = max([k for s, _, k in slots if s == "w"], default=-1) + 1
    depth_n = max([sizes[i][1] for i, s in enumerate(slots) if s[1] == "n"], default=0)
    depth_s = max([sizes[i][1] for i, s in enumerate(slots) if s[1] == "s"], default=0)
    margin = 8
    # site frame: x from 0, gallery z band in the middle
    west = margin + kw * pitch
    hx0 = west + (GAP if kw else 0)  # hub min x
    hx1 = hx0 + HUB
    east = hx1 + (GAP if ke else 0) + ke * pitch
    tower_d = 16 if landmark == "tower" else 0
    gz = margin + max(depth_n, HUB // 2 - GD // 2 + tower_d)  # gallery min z
    hz0 = gz + GD // 2 - HUB // 2
    W = east + margin
    D = gz + GD + max(depth_s, HUB // 2 - GD // 2 + 12) + margin
    y = STEPS  # building level
    ghosts = []

    def add(gid, origin, blocks):
        ghosts.append({"id": gid, "origin": origin, "blocks": blocks})

    add("platform", [0, 0, 0], massing.platform("rect", w=W, d=D, kit=kit, roles=roles, steps=STEPS, rail=True))

    # wings, and the gallery doors that face them
    gdoors = {"w": [], "e": []}  # (side n|s, x in site coords)
    grounds = []
    foot = []  # wing footprints: (x0, z0, w, d, height, side, roof)
    bays_legacy = []
    svc_l = []
    for i, (wing, (side_ew, side_ns, k)) in enumerate(zip(wings, slots)):
        w_, d_ = sizes[i]
        x0 = hx1 + GAP + k * pitch if side_ew == "e" else hx0 - GAP - ww - k * pitch
        x0 += (ww - w_) // 2
        if side_ns == "n":
            z0 = gz - d_ + 1  # outer rings shared with the gallery
        else:
            z0 = gz + GD - 1
        rooms = wing.get("rooms") or ["mod_room", "expansion"]
        door_l = "s" if side_ns == "n" else "n"
        th_l = _wing_mod(wing)
        if th_l:
            rooms = _rooms_door_first(rooms, door_l, w_, d_)
        fh = int(wing.get("floor_h") or (9 + 2 * ((i + seed) % 3)))  # 9 / 11 / 13: varied skyline
        floors = int(wing.get("floors") or 1)
        hs = [fh] + [6] * (floors - 1)
        prog = [rooms] + [wing.get("upper") or ["expansion"]] * (floors - 1)
        roof = _roof_for(wing, K_style, i)
        wing_roles = dict(roles or {})
        wing_roles.update(wing.get("roles") or {})
        wing_roles.setdefault("glass", "minecraft:" + ("cyan", "light_blue", "gray")[i % 3] + "_stained_glass")
        wing_roles.setdefault("wall2", (K["wall2"], K["base"], K["wall"])[i % 3])
        _mats = ROOF_MATS.get(K_style)
        if _mats and "roof" not in (wing.get("roles") or {}):  # v16: a model-wide roles.roof must not flatten every wing to one hue
            wing_roles["roof"] = _mats[i % len(_mats)]
        services.reset()
        blocks = massing.structure("rect", w=w_, d=d_, floor_hs=hs, program=prog, kit=kit, roles=wing_roles,
                                   entrances=["s" if side_ns == "n" else "n"], roof=roof, bay=4+i%3, windows=wing.get("windows") or _windows(K_style, i),
                                   accent_floor=0, seed=seed + i, core="auto", rhythm=1 + i % 3, finial=1)
        add("wing_" + str(wing.get("name", i)), [x0, y, z0], blocks)
        rec_l = services.take()
        if th_l and rec_l["manifold"]:
            svc_l.append({"name": str(wing.get("name", i)), "theme": th_l, "door": door_l, "ty": 0, "i": i,
                          "door_cell": (x0 + w_ // 2, z0 + d_) if door_l == "s" else (x0 + w_ // 2, z0 - 1),
                          "centre": (x0 + w_ // 2, z0 + d_ // 2), "w": w_, "d": d_,
                          "manifold": {(x0 + a, z0 + b) for a, b in rec_l["manifold"]},
                          "risers": [(x0 + a, z0 + b) for a, b in rec_l["risers"]],
                          "bays": [(x0 + a, z0 + b, l) for (a, b), l in rec_l["bays"]]})
        bays_legacy += _wing_bays(x0, z0, w_, d_, y, hs[0], sum(hs) + 1, "s" if side_ns == "n" else "n", K, kit, seed + i, i)
        _th = _wing_mod(wing)  # v26: the spine layout (default for steampunk) never went through Site.wing: sign it here too
        if _th:
            import mods.signs as _signs
            bays_legacy += _signs.facade(_th, x0, z0, w_, d_, y, sum(hs) + 1, "s" if side_ns == "n" else "n")
        foot.append((x0, z0, w_, d_, sum(hs) + 1, side_ns, roof or massing.ROOF_DEFAULT.get(K_style, "flat")))
        gdoors[side_ew].append((side_ns, x0 + w_ // 2))
        # courtyard trees and lamps beside the wing, on the far end from the gallery
        zt = z0 + 4 if side_ns == "n" else z0 + d_ - 5
        for xt in (x0 - GAP // 2 - 1, x0 + w_ + GAP // 2):
            _tree(grounds, xt, zt, y, _wood(K, kit), seed + i, K_style)
            _lamp(grounds, xt, zt + (6 if side_ns == "n" else -6), y, K)

    # gallery: west and east halves, each sharing an outer ring with the hub
    for half, x0, x1 in (("w", margin, hx0), ("e", hx1 - 1, W - margin)):
        if x1 - x0 < 8:
            continue
        ents = ["e" if half == "w" else "w", half]  # into the hub, and the outside end
        ents += [f"{s}@{x - x0}" for s, x in gdoors[half]]
        blocks = massing.structure("rect", w=x1 - x0 + 1, d=GD, floor_hs=[7], program=["hall"], kit=kit,
                                   roles=roles, entrances=ents, roof="flat", windows="band", accent_floor=0,
                                   roof_details=0, antennas=0, seed=seed + 50)
        add("gallery_" + half, [x0, y, gz], blocks)

    # hub: the big showcase hall (for the AE2 controller / quantum computer) under a dome
    hub = massing.structure("octagon", w=HUB, d=HUB, c=9, floor_hs=[12], program=["hall"], kit=kit, roles=roles,
                            entrances=["e", "w", "s"] + (["n"] if landmark == "tower" else []), roof="dome",
                            windows="grid", accent_floor=0, seed=seed + 60)
    add("hub", [hx0, y, hz0], hub)

    # landmark: the one tall volume, north of the hub, a lift inside
    tcx, tcz, r = hx0 + HUB // 2, hz0 - 5, 7
    if landmark == "tower":
        for gid, org, bl in _tower(K, kit, roles, seed, tcx, tcz, y):
            add(gid, org, bl)
    elif landmark == "spire":
        add("spire", [hx0 + HUB // 2 - 4, y, hz0 - 10], massing.spire(h=45, base=9, kit=kit, roles=roles))

    # front plaza south of the hub: lamp avenue and two trees
    cx = hx0 + HUB // 2
    pz0 = hz0 + HUB
    for j in range(0, D - margin - pz0, 5):
        for sx in (-5, 5):
            _lamp(grounds, cx + sx, pz0 + 2 + j, y, K)
    for sx in (-10, 10):
        _tree(grounds, cx + sx, pz0 + 5, y, _wood(K, kit), seed, K_style)
    # yards on the free platform: buildings + clearance, the gallery, hub, tower, front avenue, grounds are taken
    occ = set()

    def take(x0, z0, w, d, pad=2):
        occ.update((x, z) for x in range(x0 - pad, x0 + w + pad) for z in range(z0 - pad, z0 + d + pad))
    for (x0, z0, w_, d_, *_rest) in foot:
        take(x0, z0, w_, d_, 4 if K_style in ("gothic", "solarpunk") else 2)
    take(margin, gz, W - 2 * margin, GD)
    take(hx0, hz0, HUB, HUB)
    if landmark != "none":
        take(tcx - r, tcz - r, 2 * r + 1, 2 * r + 1)
    take(cx - 7, pz0, 15, D - pz0)
    occ.update((b[0] + dx, b[2] + dz) for b in grounds for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    yards = []
    _yards(yards, occ, W, D, y, K, kit, _wood(K, kit), seed)
    add("grounds", [0, 0, 0], grounds + yards)

    # signature features per style
    feat = []
    solid = None
    if K_style in ("steampunk", "rust_industrial"):
        for i, (x0, z0, w_, d_, H, side, roof) in enumerate(foot):
            zc = z0 + 1 if side == "n" else z0 + d_ - 3  # far wall, away from the gallery
            for xc in (x0 + 2, x0 + w_ - 4):
                _chimney(feat, xc, zc, y + H - 2, 6 + (i + xc) % 4, K)
            if K_style == "steampunk":  # copper pipe runs on the three wall faces that are not the door face
                if solid is None:
                    solid = {(b[0] + g["origin"][0], b[1] + g["origin"][1], b[2] + g["origin"][2])
                             for g in ghosts for b in g["blocks"]}
                pl = []
                _pipes(pl, x0, z0, w_, d_, H, y, ("n", "e", "w") if side == "n" else ("s", "e", "w"), K, i)
                feat += [b for b in pl if (b[0], b[1], b[2]) not in solid]
                if roof in ("flat", "mansard"):
                    _roofworks(K, seed, ghosts, x0, z0, i, feat)
                else:
                    _slopeworks(K, seed, ghosts, x0, z0, i, feat)
        _gear(feat, hx0 + HUB // 2, y + 17, hz0 + HUB - 3, 5, K)  # big gear over the hub's front door
        for zz in (gz + 1, gz + GD - 2):  # pipe runs along the gallery roofs
            for x in range(margin + 1, W - margin - 1):
                if not hx0 <= x < hx0 + HUB:
                    feat.append([x, y + 10, zz, "minecraft:lightning_rod[facing=east]"])
    elif K_style == "gothic":
        for (x0, z0, w_, d_, H, side, roof) in foot:
            _buttresses(feat, x0, z0, w_, d_, H, y, K, ("n" if side == "n" else "s", "e", "w"))
    elif K_style == "solarpunk":
        for i, (x0, z0, w_, d_, H, side, roof) in enumerate(foot):
            _greenwall(feat, x0, z0, w_, d_, H, y, ("n" if side == "n" else "s", "e", "w"), seed + i)
            if roof == "flat":  # roof garden: trees on the deck
                for (a, b) in ((4, 4), (w_ - 5, d_ - 5), (w_ // 2, d_ // 2)):
                    _tree(feat, x0 + a, z0 + b, y + H + 1, _wood(K, kit), i + a, K_style)
    elif K_style in ("station_white", "cyber_dark", "ae_sky"):
        skip = {(x, z) for x in range(tcx - r - 1, tcx + r + 2) for z in range(tcz - r - 1, tcz + r + 2)}
        _ring(feat, hx0 + HUB // 2, hz0 + HUB // 2, HUB // 2 + 5, y + 18, K, skip)
    feat += bays_legacy
    if feat:
        add("features", [0, 0, 0], feat)
    # Keep paving only under buildings, yards and the entrance avenue.
    for b in ghosts[0]["blocks"]:
        if b[1] == STEPS - 1 and (b[0], b[2]) not in occ:
            b[3] = "minecraft:grass_block"
    if svc_l:  # v28: trench along the gallery centre line, branching under every mod wing's door to its port wall
        hub_c = (hx0 + HUB // 2, hz0 + HUB // 2)
        gal = set()
        for half, gx0, gx1 in (("w", margin, hx0), ("e", hx1 - 1, W - margin)):
            gal |= {(x, z) for x in range(gx0 + 1, gx1) for z in range(gz + 1, gz + GD - 1)}
        gal -= {(x, z) for x in range(hx0, hx0 + HUB) for z in range(hz0, hz0 + HUB)}
        gal |= {(x, z) for x in range(hx0 + 3, hx0 + HUB - 3) for z in range(hz0 + 3, hz0 + HUB - 3)
                if 4 < max(abs(x - hx0 - HUB // 2), abs(z - hz0 - HUB // 2)) < 14}
        bld = {(x, z) for (x0_, z0_, w_, d_, *_r) in foot for x in range(x0_, x0_ + w_) for z in range(z0_, z0_ + d_)}
        bld |= {(x, z) for x in range(hx0, hx0 + HUB) for z in range(hz0, hz0 + HUB)}
        paths = []
        for r in svc_l:
            dc = r["door_cell"]
            via = services.straight(hub_c, (dc[0], hub_c[1])) + services.straight((dc[0], hub_c[1]), dc)[1:]
            paths.append({"name": r["name"], "ty": 0, "cells": services.route(None, dc, r["door"], r["manifold"], hub_c, via=via),
                          "risers": r["risers"]})
        meta = services.apply({"kit": kit, "K": K, "hub": hub_c, "paths": paths, "buildings": bld - gal,
                               "halls": {}, "galleries": {0: gal}}, ghosts)
        if meta:
            meta["wings"] = [{"name": r["name"], "theme": r["theme"], "door": r["door"], "ty": 0, "centre": list(r["centre"]),
                              "bays": [list(b) for b in r["bays"]], "manifold": [list(m) for m in sorted(r["manifold"])]}
                             for r in svc_l]
    return ghosts
