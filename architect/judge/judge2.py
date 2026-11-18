"""Judge sheets v2: python judge2.py id:kit ... -> judge2/<id>_sheet.jpg
Clouds off, render distance 16, only the judged build visible, 8 shots (site iso x2, front, top, hub, tower,
one wing facade, interior cut) at 960x540, plus a row with two of the player's refs for the kit."""
import json, math, sys, time
from pathlib import Path
from PIL import Image, ImageDraw
from judge_call import call
sys.path.insert(0, str(Path(__file__).parent))
import room_pick  # v20: real-room picker
ARCH = Path("X:/Dev/Minecraft/mc-mcp/architect")
sys.path.insert(0, str(ARCH))
GLOW_WORDS = ("luminax", "lantern", "shroomlight", "glowstone", "sea_lantern", "end_rod", "froglight", "campfire", "torch", "copper_bulb", "redstone_lamp", "candle")


def occupancy(gid, sel):
    """Exact block map of a build, rebuilt from its session log: every campus call is replayed through campus.build
    (same kit/wings/origin), ghost_set calls are replayed too. Ghosts that cannot be replayed count as filled bboxes.
    Returns (cells {(x,y,z): block}, covered ghost ids)."""
    cells, done = {}, set()
    f = ARCH / "sessions" / gid / "messages.json"
    if not f.exists():
        return cells, done
    try:
        import campus
        msgs = json.load(open(f, encoding="utf-8"))
        for m in msgs:
            if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
                continue
            for b in m["content"]:
                if b.get("type") != "tool_use":
                    continue
                a = b.get("input") or {}
                if b["name"] == "campus" and str(a.get("area", "")).startswith(gid):
                    ox, oy, oz = a["origin"]
                    for g in campus.build(a["kit"], a.get("wings") or [], bool(a.get("home", True)), a.get("landmark") or "tower",
                                          a.get("roles"), layout=a.get("layout")):
                        gi = f"{a['area']}/{g['id']}"
                        for k in [k for k, v in cells.items() if v[1] == gi]:
                            del cells[k]
                        for x, y, z, blk in g["blocks"]:
                            cells[(ox + g["origin"][0] + x, oy + g["origin"][1] + y, oz + g["origin"][2] + z)] = (blk, gi)
                        done.add(gi)
    except Exception as e:  # noqa: BLE001
        print("occupancy replay failed:", repr(e)[:120])
    return cells, done

REFS = "X:/Dev/Minecraft/mc-mcp/architect/knowledge/style_refs/"
OUT = ARCH / "exports" / "judge2"  # ignored dir; sheets are not committed
OUT.mkdir(parents=True, exist_ok=True)
TW, TH = 960, 540

for c in ("gamemode spectator", "time set noon", "weather clear", "gamerule doDaylightCycle false"):
    call("run_command", {"command": c})
for opt, val in (("cloudStatus", "OFF"), ("renderDistance", 16)):
    print(opt, call("video_set", {"option": opt, "value": val, "save": False})[:80])
ghosts = json.loads(call("ghost_list", {}))["ghosts"]


def bounds(sel):
    lo = [min(g["world_min"][i] for g in sel) for i in range(3)]
    hi = [max(g["world_max"][i] for g in sel) + 1 for i in range(3)]
    return lo, hi


def shot(c, d, ox, oy, oz, label):
    k = math.sqrt(ox * ox + oy * oy + oz * oz)
    call("run_command", {"command": f"tp @s {c[0]+ox/k*d:.1f} {c[1]+oy/k*d:.1f} {c[2]+oz/k*d:.1f}"})
    call("look_at", {"x": c[0], "y": c[1], "z": c[2]})
    time.sleep(2.5)
    p = json.loads(call("screenshot", {}))["path"]
    p = "Q:" + p[2:] if p.upper().startswith("G:") else p
    im = Image.open(p).convert("RGB")
    im.thumbnail((TW, TH))
    ImageDraw.Draw(im).text((8, 6), label, fill=(255, 255, 0))
    return im


def blocked(occ, p, r=1):
    x, y, z = (int(math.floor(v)) for v in p)
    return any((x + a, y + b, z + c) in occ for a in range(-r, r + 1) for b in range(-r, r + 1) for c in range(-r, r + 1))


def clear_ray(occ, eye, tgt, stop=3.0):
    d = [tgt[i] - eye[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in d))
    steps = int(n * 2)
    for k in range(steps):
        t = k / steps
        if n * (1 - t) < stop:
            break
        if (int(math.floor(eye[0] + d[0] * t)), int(math.floor(eye[1] + d[1] * t)), int(math.floor(eye[2] + d[2] * t))) in occ:
            return False
    return True


for arg in sys.argv[1:]:
    gid, _, kit = arg.partition(":")
    sel = [g for g in ghosts if g["id"].startswith(gid + "/") and "world_min" in g]
    _zs = sorted(g["world_min"][2] for g in sel)
    if _zs:  # drop outlier ghosts (stray blocks near world origin from a wrong ghost origin): judged separately
        _med = _zs[len(_zs) // 2]
        _out = [g["id"] for g in sel if abs(g["world_min"][2] - _med) > 600]
        if _out:
            print("OUTLIER ghosts excluded from shots:", _out)
        sel = [g for g in sel if g["id"] not in _out]
    # sky stage: lift the build 130 blocks so terrain, trees and caves never hide it; moved back after
    LIFT = max(130, 330 - min(g["world_min"][1] for g in sel))  # above any mountain peak
    for g in sel:
        call("ghost_move", {"id": g["id"], "offset": [0, LIFT, 0]})
    fresh = {g["id"]: g for g in json.loads(call("ghost_list", {}))["ghosts"]}
    sel = [fresh[g["id"]] for g in sel]
    cells0, done = occupancy(gid, sel)
    occ = {(x, y + LIFT, z): v for (x, y, z), v in cells0.items()}
    for g in sel:  # ghosts we could not replay: filled bbox (conservative), flat ground layers excluded
        if g["id"] not in done and g["id"].split("/", 1)[1] not in ("platform", "grounds", "tiers", "halls", "features", "stairs"):
            for x in range(g["world_min"][0], g["world_max"][0] + 1):
                for y in range(g["world_min"][1], g["world_max"][1] + 1):
                    for z in range(g["world_min"][2], g["world_max"][2] + 1):
                        occ.setdefault((x, y, z), ("bbox", g["id"]))
    print(gid, "occupancy", len(occ), "cells,", len(done), "ghosts replayed")
    # only this build visible, no cutaway, no HUD
    for g in ghosts:
        call("ghost_show", {"id": g["id"], "visible": g["id"] in {x["id"] for x in sel}})
    call("ghost_show", {"id": "*", "clip_off": True, "xray": False, "solid": True, "hud": False})
    # camera bounds ONLY from campus-generated ghosts (replayed ids); no model-written ghost can skew framing.
    csel = [g for g in sel if g["id"] in done]
    if not csel:  # robust fallback: ghosts whose centre is within 200 blocks of the median centre (all axes)
        _ctr = [[(g["world_min"][i] + g["world_max"][i]) / 2 for i in range(3)] for g in sel]
        _med = [sorted(v[i] for v in _ctr)[len(_ctr) // 2] for i in range(3)]
        csel = [g for g, v in zip(sel, _ctr) if all(abs(v[i] - _med[i]) <= 200 for i in range(3))] or sel
    _skew = [g["id"] for g in sel if g not in csel]
    if _skew:
        print("non-campus ghosts excluded from camera bounds:", _skew)
    lo, hi = bounds(csel)
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    span = max(hi[0] - lo[0], hi[2] - lo[2])
    by = {g["id"].split("/", 1)[1]: g for g in csel}
    tiles = [shot(c, span * 0.72, -0.7, 0.5, 0.7, "site iso SW"),
             shot(c, span * 0.72, 0.7, 0.5, -0.7, "site iso NE"),
             shot([c[0], lo[1] + 10, c[2]], span * 0.6, 0, 0.32, 1, "front (south), low"),
             shot([c[0], lo[1], c[2]], span * 0.95, 0.01, 1, 0.01, "top")]
    for key, label, dirn in (("hub", "hub close", (-0.5, 0.35, 1)), ("tower", "tower close", (0.6, 0.25, -1))):
        g = by.get(key)
        if not g:
            continue
        glo, ghi = bounds([g])
        gc = [(glo[i] + ghi[i]) / 2 for i in range(3)]
        gs = max(ghi[i] - glo[i] for i in range(3))
        tiles.append(shot(gc, gs * 1.15 + 6, *dirn, label + f" ({key})"))
    # wing facade: search for an eye position OUTSIDE every ghost block with a clear sight line to the facade
    def _len(k):
        a, b = bounds([by[k]])
        return max(b[0] - a[0], b[2] - a[2])
    def _fill(k):  # fraction of the wing bbox footprint filled at the floor line: curved/ring wings score low
        a, b = bounds([by[k]])
        n = sum(1 for (x, y, z) in occ if a[0] <= x < b[0] and a[2] <= z < b[2] and y == a[1])
        return n / max(1, (b[0] - a[0]) * (b[2] - a[2]))
    wcand = [k for k in by if k.startswith("wing_") and k != "wing_home"]
    wrect = [k for k in wcand if not occ or _fill(k) >= 0.55] or wcand
    wkeys = sorted(wrect, key=_len, reverse=True) +         [k for k in by if k == "wing_home"]
    print("facade candidates", [(k, round(_fill(k), 2), _len(k)) for k in wcand])
    wkey, best, used_fb = None, None, False

    def search(wk, dists, ups, slides):
        wl, wh = bounds([by[wk]])
        wc = [(wl[i] + wh[i]) / 2 for i in range(3)]
        hx, hz = (wh[0] - wl[0]) / 2, (wh[2] - wl[2]) / 2
        pref = [(0, 1 if wc[2] >= c[2] else -1), (0, -1 if wc[2] >= c[2] else 1),
                (1 if wc[0] >= c[0] else -1, 0), (-1 if wc[0] >= c[0] else 1, 0)]
        if hx < hz:
            pref = pref[2:] + pref[:2]
        for dist in dists:
            for up in ups:
                for nx, nz in pref:
                    face = [wc[0] + nx * hx, wl[1] + max(6, (wh[1] - wl[1]) * 0.4), wc[2] + nz * hz]
                    eye = [face[0] + nx * dist, wl[1] + up, face[2] + nz * dist]
                    for slide in slides:
                        e2 = [eye[0] + (slide if nz else 0), eye[1], eye[2] + (slide if nx else 0)]
                        t2 = [face[0] + (slide if nz else 0), face[1], face[2] + (slide if nx else 0)]
                        if occ:
                            lat = (hx if nz else hz) * 0.8
                            side = [[t2[0] + (s_ * lat if nz else 0), t2[1], t2[2] + (s_ * lat if nx else 0)] for s_ in (-1, 0, 1)]
                            if blocked(occ, e2, 4) or not all(clear_ray(occ, e2, t_, 6.0) for t_ in side):
                                continue
                        return (e2, t2, nx, nz, dist, up)
        return None

    for wk in wkeys:
        L = _len(wk)
        ds = tuple(int(min(75, max(28, L * f))) for f in (1.0, 1.25, 0.85, 1.5))
        best = search(wk, ds, (int(ds[0] * 0.3), int(ds[0] * 0.45), int(ds[0] * 0.2)), (0, 3, -3, 6, -6, 10, -10))
        if best:
            wkey = wk
            break
    if not best:  # roof-level fallback: higher and further out, long slides, any wing
        for wk in wkeys:
            best = search(wk, (40, 55, 70), (22, 32, 45), (0, 10, -10, 20, -20, 30, -30, 40, -40))
            if best:
                wkey, used_fb = wk, True
                break
    if wkey is None:
        wkey = wkeys[0] if wkeys else None
    if wkey and not best:  # last resort: oblique 3/4 view from above, never straight down
        wl, wh = bounds([by[wkey]])
        wc = [(wl[i] + wh[i]) / 2 for i in range(3)]
        best = ([wc[0] + 30, hi[1] + 12, wc[2] + 45], [wc[0], wl[1] + 5, wc[2]], 0, 1, 50, 0)
        used_fb = True
    if wkey:
        eye, tgt, nx, nz, dist, up = best
        call("run_command", {"command": f"tp @s {eye[0]:.1f} {eye[1]:.1f} {eye[2]:.1f}"})
        call("look_at", {"x": tgt[0], "y": tgt[1], "z": tgt[2]})
        time.sleep(2.5)
        p = json.loads(call("screenshot", {}))["path"]
        p = "Q:" + p[2:] if p.upper().startswith("G:") else p
        im = Image.open(p).convert("RGB")
        im.thumbnail((TW, TH))
        ImageDraw.Draw(im).text((8, 6), f"wing facade ({wkey}) {dist} out, {up} up" + (" ROOF-LEVEL FALLBACK" if used_fb else "") + ("" if occ else " BBOX ONLY"), fill=(255, 255, 0))
        tiles.append(im)
    # interior cut: per wing find its ceiling (first layer >=55% filled above the floor); pick the wing with most light under a
    # ceiling, clip just under that ceiling and aim at the lit area from a steep angle
    def ceiling_of(wk):
        wl, wh = bounds([by[wk]])
        cells = [(x, y, z, v[0]) for (x, y, z), v in occ.items() if wl[0] <= x < wh[0] and wl[2] <= z < wh[2] and wl[1] <= y < wh[1]]
        if not cells:
            return None
        area = (wh[0] - wl[0]) * (wh[2] - wl[2])
        layers = {}
        for x, y, z, b_ in cells:
            layers[y] = layers.get(y, 0) + 1
        for y in range(wl[1] + 4, int(wh[1])):
            if layers.get(y, 0) >= 0.7 * area:
                lit_ = [(x, yy, z) for x, yy, z, b_ in cells if yy <= y and any(w in b_ for w in GLOW_WORDS)]
                # densest machine area: 8x8 grid cell with the most non-wall blocks inside the room (inset 2, floor+1 .. ceiling-1)
                grid = {}
                for x, yy, z, b_ in cells:
                    if wl[1] + 2 <= yy < y and wl[0] + 2 <= x < wh[0] - 2 and wl[2] + 2 <= z < wh[2] - 2:
                        k = ((x - wl[0]) // 8, (z - wl[2]) // 8)
                        grid[k] = grid.get(k, 0) + 1
                dense = None
                if grid:
                    k = max(grid, key=grid.get)
                    dense = [wl[0] + k[0] * 8 + 4, wl[1] + 2, wl[2] + k[1] * 8 + 4, grid[k]]
                return y, lit_, wl, wh, dense
        return None
    room = room_pick.pick_room({k: v for k, v in occ.items() if v[0] != "bbox"}, GLOW_WORDS) if occ else None
    if room:  # v20: a real built room (ceiling lights over a floor), not the densest-area guess
        call("ghost_show", {"id": "*", "clip_y": room["cut_y"]})
        tiles.append(shot(room["aim"], min(room["span"] * 0.9 + 10, 40), -0.25, 1.35, 0.35,
                          f"interior cut REAL ROOM {room['ghost'].split('/')[-1]} y={room['cut_y']} ({room['lights']} ceiling lights, {room['stuff']} furnishing blocks)"))
        call("ghost_show", {"id": "*", "clip_off": True})
    best_c = None
    for wk in [k for k in by if k.startswith("wing_") and k != "wing_home"] + ["wing_home"]:
        if best_c and best_c[1][1] and wk == "wing_home":
            break
        r_ = ceiling_of(wk)
        if r_ and (best_c is None or len(r_[1]) > len(best_c[1][1])
                   or (len(r_[1]) == len(best_c[1][1]) and len(r_[1]) < 4 and (r_[4] or [0] * 4)[3] > (best_c[1][4] or [0] * 4)[3])):
            best_c = (wk, r_)
    if room:
        pass
    elif best_c:
        wk, (cy, lit, wl, wh, dense) = best_c
        cut_y = cy - 1
        wc = [(wl[i] + wh[i]) / 2 for i in range(3)]
        if len(lit) >= 4:
            aim = [sum(p_[0] for p_ in lit) / len(lit), wl[1] + 2, sum(p_[2] for p_ in lit) / len(lit)]
        elif dense:  # no lit blocks under any ceiling: aim at the densest machine area
            aim = dense[:3]
            lit = [None] * 0
        else:
            aim = [wc[0], wl[1] + 2, wc[2]]
        span_w = max(wh[0] - wl[0], wh[2] - wl[2])
        call("ghost_show", {"id": "*", "clip_y": cut_y})
        tiles.append(shot(aim, min(span_w * 0.75, 45), -0.25, 1.35, 0.35, f"interior cut {wk} y={cut_y} ({len(lit)} lit blocks" + ("" if len(lit) >= 4 else f", DENSEST-AREA FALLBACK {dense[3] if dense else 0} blocks") + ")"))
        call("ghost_show", {"id": "*", "clip_off": True})
    else:
        wg = by.get(wkey) or next(g for k, g in by.items() if k.startswith("wing_"))
        wl, wh = bounds([wg])
        wc = [(wl[i] + wh[i]) / 2 for i in range(3)]
        cut_y = int(wl[1] + 7)
        call("ghost_show", {"id": "*", "clip_y": cut_y})
        tiles.append(shot([wc[0], wl[1] + 2, wc[2]], max(wh[0] - wl[0], wh[2] - wl[2]) * 0.85, -0.25, 1.35, 0.35, f"interior cut y={cut_y} (no ceiling found)"))
        call("ghost_show", {"id": "*", "clip_off": True})
    rows = (len(tiles) + 1) // 2
    sheet = Image.new("RGB", (TW * 2, TH * (rows + 1)), (20, 20, 20))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * TW, (i // 2) * TH))
    if kit:
        idx = json.load(open(REFS + "index.json", encoding="utf-8"))
        for j, r in enumerate([r for r in idx if r["kit"] == kit][:2]):
            im = Image.open(REFS + r["file"]).convert("RGB")
            im.thumbnail((TW, TH))
            sheet.paste(im, (j * TW + (TW - im.width) // 2, rows * TH))
    # ---- detail sheet: close-ups of the procedural features (dock+airship, gear, gothic porch, pipe run) located from the
    # replayed campus cells; each eye is searched OUTSIDE every ghost block with a clear ray, absent features are skipped.
    def fcells(pred):
        return [p_ for p_, v in occ.items() if pred(v[1].split("/", 1)[-1], v[0])]

    def cen(cs):
        return [sum(p_[i] for p_ in cs) / len(cs) for i in range(3)]

    def clusters(cs, gap=2):
        left, out_ = set(cs), []
        while left:
            seed_ = left.pop()
            comp, stack = [seed_], [seed_]
            while stack:
                a_ = stack.pop()
                for dx in range(-gap, gap + 1):
                    for dy in range(-gap, gap + 1):
                        for dz in range(-gap, gap + 1):
                            q = (a_[0] + dx, a_[1] + dy, a_[2] + dz)
                            if q in left:
                                left.discard(q)
                                comp.append(q)
                                stack.append(q)
            out_.append(comp)
        return sorted(out_, key=len, reverse=True)

    def eye_shot(tgt, prefs, dists, ups, label, stop=4.0, extra=None, avoid=None):
        """prefs: horizontal directions, best first; the first eye outside every ghost block with a clear ray wins."""
        occ_real = {k_: v_ for k_, v_ in occ.items() if v_[0] != "bbox"}  # 2nd pass: ignore the conservative model-ghost boxes
        for occ_use, dists_use in ((occ, dists), (occ_real, tuple(dists) + (int(max(dists) * 1.5),))):
          for dist in dists_use:
            for up in ups:
                for nx, nz in prefs:
                    n_ = math.hypot(nx, nz) or 1
                    eye = [tgt[0] + nx / n_ * dist, tgt[1] + up, tgt[2] + nz / n_ * dist]
                    if blocked(occ_use, eye, 3) or not clear_ray(occ_use, eye, tgt, stop):
                        continue
                    if extra and not all(clear_ray(occ_use, eye, e_, 2.5) for e_ in extra):  # v16: low points must be visible too
                        continue
                    if avoid and any(near_seg(a_, eye, tgt, 3.6) for a_ in avoid):  # v17: no tree in the view cone
                        continue
                    call("run_command", {"command": f"tp @s {eye[0]:.1f} {eye[1]:.1f} {eye[2]:.1f}"})
                    call("look_at", {"x": tgt[0], "y": tgt[1], "z": tgt[2]})
                    time.sleep(2.5)
                    p = json.loads(call("screenshot", {}))["path"]
                    p = "Q:" + p[2:] if p.upper().startswith("G:") else p
                    im = Image.open(p).convert("RGB")
                    im.thumbnail((TW, TH))
                    ImageDraw.Draw(im).text((8, 6), f"{label} ({dist:.0f} out, {up:.0f} up)", fill=(255, 255, 0))
                    return im
        if extra:
            return eye_shot(tgt, prefs, dists, ups, label, stop, None, avoid)
        print("detail shot skipped (no clear eye):", label)
        return None

    def near_seg(a_, e_, t_, r_):
        d_ = [t_[i] - e_[i] for i in range(3)]
        L2 = sum(v * v for v in d_) or 1.0
        u_ = max(0.0, min(0.9, sum((a_[i] + 0.5 - e_[i]) * d_[i] for i in range(3)) / L2))
        return sum((a_[i] + 0.5 - e_[i] - u_ * d_[i]) ** 2 for i in range(3)) < r_ * r_

    trees_ = [k_ for k_, v_ in occ.items() if v_[0] != "bbox" and ("leaves" in v_[0] or v_[0].split("[")[0].endswith("_log"))]

    def fan(nx, nz):  # preferred horizontal direction, then +-40, +-80, +-120 and the opposite
        a0 = math.atan2(nz, nx)
        return [(math.cos(a0 + d_ * math.pi / 180), math.sin(a0 + d_ * math.pi / 180)) for d_ in (0, 40, -40, 80, -80, 120, -120, 180)]

    dtiles, notes = [], []
    # dock + airship: two obliques, from the free outer side then from a perpendicular side
    dock = fcells(lambda g_, b_: g_ == "airdock")
    if dock:
        dc = cen(dock)
        ox_, oz_ = dc[0] - c[0], dc[2] - c[2]
        im = eye_shot(dc, fan(ox_, oz_), (60, 75, 90), (30, 45), "hex dock + airship, outer oblique", 14.0)
        if im:
            dtiles.append(im)
        im = eye_shot(dc, fan(-oz_, ox_) + fan(oz_, -ox_), (60, 80), (30, 45), "hex dock + airship, side oblique", 14.0)
        if im:
            dtiles.append(im)
        notes.append("dock: " + str([round(v) for v in dc]))
    else:
        notes.append("dock: ABSENT")
    # steam tower gear: biggest cogwheel, shoot along its wall normal
    gears = fcells(lambda g_, b_: g_ == "tower_gears")
    if gears:
        cl = clusters(gears)[0]
        gc = cen(cl)
        ex = [max(p_[i] for p_ in cl) - min(p_[i] for p_ in cl) for i in range(3)]
        tw = by.get("tower")
        tc = [(bounds([tw])[0][i] + bounds([tw])[1][i]) / 2 for i in range(3)] if tw else c
        nx, nz = (1 if gc[0] >= tc[0] else -1, 0) if ex[0] <= ex[2] else (0, 1 if gc[2] >= tc[2] else -1)
        im = eye_shot(gc, fan(nx, nz), (24, 32, 42), (4, 10), "steam tower gear")
        if im:
            dtiles.append(im)
        notes.append("gear: " + str([round(v) for v in gc]))
    else:
        notes.append("gear: ABSENT")
    # gothic porch: first porch ghost, aim at its front plane from outside
    pids = sorted({v[1].split("/", 1)[-1] for v in occ.values() if v[1].split("/", 1)[-1].startswith("porch_")})
    if pids:
        pc = [p_ for p_, v in occ.items() if v[1].endswith("/" + pids[0])]
        pcc = cen(pc)
        ex = [max(p_[i] for p_ in pc) - min(p_[i] for p_ in pc) for i in range(3)]
        # facing = from the nearest wing's centre to the porch (the porch stands on the wing's door face), head-on shot
        wl = [bounds([g_]) for k_, g_ in by.items() if k_.startswith("wing_")]
        best_ = None
        for lo_, hi_ in wl:
            wc_ = ((lo_[0] + hi_[0]) / 2, (lo_[2] + hi_[2]) / 2)
            dd_ = math.hypot(pcc[0] - wc_[0], pcc[2] - wc_[1])
            if best_ is None or dd_ < best_[0]:
                best_ = (dd_, wc_)
        away = (pcc[0] - best_[1][0], pcc[2] - best_[1][1]) if best_ else (pcc[0] - c[0], pcc[2] - c[2])
        nx, nz = ((1 if away[0] >= 0 else -1), 0) if abs(away[0]) >= abs(away[1]) else (0, (1 if away[1] >= 0 else -1))
        tgt = [pcc[0], pcc[1] + 1, pcc[2]]
        a0_ = math.atan2(nz, nx)
        head = [(math.cos(a0_ + d_ * math.pi / 180), math.sin(a0_ + d_ * math.pi / 180)) for d_ in (0, 12, -12, 25, -25)]
        ymin_p = min(p_[1] for p_ in pc)
        low_pts = [[pcc[0] + nx * 3, ymin_p + 2, pcc[2] + nz * 3], [pcc[0] + nx * 3 + nz * 3, ymin_p + 2, pcc[2] + nz * 3 + nx * 3],
                   [pcc[0] + nx * 3 - nz * 3, ymin_p + 2, pcc[2] + nz * 3 - nx * 3]]  # arch foot + both sides must be in view
        im = eye_shot(tgt, head, (14, 18, 11, 22, 26, 32), (7, 11, 15, 22, 28, 34), f"gothic porch head-on ({pids[0]})", 6.0, extra=low_pts)
        if im:
            dtiles.append(im)
        notes.append("porch: " + pids[0] + " " + str([round(v) for v in pcc]))
    else:
        notes.append("porch: ABSENT")
    # sci radar dish + solar roof garden/waterfall: oblique close-ups from outside
    def feature_shot(gid_, label, dists, ups, aim_dy=0):
        cs = fcells(lambda g_, b_: g_ == gid_)
        if not cs:
            notes.append(gid_ + ": ABSENT")
            return
        fc_ = cen(cs)
        out_ = (fc_[0] - c[0], fc_[2] - c[2])
        im_ = eye_shot([fc_[0], fc_[1] + aim_dy, fc_[2]], fan(*out_) + fan(-out_[0], -out_[1]), dists, ups, label, 10.0)
        if im_:
            dtiles.append(im_)
        notes.append(gid_ + ": " + str([round(v) for v in fc_]))
    feature_shot("radar", "sci radar dish + antennas", (36, 48, 60), (14, 24), 6)
    rg = fcells(lambda g_, b_: g_ == "roofgarden")
    if rg:  # waterfall: shoot along the face normal from outside, towards the lowest water column
        fl = clusters(rg, 3)[0]
        wat = [p_ for p_ in fl if occ[p_][0].startswith("minecraft:water")]
        ymin_ = min(q_[1] for q_ in wat) if wat else 0
        low_ = [p_ for p_ in wat if p_[1] <= ymin_ + 1] or wat
        high_ = [p_ for p_ in wat if p_[1] >= ymin_ + 5] or wat
        gc_ = cen(low_)
        hc_ = cen(high_)
        aw = (gc_[0] - hc_[0], gc_[2] - hc_[2])  # roof pond -> ground pool = outward normal of the waterfall face
        n_ = (1 if aw[0] >= 0 else -1, 0) if abs(aw[0]) >= abs(aw[1]) else (0, 1 if aw[1] >= 0 else -1)
        a1_ = math.atan2(n_[1], n_[0])
        head2 = [(math.cos(a1_ + d_ * math.pi / 180), math.sin(a1_ + d_ * math.pi / 180)) for d_ in (0, 20, -20, 40, -40)]
        im = eye_shot([gc_[0], gc_[1] + 8, gc_[2]], head2, (26, 34, 44), (8, 14), "solar roof garden + waterfall", 6.0)
        if im:
            dtiles.append(im)
        notes.append("roofgarden: " + str([round(v) for v in gc_]) + f" water {len(wat)}")
    else:
        notes.append("roofgarden: ABSENT")
    # pipe run (v16): collect straight runs of the teal pipe block in the features ghost, longest first; per run use the run's
    # mid point + the wall normal (side with a wall behind within 3 blocks and free air in front) and aim at the pipe face itself.
    pipes = {p_ for p_, v in occ.items() if v[1].endswith("/features") and v[0].split("[")[0] == "minecraft:waxed_oxidized_copper"}
    runs = []
    for axis in (0, 2):
        rows = {}
        for p_ in pipes:
            rows.setdefault((p_[1], p_[2 - axis]), []).append(p_[axis])
        for k_, vs in rows.items():
            vs.sort()
            st = prev_ = vs[0]
            for v_ in vs[1:] + [None]:
                if v_ is None or v_ - prev_ > 2:
                    if prev_ - st >= 8:
                        runs.append((prev_ - st, axis, k_, st, prev_))
                    if v_ is not None:
                        st = v_
                if v_ is not None:
                    prev_ = v_
    runs.sort(reverse=True)
    pipe_done = False
    wall_blocks = {k_: v_ for k_, v_ in occ.items() if not v_[1].endswith("/features") and v_[0] != "bbox"}
    for tree_pass in (True, False):  # v17: first look for a run with no tree in the view cone, then accept any
      if pipe_done:
        break
      for ln, axis, (yy_, o_), a0_, a1_ in runs[:16]:
            mid = (a0_ + a1_) // 2
            pt = (mid, yy_, o_) if axis == 0 else (o_, yy_, mid)
            nrm = (0, 1) if axis == 0 else (1, 0)  # perpendicular to the run, horizontal
            best_sg, best_sc = None, 0
            for sg in (1, -1):
                front = sum(1 for k in range(1, 7) for dy in (-1, 0, 1)
                            if (pt[0] + nrm[0] * sg * k, pt[1] + dy, pt[2] + nrm[1] * sg * k) in occ and occ[(pt[0] + nrm[0] * sg * k, pt[1] + dy, pt[2] + nrm[1] * sg * k)][0] != "bbox")
                back = sum(1 for k in (1, 2, 3) for dy in (-1, 0, 1) for t_ in (-4, 0, 4)
                           if (pt[0] - nrm[0] * sg * k + (t_ if axis == 0 else 0), pt[1] + dy, pt[2] - nrm[1] * sg * k + (t_ if axis == 2 else 0)) in wall_blocks)
                sc = back - 3 * front
                if front <= 4 and back >= 3 and sc > best_sc:
                    best_sg, best_sc = sg, sc
            if best_sg is None:
                continue
            tgt = [pt[0] + 0.5 + nrm[0] * best_sg * 0.5, pt[1] + 0.5, pt[2] + 0.5 + nrm[1] * best_sg * 0.5]
            sx_, sz_ = nrm[0] * best_sg * 0.5, nrm[1] * best_sg * 0.5
            def _pt(f_):
                v_ = a0_ + f_ * (a1_ - a0_) + 0.5
                return [v_, pt[1] + 0.5, pt[2] + 0.5 + sz_] if axis == 0 else [pt[0] + 0.5 + sx_, pt[1] + 0.5, v_]
            im = eye_shot(tgt, fan(nrm[0] * best_sg, nrm[1] * best_sg)[:5], (10, 14, 20), (2, 4, 7),
                          f"steam pipe run ({ln} long, face normal {nrm[0]*best_sg},{nrm[1]*best_sg})" + ("" if tree_pass else " TREES-FALLBACK"),
                          4.0, [_pt(0.25), _pt(0.75)], trees_ if tree_pass else None)
            if im:
                dtiles.append(im)
                notes.append(f"pipes: run {ln} at {pt} normal {(nrm[0]*best_sg, nrm[1]*best_sg)}")
                pipe_done = True
                break
    if not pipe_done:
        notes.append("pipes: ABSENT" if not runs else "pipes: runs found but no wall-backed face with a clear eye")
    print(gid, "detail:", "; ".join(notes))
    if dtiles:
        rows_d = (len(dtiles) + 1) // 2
        dsheet = Image.new("RGB", (TW * 2, TH * rows_d), (20, 20, 20))
        for i, im in enumerate(dtiles):
            dsheet.paste(im, ((i % 2) * TW, (i // 2) * TH))
        dsheet.save(OUT / f"{gid}_detail.jpg", quality=88)
        print(gid, len(dtiles), "detail shots ->", OUT / f"{gid}_detail.jpg")
    for g in sel:
        call("ghost_move", {"id": g["id"], "offset": [0, -LIFT, 0]})
    out = OUT / f"{gid}_sheet.jpg"
    sheet.save(out, quality=88)
    print(gid, len(tiles), "shots", lo, hi, out)

for g in ghosts:
    call("ghost_show", {"id": g["id"], "visible": True})
call("ghost_show", {"id": "*", "hud": True})
