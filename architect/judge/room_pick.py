"""v20: pick a REAL built room from replayed campus cells (no 70%-ceiling-layer rule).
A room light = kit glow block in a ceiling (solid/full block, not a floor lamp) with >=3 clear air cells below and a
solid floor within 10 below. The best room = densest cluster of such lights on one floor level inside one ghost
(radius 12), tie-break by furnishing (non-air cells between floor and ceiling). Returns None if no room has >=3 lights."""
FULL_GLOW = ("luminax", "shroomlight", "glowstone", "sea_lantern", "froglight", "copper_bulb", "redstone_lamp")
SKIP_GHOST = ("tower", "grounds", "platform", "tiers", "stairs", "features", "foundation")


def pick_room(cells, glow_words=None, prefer_wings=True):
    lights = []
    for (x, y, z), v in cells.items():
        blk, gi = v if isinstance(v, tuple) else (v, "")
        name = gi.split("/")[-1]
        if name in SKIP_GHOST or "ladder" in blk or not any(w in blk for w in FULL_GLOW):
            continue
        if any((x, y - d, z) in cells for d in (1, 2, 3)):
            continue
        fl = next((y - d for d in range(4, 12) if (x, y - d, z) in cells), None)
        if fl is None or (x, y + 1, z) not in cells and "bulb" not in blk:
            continue
        lights.append((x, y, z, fl, gi))
    if len(lights) < 3:
        return None
    best = None
    for (x, y, z, fl, gi) in lights:
        grp = [l for l in lights if l[4] == gi and abs(l[3] - fl) <= 1 and abs(l[1] - y) <= 1
               and abs(l[0] - x) <= 12 and abs(l[2] - z) <= 12]
        if len(grp) < 3:
            continue
        cx = sum(l[0] for l in grp) / len(grp)
        cz = sum(l[2] for l in grp) / len(grp)
        stuff = sum(1 for (a, b, c), v in cells.items() if abs(a - cx) <= 10 and abs(c - cz) <= 10 and fl < b < y)
        score = len(grp) + 0.04 * stuff + (3 if name_is_wing(gi) and prefer_wings else 0)
        if best is None or score > best[0]:
            best = (score, grp, stuff, gi, cx, cz, fl, y)
    if not best:
        return None
    score, grp, stuff, gi, cx, cz, fl, y = best
    return {"ghost": gi, "lights": len(grp), "stuff": stuff, "floor": fl, "ceil": y, "cut_y": y - 1,
            "aim": [cx, fl + 2, cz], "span": max(max(l[0] for l in grp) - min(l[0] for l in grp),
                                                 max(l[2] for l in grp) - min(l[2] for l in grp)) + 8}


def name_is_wing(gi):
    return gi.split("/")[-1].startswith("wing_") or gi.split("/")[-1] in ("hub", "halls")
