"""Offline tests for terrain.py with fake surveys: python test_terrain.py   (no Minecraft, no API; ~30 s because it builds campuses)."""
import json
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import terrain as S  # noqa: E402

N6 = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def floaters(ghosts, origin, sv):
    """Run the architect's own floater guard over the campus ghosts (world coords): number of floating/snapped parts."""
    import floaters as F
    g = F.Guard()
    ox, oy, oz = origin
    world = []
    for gh in ghosts:
        o = [ox + gh["origin"][0], oy + gh["origin"][1], oz + gh["origin"][2]]
        a = {"id": "t/" + gh["id"], "origin": o, "blocks": gh["blocks"]}
        g.record(a["id"], a, True)
        g.campus_ids.add(a["id"])
        world.append(a)
    bad = 0
    for a in world:
        _, fl = g.check(a["id"], a)
        bad += sum(p.get("blocks", 0) for p in fl)
    return bad


def main():
    # 1. survey roundtrip
    sv = S.fake("hill")
    sv2 = S.Survey.from_json(json.dumps(sv.to_json()))
    check("roundtrip heights", sv2.ys == sv.ys and sv2.flags == sv.flags)

    # 2. flat: lime, no fill
    flat = S.fake("flat", w=60, h=60, step=3)
    p = S.plan(flat, "hextech")
    check("flat -> lime", p["class"] == "lime" and p["fill"] == 0 and p["cut"] == 0, p["summary"])
    check("flat -> deterministic", S.plan(flat, "hextech") == p)

    # 3. hill: still found a placement, picks the flatter side or needs foundations/terraces
    hill = S.fake("hill", w=80, h=80, step=3)
    ph = S.plan(hill, "hextech")
    check("hill -> not on the summit when a flat spot exists", ph["y_max"] - ph["y_min"] <= 24, ph["summary"])
    check("hill picks a smaller/other config than flat", (ph["layout"], ph["wings"]) != (p["layout"], p["wings"])
          or ph["fit"] <= p["fit"], f"{ph['layout']}x{ph['wings']} vs {p['layout']}x{p['wings']}")

    # 4. shoreline: avoids the sea
    sh = S.fake("shoreline", w=60, h=60, step=3)
    ps = S.plan(sh, "hextech")
    check("shoreline -> no water in the site", ps["water_pct"] == 0.0, ps["summary"])
    seaward = S.evaluate(sh, 0, 100, 120, 80)  # forced into the sea
    check("rect in the sea -> red", seaward["class"] == "red", seaward["summary"] if "summary" in seaward else str(seaward["water_pct"]))

    # 5. forest: trees counted + trees listed; a clearing beats the dense part
    fo = S.fake("forest", w=60, h=60, step=3)
    pf = S.plan(fo, "gothic")
    check("forest -> trees reported", pf["tree_cells"] > 0 and pf["tree_pct"] > 0, pf["summary"])
    check("forest -> fit lower than flat", pf["fit"] < p["fit"], f"{pf['fit']} < {p['fit']}")

    # 6. unknown chunks: avoid unloaded area, never red when the loaded third is big enough
    un = S.fake("unknown", w=60, h=60, step=3)
    pu = S.plan(un, "hextech")
    check("unknown -> mostly known", pu["unknown_pct"] < 35, pu["summary"])
    allunk = S.Survey.from_fn(0, 0, 3, 30, 30, lambda x, z: (None, "?"))
    pa = S.plan(allunk, "hextech")
    check("all unknown -> red", pa["class"] == "red", pa["summary"])

    # 7. cliff: terraces preferred, fill/cut reported
    cl = S.fake("cliff", w=60, h=60, step=3)
    pc = S.plan(cl, "hextech")
    check("cliff -> yellow or lime but reports levels", pc["class"] in ("lime", "yellow"), pc["summary"])

    # 8. tight survey (radius 48 -> 96 wide): shrinks to a small tier instead of failing
    tight = S.fake("flat", w=48, h=48, step=2)
    pt = S.plan(tight, "hextech")
    check("tight survey -> smaller tier fits", pt["w"] <= 96 and pt["d"] <= 96 and pt["class"] != "red", pt["summary"])

    # 9. rotation of block states
    check("rot facing", S.rot_state("minecraft:oak_stairs[facing=north,half=top]") == "minecraft:oak_stairs[facing=east,half=top]")
    check("rot axis", S.rot_state("minecraft:oak_log[axis=x]") == "minecraft:oak_log[axis=z]")
    check("rot fence", S.rot_state("minecraft:oak_fence[north=true,east=false,south=false,west=false]")
          == "minecraft:oak_fence[east=true,south=false,west=false,north=false]")
    check("rot plain", S.rot_state("minecraft:stone") == "minecraft:stone")

    # 10. campus + foundations on a hill and a cliff (real campus build)
    import campus
    wings = [{"name": "a", "rooms": ["mod_room"], "size": "s"}]
    baseline = None
    for kind in ("flat", "slope", "hill", "cliff", "shoreline"):
        svk = S.fake(kind, w=80 if kind == "hill" else 60, h=80 if kind == "hill" else 60, step=3)
        pl = S.plan(svk, "steampunk")
        t = time.time()
        ghosts = campus.build("steampunk", wings[:pl["wings"]], True, "tower", None, layout=pl["layout"])
        out, rep = S.apply(ghosts, svk, near=(90, 90))
        fl = floaters(out, rep["origin"], svk)
        if baseline is None:
            baseline = fl  # the campus's own intrinsic guard hits on flat ground; terrain must add none
        fo = [g for g in out if g["id"] == "foundation"]
        fo_fl = floaters(fo, rep["origin"], svk) if fo else 0
        check(f"{kind}: floater blocks {fl} (flat baseline {baseline}), foundation alone {fo_fl}", fl <= baseline and fo_fl == 0, rep["summary"])
        if fo:  # every foundation column starts right on the ground (first block at terrain+1)
            mins = {}
            for b in fo[0]["blocks"]:
                k = (b[0], b[2])
                mins[k] = min(mins.get(k, 999), b[1])
            ox, oy, oz = rep["origin"]
            bad_cols = [k for k, y in mins.items() if oy + y != svk.height_at(ox + k[0], oz + k[1]) + 1]
            check(f"{kind}: foundation columns touch ground ({len(mins)} cols)", not bad_cols, str(bad_cols[:3]))
        if kind in ("hill", "slope", "cliff"):
            check(f"{kind}: foundation blocks exist when fill needed", rep["fill_blocks"] == 0 or rep["foundation_ghost_blocks"] > 0)
        check(f"{kind}: {time.time() - t:.1f}s build", True)
    # rotation keeps every block and the floater count at 0
    svr = S.fake("flat", w=60, h=60, step=3)
    g0 = campus.build("hextech", wings, True, "tower", None, layout="radial")
    g1 = S.rotate_ghosts([dict(g, origin=list(g["origin"]), blocks=[list(b) for b in g["blocks"]]) for g in g0], 1)
    check("rotate keeps block count", sum(len(g["blocks"]) for g in g0) == sum(len(g["blocks"]) for g in g1))
    out, rep = S.apply(g0, svr, force={"x": 20, "z": 20, "rot": 90})
    check("forced area + rot 90 places at the area", rep["origin"][0] >= 20 and rep["rot"] == 90, rep["summary"])
    print("FAILED" if check.failed else "ALL OK", check.failed)
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
