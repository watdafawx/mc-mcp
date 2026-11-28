"""Offline tests for motifs.py, the set-piece library: python test_motifs.py   (no Minecraft, no network).

Every motif in motifs.ALL is checked on its own (non-empty, only blocks the pack has, wall motifs outside the wall
and inside their SIZE box, top motifs above the deck, no unresolved {placeholders}, stairs with real compass
facings, for every kit and every side) and then through design.compose on the bench spec: no "skipped" note for a
motif that should fit, and nothing a feature adds lands inside another volume's rooms.
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shapes  # noqa: E402,F401  imported first on purpose (massing imports shapes; avoids a circular import)
import massing  # noqa: E402
import design  # noqa: E402
import motifs  # noqa: E402

AIR = "minecraft:air"
HERE = Path(__file__).parent
LIB = json.loads((HERE / "knowledge" / "blocklib.json").read_text("utf-8"))
COMPASS = {"north", "south", "east", "west"}
FACING = re.compile(r"facing=(\w+)")
NEW = ["porch", "balcony", "blade_sign", "timber_frame", "smokestack", "water_tank", "landing_pad", "crane"]


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def bid(b: str) -> str:
    return b.split("[", 1)[0]


def facade(kit: str, windows: str = "grid"):
    """A real facade to overlay: {(x, y, z): block} of a 33 x 21 hall with a south entrance, plus its flat-south-side
    `existing(u, v, y)` exactly as design._motif builds it (v along +x, u outward = +z from the edge row z = 20)."""
    blocks = massing.structure(shape="rect", w=33, d=21, floor_hs=[9, 6], program=["machine_hall", "workshop"],
                               kit=kit, windows=windows, entrances=["s"], seed=1)
    out = {(x, y, z): b for x, y, z, b in blocks}
    return out, (lambda u, v, y: out.get((v, y, 20 + u)))


def variants(kind: str, K: dict) -> list:
    """(label, cells) for every parameter set / style of one motif on kit K."""
    if kind in motifs.WALL:
        ps = motifs.candidates(kind, 0) + motifs.candidates(kind, 9)
        if kind == "porch":
            ps = [{"style": "classic"}, {"style": "industrial"}]
        if kind == "blade_sign":
            ps = [{"glyph": g} for g in ("H", "I", "O")]
        return [(f"{kind}{p}", motifs.WALL[kind](K, **p), p) for p in ps]
    if kind in motifs.LINE:
        if kind in motifs.OVERLAY:
            _, ex = facade(K["_kit"], "none")
            return [(kind, motifs.LINE[kind](K, 33, [9, 6], existing=ex), {})]
        return [(kind, motifs.LINE[kind](K, 33, [9, 6]), {})]
    return [(f"{kind}{wd}x{dd}", motifs.TOP[kind](K, wd, dd), {}) for wd, dd in ((21, 17), (31, 19), (15, 15))]


# ---------------------------------------------------------------------------------------------- each motif alone

check("every new motif is registered", all(m in motifs.ALL for m in NEW), str(motifs.ALL))
check("design.FEATURES follows motifs.ALL", all(m in design.FEATURES for m in motifs.ALL))
try:
    json.dumps(design.SCHEMA)
    check("design.SCHEMA still serialises", True)
except Exception as e:  # noqa: BLE001
    check("design.SCHEMA still serialises", False, str(e))
check("SYSTEM prompt describes every new motif", all(m in design.SYSTEM for m in NEW))

for kind in motifs.ALL:
    for kit in sorted(massing.KITS):
        K = massing._kit(kit)
        K["_kit"] = kit
        for label, cells, p in variants(kind, K):
            tag = f"{label} [{kit}]"
            if kind in motifs.TOP and not cells and label.endswith("15x15"):
                continue  # a deck too small for the motif returns nothing on purpose (21x17 and 31x19 must not)
            check(f"{tag}: non-empty", bool(cells))
            blocks = list(cells.values())
            missing = sorted({bid(b) for b in blocks if bid(b) not in LIB})
            check(f"{tag}: every block id is in blocklib", not missing, str(missing[:4]))
            if kind in motifs.WALL:
                hw, h = motifs.SIZE[kind](p)
                bad = [k for k in cells if k[0] < 0 or abs(k[1]) > hw or not 0 <= k[2] < h]
                check(f"{tag}: u >= 0 and inside its SIZE box ({hw}, {h})", not bad, str(bad[:3]))
            elif kind in motifs.TOP:
                wd, dd = (int(t) for t in re.search(r"(\d+)x(\d+)$", label).groups())
                # y >= 0 everywhere; the one allowed exception is the pagoda's lanterns hanging under its eave corners
                # OUTSIDE the deck rectangle (they replace the cornice stair there)
                bad = [k for k, b in cells.items() if k[1] < 0 and not (
                    "lantern[hanging=true]" in b and not (0 <= k[0] < wd and 0 <= k[2] < dd))]
                check(f"{tag}: nothing below the deck (y >= 0)", not bad, str(bad[:3]))
            elif kind in motifs.OVERLAY:
                bad = [k for k in cells if k[0] not in (-1, 0)]
                check(f"{tag}: only the wall plane and pier layer (u = -1, 0)", not bad, str(bad[:3]))
            for side in "nsew":
                oriented = [motifs.orient(b, side) for b in blocks]
                left = [b for b in oriented if "{" in b or "}" in b]
                if left:
                    check(f"{tag} side {side}: no placeholder left", False, left[0])
                    break
                stairs = [b for b in oriented if bid(b).endswith("_stairs")]
                badf = [b for b in stairs if (FACING.search(b) or [None, None])[1] not in COMPASS]
                if badf:
                    check(f"{tag} side {side}: stairs have a compass facing", False, badf[0])
                    break
                other = [m for b in oriented for m in FACING.findall(b) if m not in COMPASS | {"up", "down"}]
                if other:
                    check(f"{tag} side {side}: facing values are real", False, other[0])
                    break
            else:
                check(f"{tag}: placeholders resolve and facings are valid on all 4 sides", True)

# ---------------------------------------------------------------------------------------------- shapes of the pieces

K = massing._kit("steampunk")
B = motifs.porch(K, style="classic")
check("porch classic: 2 pillar columns at u=3 and a pediment", sum(1 for (u, v, y), b in B.items() if u == 3 and y == 2) == 2
      and max(y for (_, _, y) in B) >= 7)
check("porch classic: stairs at the threshold face in", B[(1, 0, 0)].endswith("[facing={in},half=bottom]"))
check("porch classic: a hanging lantern", any("lantern[hanging=true]" in b for b in B.values()))
BI = motifs.porch(K, style="industrial")
check("porch industrial: no columns (nothing at u=3 below the canopy)", not any(u == 3 and 1 <= y <= 3 and v != 0 for (u, v, y) in BI))
check("porch industrial: chains and iron bars", any("chain" in b for b in BI.values()) and any("iron_bars" in b for b in BI.values()))
BA = motifs.balcony(K)
check("balcony: slab floor, rail on the outer edge, upside-down stair brackets",
      all(BA[(2, v, 1)].endswith("[type=top]") for v in range(-2, 3)) and all((2, v, 2) in BA for v in range(-2, 3))
      and any("half=top" in b and "stairs" in b for b in BA.values()))
BS = motifs.blade_sign(K)
check("blade sign: 1 thick (v=0), 3 out, 5 board + chains + arm",
      {k[1] for k in BS} == {0} and max(k[0] for k in BS) == 3 and max(k[2] for k in BS) == 6)
BK = motifs.smokestack(K, h=16)
check("smokestack: wider at the base than the top (radius 2 -> 1)",
      len({k[0:2] for k in BK if k[2] == 2}) > len({k[0:2] for k in BK if k[2] == 11}))
check("smokestack: stays out of the wall (u >= 1) and has a campfire", min(k[0] for k in BK) >= 1
      and any("campfire" in b for b in BK.values()))
BT = motifs.water_tank(K, 21, 17)
check("water tank: 4 legs, near a corner (not the middle)", sum(1 for k in BT if k[1] == 0 and "stripped_spruce" in BT[k]) == 4
      and min(k[0] for k in BT) < 8 and min(k[2] for k in BT) < 8)
check("water tank: ladder", any("ladder" in b for b in BT.values()))
BL = motifs.landing_pad(K, 21, 17)
check("landing pad: white H, glowing edge lights, a gap in the rail",
      any(b == "minecraft:white_concrete" for b in BL.values())
      and sum(1 for k, b in BL.items() if k[1] == 0 and ("shroom" in b or "luminax" in b)) >= 4
      and any(k[1] == 1 for k in BL))
BC = motifs.crane(K, 31, 19)
check("crane: mast, cab glass, long jib with chain + hook, counterweight",
      max(k[1] for k in BC) >= 20 and any(b == "minecraft:glass" for b in BC.values())
      and any("hopper" in b for b in BC.values()) and sum(1 for b in BC.values() if "chain" in b) >= 5
      and max(k[0] for k in BC) - min(k[0] for k in BC) >= 15)
check("crane + tank + pad refuse a deck that is too small", not motifs.crane(K, 12, 9) and not motifs.water_tank(K, 9, 9)
      and not motifs.landing_pad(K, 11, 11))

# timber frame only replaces: posts + beams + (windows none) braces, never glass / doors
for kit in ("steampunk", "gothic", "solarpunk"):
    Kk = massing._kit(kit)
    for windows in ("grid", "none"):
        out, ex = facade(kit, windows)
        T = motifs.timber_frame(Kk, 33, [9, 6], existing=ex)
        glass = [(k, ex(*k)) for k in T if "glass" in (ex(*k) or "") or "pane" in (ex(*k) or "")]
        gone = [k for k in T if ex(*k) in (None, AIR)]
        check(f"timber_frame [{kit}/{windows}]: replaces only existing blocks, never glass or empty cells",
              bool(T) and not glass and not gone, f"{len(T)} cells, {len(glass)} glass, {len(gone)} empty")
        posts = [k for k, b in T.items() if b.endswith("[axis=y]")]
        check(f"timber_frame [{kit}/{windows}]: posts and beams", len(posts) >= 8 and any("axis_v" in b for b in T.values()))
    out, ex = facade(kit, "none")
    T = motifs.timber_frame(Kk, 33, [9, 6], existing=ex)
    floor_lines = (1, 10)  # y of the floor beams of a [9, 6] volume: those are beams, not braces
    braces = [k for k, b in T.items() if k[0] == -1 and "axis_v" in b and k[2] not in floor_lines]
    check(f"timber_frame [{kit}/none]: diagonal braces in the blank panels", len(braces) > 20, str(len(braces)))
check("timber_frame without an `existing` callable does nothing", motifs.timber_frame(K, 33, [9, 6]) == {})

# ---------------------------------------------------------------------------------------------- through compose

BENCH = json.loads((HERE / "designs" / "bench_motifs.json").read_text("utf-8"))
BENCH2 = json.loads((HERE / "designs" / "bench_motifs2.json").read_text("utf-8"))


def feat(kind, on, **o):
    f = {"kind": kind, "on": on, "to": "", "side": "s", "pos": 0.5, "size": 0, "level": 0}
    f.update(o)
    return f


def interiors(rep: dict, spec: dict) -> dict:
    """id -> (interior cells, y0, y top) like test_design.build()."""
    out, fixes = {}, []
    for s, rv in zip(spec["volumes"], rep["volumes"]):
        v = design.Vol(dict(s), fixes)
        cx, cy, cz = rv["corner"]
        v.x0, v.y0, v.z0 = cx, cy, cz
        v.fp = {(x + cx, z + cz) for x, z in v.footprint()}
        out[rv["id"]] = (design._interior(v), cy, cy + v.ry, v)
    return out


def run(spec: dict, name: str):
    """compose + the checks every placement must pass; returns (ghosts, report, features' cells, volume footprints)."""
    ghosts, rep = design.compose(spec)
    ins = interiors(rep, spec)
    cells = {(x, y, z): b for g in ghosts if g["id"] == "features" for x, y, z, b in g["blocks"]}
    inside = [(c, vid) for c in cells for vid, (cs, lo, hi, _v) in ins.items() if (c[0], c[2]) in cs and lo <= c[1] <= hi]
    check(f"{name}: no feature block inside another volume's rooms", not inside, str(inside[:2]))
    return ghosts, rep, cells, {vid: i[3].fp for vid, i in ins.items()}


PLACE = {  # motif -> feature (bench_motifs.json: hall 31x19 [s entrance] + tower 15x15 with a pagoda)
    "porch": feat("porch", "hall", side="s"),
    "balcony": feat("balcony", "tower", side="s", level=1, size=2),
    "blade_sign": feat("blade_sign", "hall", side="w", pos=0.3),
    "timber_frame": feat("timber_frame", "hall", side="w"),
    "smokestack": feat("smokestack", "hall", side="w", pos=0.7, size=6),
    "water_tank": feat("water_tank", "hall", side="top", size=9),
    "landing_pad": feat("landing_pad", "hall", side="top"),
    "crane": feat("crane", "hall", side="top", size=14),
}
base_ghosts, base_rep = design.compose(copy.deepcopy(BENCH))
base_cells = {(x, y, z): b for g in base_ghosts for x, y, z, b in g["blocks"]}
for kind in NEW:
    spec = copy.deepcopy(BENCH)
    spec["features"].append(PLACE[kind])
    ghosts, rep, cells, fps = run(spec, f"compose {kind}")
    skipped = [n for n in rep["notes"] if kind in n]
    check(f"compose {kind}: placed (no 'skipped' note)", not skipped, str(skipped))
    own = {c: b for c, b in cells.items() if base_cells.get(c) != b}
    check(f"compose {kind}: adds blocks", len(own) > 15, f"{len(own)} changed/new")
    if kind == "timber_frame":
        check("compose timber_frame: only replaced existing wall blocks (nothing added to air)",
              all(base_cells.get(c, AIR) != AIR for c in own))
        check("compose timber_frame: the replacements are logs", all("log" in cells[c] for c in own))
        check("compose timber_frame: no glass replaced", not any("glass" in base_cells[c] or "pane" in base_cells[c] for c in own))
    if kind == "smokestack":
        foot = {(x, z) for fp in fps.values() for (x, z) in fp}
        inside_fp = [c for c in own if (c[0], c[2]) in foot]
        top = max(c[1] for c in own)
        check("compose smokestack: stands outside every footprint", not inside_fp, str(inside_fp[:2]))
        hall = next(v for v in rep["volumes"] if v["id"] == "hall")
        check("compose smokestack: reaches roof level + size (6)", top == hall["corner"][1] + hall["size"][1] - 1 + 6, str(top))
    if kind in motifs.TOP and kind != "pagoda":
        hall = next(v for v in rep["volumes"] if v["id"] == "hall")
        roofy = hall["corner"][1] + hall["size"][1] - 1
        check(f"compose {kind}: sits above the roof deck", all(c[1] > roofy for c in own), f"min y {min(c[1] for c in own)} roof {roofy}")
    if kind == "porch":
        door = [c for c in cells if c[1] in (1, 2, 3)]
        check("compose porch: nothing in the doorway itself", not [c for c in door if (c[0], c[2]) in fps["hall"]])
    if kind == "balcony":
        check("compose balcony: never replaces a wall or glass block (only air)", all(base_cells.get(c, AIR) == AIR for c in own))

# placement rules in design.py
spec = copy.deepcopy(BENCH)
spec["features"] = [feat("porch", "hall", side="n"), feat("balcony", "hall", side="s", level=0)]  # no door / one floor
ghosts, rep = design.compose(spec)
check("porch on a side without a doorway is skipped with a note", any("porch" in n and "doorway" in n for n in rep["notes"]), str(rep["notes"]))
check("balcony on a one-floor volume is skipped with a note", any("balcony" in n for n in rep["notes"]), str(rep["notes"]))
spec["features"] = [feat("porch", "hall", side="s", size=1), feat("porch", "hall", side="s", size=2)]
g1, r1 = design.compose({**spec, "features": spec["features"][:1]})
g2, r2 = design.compose({**spec, "features": spec["features"][1:]})
f1 = {(x, y, z): b for g in g1 if g["id"] == "features" for x, y, z, b in g["blocks"]}
f2 = {(x, y, z): b for g in g2 if g["id"] == "features" for x, y, z, b in g["blocks"]}
check("porch size 1 = classic (columns), size 2 = industrial (iron bars + chains)",
      any("chain" in b for b in f2.values()) and not any("chain" in b for b in f1.values()))
spec = copy.deepcopy(BENCH)
spec["features"] = [feat("smokestack", "hall", side="e", pos=0.5, size=6)]  # the tower stands against that wall
ghosts, rep, cells, fps = run(spec, "smokestack beside a neighbour")
foot = [c for c in cells if any((c[0], c[2]) in fp for fp in fps.values())]
check("smokestack never goes through a neighbouring volume's footprint", not foot, f"{len(foot)} cells; notes {rep['notes']}")

# the full 12-motif bench spec: composes clean
ghosts, rep, cells, fps = run(copy.deepcopy(BENCH2), "bench_motifs2")
check("bench_motifs2: uses all 12 motifs", {f["kind"] for f in BENCH2["features"]} == set(motifs.ALL), str(sorted(motifs.ALL)))
check("bench_motifs2: nothing skipped", not rep["notes"], str(rep["notes"]))
check("bench_motifs2: 4 volumes", len(BENCH2["volumes"]) == 4 and len(rep["volumes"]) == 4)

print()
print("FAILED" if check.failed else "all ok", f"({check.failed} failed)")
sys.exit(1 if check.failed else 0)
