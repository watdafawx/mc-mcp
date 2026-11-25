"""Offline tests for depth.py, the facade depth pass: python test_depth.py   (no Minecraft, no network).

The pass runs at the end of massing.structure and may only ADD blocks outward from the building: the plinth skirt,
pier feet/capitals, the cornice, and the window sills/hoods in the recessed bays. Nothing inside the rooms, no
doorway filled in, no state the kit does not have. Disabled with ARCHITECT_DEPTH=0.
"""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shapes  # noqa: E402,F401  imported first on purpose (massing imports shapes; avoids a circular import)
import massing  # noqa: E402
import depth as D  # noqa: E402

AIR = "minecraft:air"
BLOCKLIB = Path(D.__file__).resolve().parent / "knowledge" / "blocklib.json"
FACING = re.compile(r"facing=(\w+)")
DIRVEC = {"east": (1, 0), "west": (-1, 0), "south": (0, 1), "north": (0, -1)}
KITS = ("gothic", "steampunk", "hextech", "station_white", "solarpunk")
RECT = dict(shape="rect", w=21, d=13, floor_hs=[9, 6], program=["machine_hall", "workshop"])


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def build(env, **kw):
    """massing.structure with ARCHITECT_DEPTH forced to `env`."""
    os.environ["ARCHITECT_DEPTH"] = env
    return {(b[0], b[1], b[2]): b[3] for b in massing.structure(**kw)}


def added(off, on):
    """{cell: block} for the cells only the ON build has."""
    return {c: b for c, b in on.items() if c not in off}


def first(d):
    return sorted(d.items())[0] if d else None


# ---------------------------------------------------------------------------------------------- shared helpers

def check_adds(off, on, label, want=100):
    add = added(off, on)
    changed = {c: (off[c], on[c]) for c in off if c in on and on[c] != off[c]}
    removed = {c: off[c] for c in off if c not in on}
    check(f"{label}: adds blocks (>{want})", len(add) > want, f"{len(add)} added")
    check(f"{label}: never changes a block of the OFF build", not changed,
          f"{len(changed)} changed, e.g. {first(changed)}")
    check(f"{label}: never removes a block of the OFF build", not removed,
          f"{len(removed)} removed, e.g. {first(removed)}")
    return add


def footprint_rings(kw):
    """The footprint and the cells depth may touch inside it: the plinth ring (x/z = 0 / w-1 / d-1, the cut
    corners of a shaped footprint) plus the wall ring one block in (x/z = 1 / w-2). Mirrors massing.structure."""
    fp = massing.footprint(kw["shape"], kw.get("w"), kw.get("d"), kw.get("r"), kw.get("r_in"),
                           kw.get("a0", 0), kw.get("a1", 360), kw.get("c"), kw.get("cut_w"), kw.get("cut_d"))
    outer = massing.edge(fp)
    wall = massing.edge({p for p in fp if p not in outer})
    return fp, outer | wall


def check_rooms(add, kw, label):
    """No added cell with 2 <= x <= w-3 and 2 <= z <= d-3: that box is the rooms, and modded play needs it.
    Cells outside the footprint are free (skirt, cornice); on a shaped footprint the cut corners count as free."""
    fp, ok = footprint_rings(kw)
    bad = {c: b for c, b in add.items() if (c[0], c[2]) in fp and (c[0], c[2]) not in ok}
    check(f"{label}: nothing added inside the rooms", not bad, f"{len(bad)} cells, e.g. {first(bad)}")
    if kw["shape"] == "rect":  # the same rule written out, exactly as the spec puts it
        w, d = kw["w"], kw["d"]
        box = {c: b for c, b in add.items() if 2 <= c[0] <= w - 3 and 2 <= c[2] <= d - 3 and (c[0], c[2]) in fp}
        check(f"{label}: no added cell in the 2..w-3 x 2..d-3 room box", not box,
              f"{len(box)} cells, e.g. {first(box)}")
    on_ring = sum(1 for c in add if (c[0], c[2]) in fp)
    free = len(add) - on_ring
    check(f"{label}: the pass adds both ring cells and free cells", on_ring > 0 and free > 0,
          f"{on_ring} inside the footprint / {free} outside")


def check_open(off, on, label):
    """Every explicitly empty (air) cell of the OFF build must stay open: those are the doorways and the core."""
    doors = {c: b for c, b in off.items() if b == AIR}
    hit = {c: (b, on[c]) for c, b in doors.items() if on.get(c) not in (None, AIR)}
    check(f"{label}: doorways and openings stay air", not hit,
          f"{len(hit)} of {len(doors)} air cells filled, e.g. {first(hit)}")
    check(f"{label}: the build does have air cells (doorways, core holes)", len(doors) > 0, len(doors))


def check_ids(add, lib, label):
    ids = {b.split("[", 1)[0] for b in add.values()}
    bad = sorted(i for i in ids if lib and i not in lib)
    check(f"{label}: every added block id exists in blocklib", not bad, f"{bad[:5]} ({len(ids)} ids)")
    check(f"{label}: added blocks are never air", AIR not in ids, sorted(ids)[:6])


def check_stairs(on, add, label):
    """A depth stair must touch the building: the neighbour its facing= names is a solid block of the ON build."""
    stairs = {c: b for c, b in add.items() if "_stairs[" in b or b.endswith("_stairs")}
    bad, noface = {}, {}
    for c, b in stairs.items():
        m = FACING.search(b)
        if not m:
            noface[c] = b
            continue
        vx, vz = DIRVEC[m.group(1)]
        nb = on.get((c[0] + vx, c[1], c[2] + vz))
        if nb is None or nb == AIR:
            bad[c] = (b, nb)
    check(f"{label}: added stairs declare a facing", not noface, first(noface))
    check(f"{label}: every added stair backs onto the building", not bad,
          f"{len(bad)} of {len(stairs)} loose, e.g. {first(bad)}")
    check(f"{label}: the pass actually adds stairs", len(stairs) > 10, f"{len(stairs)} stairs")


def check_same(a, b, label):
    diff = [c for c in a if a[c] != b.get(c)] + [c for c in b if c not in a]
    check(f"{label}: two ON builds are identical", not diff and len(a) == len(b),
          f"{len(diff)} cells differ, e.g. {sorted(diff)[:2]}")


# ------------------------------------------------------------------------------------------------------- 1-6. kits

def test_kits():
    lib = D.palette._lib()
    for kit in KITS:
        off = build("0", **RECT, kit=kit)
        on = build("1", **RECT, kit=kit)
        add = check_adds(off, on, f"{kit}")
        check_rooms(add, {**RECT, "kit": kit}, kit)
        check_open(off, on, kit)
        check_ids(add, lib, kit)
        check_stairs(on, add, kit)
        check_same(dict(on), build("1", **RECT, kit=kit), kit)
        print()


# --------------------------------------------------------------------------------------------- 7. env switch == off

def test_env_off():
    lib = D.palette._lib()  # warm the cache so the no-op run does no extra work
    before = os.environ.get("ARCHITECT_DEPTH")
    off = build("0", **RECT, kit="gothic")
    real = D.apply
    try:
        D.apply = lambda *a, **k: 0
        os.environ["ARCHITECT_DEPTH"] = "1"  # env says on, the pass is a no-op: must match the env-off build
        noop = build("1", **RECT, kit="gothic")
        check("env: ARCHITECT_DEPTH=0 equals depth.apply never running", off == noop,
              f"{len(added(off, noop))} cells differ, e.g. {first(added(off, noop))}")
        D.apply = real
        on = build("1", **RECT, kit="gothic")
        check("env: depth is back on after the restore", added(off, on) and on != off, f"{len(added(off, on))} added")
    finally:
        D.apply = real
        if before is None:
            os.environ.pop("ARCHITECT_DEPTH", None)
        else:
            os.environ["ARCHITECT_DEPTH"] = before
    check("env: the variable is restored", os.environ.get("ARCHITECT_DEPTH") == before,
          os.environ.get("ARCHITECT_DEPTH"))
    check("env: the OFF build is stable", off == build("0", **RECT, kit="gothic") and lib is not None)


# ------------------------------------------------------------------------------------------------- 8. octagon

def test_octagon():
    oct_kw = dict(shape="octagon", w=21, d=21, c=6, floor_hs=[8])
    off = build("0", **oct_kw, kit="gothic")
    on = build("1", **oct_kw, kit="gothic")
    add = check_adds(off, on, "octagon")
    check_ids(add, D.palette._lib(), "octagon")
    check_stairs(on, add, "octagon")
    # an octagon's cut corners are outside the footprint, so a skirt cell at x=2 is legal: the ring rule is
    # derived from the real footprint, not from the w x d rectangle
    check_rooms(add, oct_kw, "octagon")


def main():
    t0 = time.time()
    test_kits()
    test_env_off()
    test_octagon()
    print()
    print("FAILED" if check.failed else "ALL OK", check.failed, f"({time.time() - t0:.1f}s)")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
