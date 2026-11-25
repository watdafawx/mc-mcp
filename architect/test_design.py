"""Offline tests for design.compose, the spec -> ghosts composer: python test_design.py   (no Minecraft, no network).

compose() is the deterministic half of build-as-program: a design spec (volumes placed "at" a corner, "attach"ed to
a side or "stack"ed on a roof, plus features) becomes ghosts the builder places. It must never call a model: the
same spec and seed give the same blocks. And it owns the rules the designer model cannot be trusted with: no two
ground volumes overlap, modded interiors are big, every gap-0 attach gets a doorway through the shared wall, a
volume something stacks on gets a flat roof, decoration never eats another volume's rooms, and block ids the pack
does not have are dropped instead of placed.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shapes  # noqa: E402,F401  imported first on purpose (design imports massing; avoids a circular import)
import design  # noqa: E402

AIR = "minecraft:air"
HERE = Path(__file__).parent
DESIGNS = HERE / "designs"
VOID_ROLE = "minecraft:not_a_block"  # not in knowledge/blocklib.json: _roles must drop it


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


# ---------------------------------------------------------------------------------------------- shared helpers

def load(name: str) -> dict:
    return json.loads((DESIGNS / f"{name}.json").read_text("utf-8"))


def vol(**over) -> dict:
    """One schema-complete volume (every field SCHEMA asks for); keyword args edit it. `place=` merges into place."""
    v = {
        "id": "v", "purpose": "a hall", "shape": "rect", "w": 21, "d": 17, "r": 0, "cut_w": 0, "cut_d": 0,
        "floor_hs": [9], "program": ["machine_hall"], "roof": "flat", "windows": "band", "rhythm": 0,
        "accent_floor": -1, "open_ground": False, "entrances": ["s"], "roles": [],
        "place": {"mode": "at", "to": "", "side": "e", "align": "start", "offset": 0, "gap": 0, "x": 0, "z": 0},
    }
    at = over.pop("place", None)
    v.update(over)
    if at:
        v["place"] = {**v["place"], **at}
    return v


def spec(vols: list, roles: list | None = None, features: list | None = None) -> dict:
    return {"concept": "test design", "kit": "steampunk", "roles": roles or [], "volumes": vols,
            "features": features or []}


def feature(kind: str, on: str, **over) -> dict:
    """One schema-complete feature."""
    f = {"kind": kind, "on": on, "to": "", "side": "s", "pos": 0.5, "size": 0, "level": 0}
    f.update(over)
    return f


def merged(ghosts: list, skip: tuple = ()) -> dict:
    """{cell: block} of every ghost except the ids in `skip`."""
    out = {}
    for g in ghosts:
        if g["id"] in skip:
            continue
        for x, y, z, b in g["blocks"]:
            out[(x, y, z)] = b
    return out


def first(d):
    return sorted(d.items())[0] if d else None


def boxes(rep: dict) -> dict:
    """id -> (x0, y0, z0, x1, y1, z1) from the report's corner + size (size[1] is ry+1, the roofed envelope)."""
    out = {}
    for v in rep["volumes"]:
        x0, y0, z0 = v["corner"]
        w, h, d = v["size"]
        out[v["id"]] = (x0, y0, z0, x0 + w - 1, y0 + h - 1, z0 + d - 1)
    return out


def build(spec_: dict, seed: int = 1):
    """compose() plus the little re-runs the checks need: absolute footprints and interior cells per volume."""
    ghosts, rep = design.compose(spec_, seed)
    fps, inner = {}, {}
    fixes: list = []
    for s, rv in zip(spec_["volumes"], rep["volumes"]):
        v = design.Vol(dict(s), fixes)  # same clamps as compose: only the footprint is used
        cx, cy, cz = rv["corner"]
        v.x0, v.y0, v.z0 = cx, cy, cz
        v.fp = {(x + cx, z + cz) for x, z in v.footprint()}
        fps[rv["id"]] = v.fp
        inner[rv["id"]] = (design._interior(v), cy, cy + v.ry, v)
    return ghosts, rep, fps, inner


def doorway_cells(spec_: dict, rep: dict, fps: dict) -> list:
    """[(attach id, [cells])] for every gap-0 attach: the hole design._doorway cuts through the shared wall.

    Mirrors _doorway: 4 deep across both facade rings, 3 wide around the middle of the shared side's span, from
    ground+1 up to min(4, both ground floor heights - 1). Only the y rows +1..+3 are the test's business
    (the 4th row is the top of the door head, which the 3-wide reading does not need).
    """
    byid = {v["id"]: v for v in rep["volumes"]}
    out = []
    for v in spec_["volumes"]:
        pl = v["place"]
        if pl["mode"] != "attach" or int(pl.get("gap") or 0) != 0 or pl.get("to") not in byid:
            continue
        b, a = byid[v["id"]], byid[pl["to"]]
        if a["corner"][1] != b["corner"][1] or a["floors"][0] < 5 or b["floors"][0] < 5:
            continue  # the composer only carves between two volumes at the same ground height
        side = pl.get("side") if pl.get("side") in design.SIDES else "e"
        ax0, ay, az0 = a["corner"]
        aw, _, ad = a["size"]
        ax1, az1 = ax0 + aw - 1, az0 + ad - 1
        fa, fb = fps[a["id"]], fps[b["id"]]
        if side in "ns":
            span = sorted({p[0] for p in fa} & {p[0] for p in fb})
        else:
            span = sorted({p[1] for p in fa} & {p[1] for p in fb})
        if len(span) < 5:
            continue
        mid = span[len(span) // 2]
        if side == "e":
            cut = [(ax1 + k, t) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
        elif side == "w":
            cut = [(ax0 - k, t) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
        elif side == "s":
            cut = [(t, az1 + k) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
        else:
            cut = [(t, az0 - k) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
        hgt = min(4, a["floors"][0] - 1, b["floors"][0] - 1)
        y0 = max(a["corner"][1], b["corner"][1])
        out.append((v["id"], [(x, y, z) for x, z in cut for y in range(y0 + 1, y0 + min(3, hgt) + 1)]))
    return out


def check_disjoint_fps(spec_: dict, fps: dict, rep: dict, label: str):
    """No two ground volumes (not stacked) share a footprint cell where their bodies share a height."""
    stacked = {v["id"] for v in spec_["volumes"] if v["place"]["mode"] == "stack"}
    bh = {v["id"]: (v["corner"][1], sum(v["floors"]) + 1) for v in rep["volumes"]}  # ground y, body height (ry)
    ground = [i for i in fps if i not in stacked]
    pairs, bad = 0, {}
    for i, a in enumerate(ground):
        for b in ground[i + 1:]:
            if bh[a][0] > bh[b][0] + bh[b][1] or bh[b][0] > bh[a][0] + bh[a][1]:
                continue  # their bodies never share a height: a footprint conflict would be harmless
            pairs += 1
            hit = fps[a] & fps[b]
            if hit:
                bad[(a, b)] = sorted(hit)[:2]
    check(f"{label}: there are ground volumes side by side to test", pairs > 0, f"{pairs} pairs")
    check(f"{label}: no two ground volume footprints overlap", not bad, f"{len(bad)} overlapping, {first(bad)}")


# ---------------------------------------------------------------------------------------- 1. deterministic

def test_determinism():
    for name in ("bench_factory", "live_factory"):
        s = load(name)
        before = json.dumps(s, sort_keys=True)
        a, ra = design.compose(s)
        b, rb = design.compose(s)
        check(f"{name}: same spec + seed gives identical ghosts", a == b,
              f"{len(a)} ghosts / {sum(len(g['blocks']) for g in a)} blocks")
        check(f"{name}: same spec + seed gives the same report",
              (ra["fixes"], ra["volumes"], ra["notes"], ra["doorways"], ra["blocks"])
              == (rb["fixes"], rb["volumes"], rb["notes"], rb["doorways"], rb["blocks"]))
        check(f"{name}: compose does not mutate the spec", json.dumps(s, sort_keys=True) == before)
        print()


# ------------------------------------------------------------------------------------------ 2. no overlaps

def test_overlaps():
    for name in ("bench_factory", "live_factory"):
        s = load(name)
        ghosts, rep, fps, inner = build(s)
        check_disjoint_fps(s, fps, rep, name)
        check(f"{name}: the composer did not have to give up on an overlap",
              not any("could not clear an overlap" in f for f in rep["fixes"]), rep["fixes"])
        print()
    # two absolute volumes dropped on top of each other: the second must be pushed clear
    s = spec([vol(id="a", w=21, d=17), vol(id="b", w=21, d=17, place={"mode": "at", "x": 3, "z": 3})])
    ghosts, rep, fps, inner = build(s)
    bx = boxes(rep)
    check_disjoint_fps(s, fps, rep, "push")
    check("push: the second at-volume was moved clear of the first",
          bx["b"][0] > bx["a"][3] or bx["b"][2] > bx["a"][5], f"a {bx['a'][:1] + (bx['a'][3],)} b {bx['b'][:1] + (bx['b'][3],)}")
    check("push: the requested overlap did not stop the build", len(ghosts) == 2 and rep["blocks"] > 1000,
          f"{rep['blocks']} blocks")


# -------------------------------------------------------------------------------------- 3. big interiors

def test_big_interior():
    s = spec([vol(id="hall", floor_hs=[5], w=11, d=11)])
    ghosts, rep = design.compose(s)
    v = rep["volumes"][0]
    check("big: a machine hall floor of 5 is raised to 9", v["floors"] == [9], v["floors"])
    check("big: a machine hall 11 wide becomes at least 15", v["size"][0] >= 15, v["size"])
    check("big: a machine hall 11 deep becomes at least 15", v["size"][2] >= 15, v["size"])
    check("big: the fix is reported for the floor height",
          any("floor 0 height 5 -> 9" in f and "machine_hall" in f for f in rep["fixes"]), rep["fixes"])
    check("big: the fix is reported for the width", any("w 11 -> 15" in f for f in rep["fixes"]), rep["fixes"])
    check("big: the fix is reported for the depth", any("d 11 -> 15" in f for f in rep["fixes"]), rep["fixes"])
    check("big: the clear inside is >= 11 wide", v["clear_inside"][0] >= 11, v["clear_inside"])
    # the same numbers on a living floor are legal: the rule is about the program, not a blanket minimum
    ghosts, rep = design.compose(spec([vol(id="flat", program=["living"], floor_hs=[4], w=11, d=11)]))
    v = rep["volumes"][0]
    check("big: a living floor of 4 is left alone", v["floors"] == [4], v["floors"])
    check("big: an 11-wide living volume is left alone", v["size"][0] == 11, v["size"])
    check("big: nothing to fix on a legal volume", not rep["fixes"], rep["fixes"])


# --------------------------------------------------------------------------------- 4. stacking / flat roofs

def test_stack():
    s = spec([vol(id="hall", w=21, d=21, floor_hs=[9], roof="sawtooth"),
              vol(id="tower", w=9, d=9, floor_hs=[6], program=["hall"], roof="spire",
                  place={"mode": "stack", "to": "hall", "x": 0, "z": 0})])
    ghosts, rep = design.compose(s)
    by = {v["id"]: v for v in rep["volumes"]}
    hall, tower = by["hall"], by["tower"]
    check("stack: the volume something stands on gets a flat roof", hall["roof"] == "flat", hall["roof"])
    check("stack: the stacked volume sits on the base roof line",
          tower["corner"][1] == hall["corner"][1] + sum(hall["floors"]) + 1,
          f"{tower['corner'][1]} vs {hall['corner'][1]} + {sum(hall['floors'])} + 1")
    check("stack: the stacked volume keeps its own roof", tower["roof"] == "spire", tower["roof"])
    check("stack: the stacked volume stays inside the base footprint",
          tower["corner"][0] > hall["corner"][0] and tower["corner"][0] + tower["size"][0]
          < hall["corner"][0] + hall["size"][0], f"{tower['corner']} / {tower['size']}")
    # the shipped fixture stacks the tower on the hall the same way
    ghosts, rep = design.compose(load("live_factory"))
    by = {v["id"]: v for v in rep["volumes"]}
    hall, tower = by["hall"], by["tower"]
    check("live_factory: the stacked-on hall has a flat roof", hall["roof"] == "flat", hall["roof"])
    check("live_factory: the tower starts at the hall's roof line",
          tower["corner"][1] == hall["corner"][1] + sum(hall["floors"]) + 1,
          f"{tower['corner'][1]} vs {hall['corner'][1]} + {sum(hall['floors'])} + 1")


# ----------------------------------------------------------------------------------------- 5. doorways

def check_doorways(spec_: dict, label: str, allow_features: bool = False):
    ghosts, rep, fps, inner = build(spec_)
    doors = doorway_cells(spec_, rep, fps)
    cells = [c for _, cs in doors for c in cs]
    check(f"{label}: gap-0 attaches are reported as doorways", rep["doorways"] >= 1 and len(doors) >= 1,
          f"{rep['doorways']} doorways, {len(doors)} gap-0 attaches")
    check(f"{label}: the doorway cells were actually checked", len(cells) >= 9 * 3, f"{len(cells)} cells")
    volmap = merged(ghosts, skip=("features", "platform"))
    bad = {c: volmap[c] for c in cells if volmap.get(c) not in (None, AIR)}
    check(f"{label}: the doorway is open in the merged volume blocks", not bad,
          f"{len(bad)} of {len(cells)} filled, e.g. {first(bad)}")
    if not allow_features:  # a gear/pipes run may legitimately be put over the door later, in the features ghost
        full = merged(ghosts)
        bad2 = {c: full[c] for c in cells if full.get(c) not in (None, AIR)}
        check(f"{label}: the doorway is still open in the finished build", not bad2,
              f"{len(bad2)} of {len(cells)} filled, e.g. {first(bad2)}")
    return rep


def test_doorways():
    check_doorways(load("bench_factory"), "bench_factory")
    # live_factory puts a gear disc on the hall's south face, over the wing's door: open in the walls, covered after
    check_doorways(load("live_factory"), "live_factory", allow_features=True)
    print()
    # a plain gap-0 attach: one door, and a gap >= 3 leaves a yard instead (bridge space, no door)
    a = vol(id="a", w=21, d=17)
    b0 = vol(id="b", w=15, d=13, place={"mode": "attach", "to": "a", "side": "e", "gap": 0, "align": "center"})
    rep = check_doorways(spec([a, b0]), "gap 0")
    check("gap 0: exactly one doorway was carved", rep["doorways"] == 1, rep["doorways"])
    ghosts, rep, fps, inner = build(spec([a, vol(id="c", w=15, d=13,
                                                 place={"mode": "attach", "to": "a", "side": "e", "gap": 3,
                                                        "align": "center"})]))
    check("gap 3: a yard is not a doorway", rep["doorways"] == 0, rep["doorways"])
    check("gap 3: the yard volume is clear of the base",
          not (fps["a"] & fps["c"]), f"{len(fps['a'] & fps['c'])} shared cells")


# ------------------------------------------------------------------------------ 6. features stay outside

def check_features(spec_: dict, label: str):
    ghosts, rep, fps, inner = build(spec_)
    feat = merged(ghosts, skip=tuple(g["id"] for g in ghosts if g["id"] != "features"))
    check(f"{label}: there are feature blocks to check", len(feat) > 100, f"{len(feat)} cells")
    check(f"{label}: there are interiors to check against", any(i[0] for i in inner.values()),
          f"{sum(len(i[0]) for i in inner.values())} interior cells")
    bad = {}
    for (x, y, z), b in feat.items():
        for vid, (cells, lo, hi, _v) in inner.items():
            if lo <= y <= hi and (x, z) in cells:
                bad[(vid, x, y, z)] = b
    check(f"{label}: no feature block lands inside another volume", not bad,
          f"{len(bad)} inside, e.g. {first(bad)}")


def test_features():
    for name in ("bench_factory", "live_factory"):
        check_features(load(name), name)
    print()


# ------------------------------------------------------------------------------------ 7. bad role block ids

def test_bad_role():
    s = load("bench_factory")
    s["roles"] = [{"role": "wall2", "block": VOID_ROLE}, {"role": "pillar", "block": "minecraft:stone_bricks"}]
    ghosts, rep = design.compose(s)
    ids = {b.split("[", 1)[0] for g in ghosts for _, _, _, b in g["blocks"]}
    check("role: blocklib is loaded (the filter is active)", bool(design.palette._lib()))
    check("role: a block id the pack does not have is never used", VOID_ROLE not in ids,
          f"{len(ids)} ids")
    check("role: the other overrides still apply", "minecraft:stone_bricks" in ids, sorted(ids)[:6])
    check("role: dropping it does not stop the build", rep["blocks"] > 1000, f"{rep['blocks']} blocks")


# ------------------------------------------------------------------------------- 8. unknown attach target

def test_unknown_target():
    s = spec([vol(id="a", w=21, d=17),
              vol(id="lost", w=15, d=13, place={"mode": "attach", "to": "nope", "side": "e", "gap": 0})])
    ghosts, rep, fps, inner = build(s)
    fix = [f for f in rep["fixes"] if "'nope'" in f and "not placed" in f]
    check("unknown target: the fallback is reported", bool(fix), rep["fixes"])
    check("unknown target: the compose still returns both volumes", [v["id"] for v in rep["volumes"]] == ["a", "lost"],
          [v["id"] for v in rep["volumes"]])
    check("unknown target: the build still has blocks", rep["blocks"] > 1000 and len(ghosts) == 2,
          f"{rep['blocks']} blocks, {len(ghosts)} ghosts")
    check("unknown target: the fallback volume is placed clear of the site",
          not (fps["a"] & fps["lost"]), f"{len(fps['a'] & fps['lost'])} shared cells")


# -------------------------------------------------------------------------------------------- 9. platform

def test_platform():
    ghosts, rep = design.compose(spec([vol(id="a"), vol(id="b", w=15, d=13,
                                                    place={"mode": "attach", "to": "a", "side": "e",
                                                           "gap": 0})],
                                      features=[feature("platform", "a", side="top", size=2)]))
    by = {v["id"]: v for v in rep["volumes"]}
    withplat = merged(ghosts, skip=tuple(g["id"] for g in ghosts if g["id"] != "platform"))
    check("platform: the platform ghost is there", "platform" in {g["id"] for g in ghosts},
          [g["id"] for g in ghosts])
    check("platform: the volumes stand on top of it",
          by["a"]["corner"][1] == 2 and by["b"]["corner"][1] == 2,
          f"{by['a']['corner'][1]} / {by['b']['corner'][1]}")
    check("platform: the platform is below the volumes",
          bool(withplat) and max(y for (_, y, _) in withplat) < by["a"]["corner"][1],
          f"top {max((y for (_, y, _) in withplat), default=None)}")
    ghosts, rep = design.compose(spec([vol(id="a")], features=[feature("platform", "a", side="top", size=9)]))
    check("platform: the lift is clamped to 3 steps", rep["volumes"][0]["corner"][1] == 3,
          rep["volumes"][0]["corner"][1])
    ghosts, rep = design.compose(spec([vol(id="a")]))
    check("platform: without the feature nothing is lifted", rep["volumes"][0]["corner"][1] == 0,
          rep["volumes"][0]["corner"])
    check("platform: without the feature there is no platform ghost",
          [g["id"] for g in ghosts] == ["a"], [g["id"] for g in ghosts])


# ----------------------------------------------------------------------------------- 10. block shape

def check_blocks(ghosts: list, rep: dict, label: str, plat: bool = False):
    """Every block is a plain [x, y, z, "id:name"] cell, and the site never grows into negative x/z.

    Volume blocks must stay at >= 0. Feature blocks get 2 cells of slack: _side_cells puts decoration one block
    out and a chimney on a north/west face steps one further out, while compose() pads the site by 1 (no platform)
    -- so for now a north chimney on the site's north edge lands at z = -1 (see the note in the wrap-up). With a
    platform the padding is >= 2*lift+2, which covers it, so there the bound is the strict one.
    """
    bad = [b for g in ghosts for b in g["blocks"] if not (
        isinstance(b, list) and len(b) == 4 and all(isinstance(c, int) and not isinstance(c, bool) for c in b[:3])
        and isinstance(b[3], str) and ":" in b[3])]
    check(f"{label}: every block is [int, int, int, 'id:name']", not bad, f"{len(bad)} bad, e.g. {bad[:1]}")
    volcells = merged(ghosts, skip=("features",))
    neg_x = [c for c in volcells if c[0] < 0]
    neg_z = [c for c in volcells if c[2] < 0]
    check(f"{label}: no volume or platform block has negative x", not neg_x, f"{len(neg_x)}, e.g. {neg_x[:1]}")
    check(f"{label}: no volume or platform block has negative z", not neg_z, f"{len(neg_z)}, e.g. {neg_z[:1]}")
    feat = merged(ghosts, skip=tuple(g["id"] for g in ghosts if g["id"] != "features"))
    slack = 0 if plat else 2
    out = {c: b for c, b in feat.items() if c[0] < -slack or c[2] < -slack}
    check(f"{label}: feature blocks stay on the site (>= {-slack})", not out, f"{len(out)} off, e.g. {first(out)}")
    ids = [g["id"] for g in ghosts]
    check(f"{label}: ghost ids are unique and non-empty", len(ids) == len(set(ids)) and all(ids), ids)
    check(f"{label}: the report counts what the ghosts hold",
          rep["blocks"] == sum(len(g["blocks"]) for g in ghosts), f"{rep['blocks']}")


def test_blocks():
    for name in ("bench_factory", "live_factory"):
        ghosts, rep = design.compose(load(name))
        plat = any(f.get("kind") == "platform" for f in load(name)["features"])
        check_blocks(ghosts, rep, name, plat)
        check(f"{name}: the last ghost is the features one", ghosts[-1]["id"] == "features",
              [g["id"] for g in ghosts])
        print()


def main():
    import time
    t0 = time.time()
    test_determinism()
    test_overlaps()
    test_big_interior()
    test_stack()
    test_doorways()
    test_features()
    test_bad_role()
    test_unknown_target()
    test_platform()
    test_blocks()
    print()
    print("FAILED" if check.failed else "ALL OK", check.failed, f"({time.time() - t0:.1f}s)")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
