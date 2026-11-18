"""Offline tests for floaters.Guard: python test_floaters.py   (no Minecraft, no API; <1 s)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import floaters as F  # noqa: E402

STONE = "minecraft:stone_bricks"


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def cells_of(args):
    return {c for _, _, cs in F.entries(args) if cs for c in cs}


def base_guard():
    """Ground slab at y=100, 11x11 deck at y=128 (x 810..820, z 3765..3775), tower column x=815,z=3770 y129..139 (lantern on top)."""
    g = F.Guard()
    a = {"origin": [0, 0, 0], "boxes": [
        [800, 100, 3760, 830, 100, 3780, STONE],
        [810, 128, 3765, 820, 128, 3775, STONE],
        [815, 129, 3770, 815, 138, 3770, STONE],
        [815, 139, 3770, 815, 139, 3770, "minecraft:lantern"]]}
    g.record("t/campus", a, True)
    return g


def call(g, gid, args):
    """Mimic the architect flow: guard check, then record what survived."""
    out, parts = g.check(gid, args)
    g.record(gid, out, args.get("mode", "replace") == "replace")
    return out, parts


def main():
    # (a) merge-mode air erase must drop cells; a later part must not snap onto the erased (phantom) cells
    g = F.Guard()
    g.record("t/ground", {"boxes": [[0, 64, 0, 40, 64, 40, STONE]]}, True)
    g.record("t/tower", {"boxes": [[10, 65, 10, 12, 75, 12, STONE]]}, True)
    check("a: tower cells recorded", (11, 70, 11) in g.cells["t/tower"])
    g.record("t/tower", {"mode": "merge", "boxes": [[10, 71, 10, 12, 75, 12, "minecraft:air"]]}, False)
    check("a: erased cells removed from Guard.cells", not any(c[1] >= 71 for c in g.cells["t/tower"]), f"left={len(g.cells['t/tower'])}")
    check("a: cells below the erase kept", (11, 70, 11) in g.cells["t/tower"])
    g.record("t/tower", {"mode": "merge", "blocks": [[11, 70, 11, "minecraft:air"]]}, False)
    check("a: single air block erased too", (11, 70, 11) not in g.cells["t/tower"] and (11, 69, 11) in g.cells["t/tower"])
    # new part hovering where the erased tower top was: must NOT stay put (phantom support), must snap to the real top (y=70)
    out, parts = g.check("t/top", {"boxes": [[10, 73, 10, 12, 73, 12, STONE]]})
    y = out["boxes"][0][1] if out.get("boxes") else None
    check("a: part snaps past phantom cells to the real top", y == 71, f"y={y} parts={parts}")

    # (b) solar19 detail_tower: 13x13 ring at y=140 above crown (lantern y=139), erased rod/pole cells in between
    g = base_guard()
    ring = [[809, 140, 3764, 821, 140, 3764, STONE], [809, 140, 3776, 821, 140, 3776, STONE],
            [809, 140, 3764, 809, 140, 3776, STONE], [821, 140, 3764, 821, 140, 3776, STONE]]
    # 1: a row at y=140 from the lantern to the ring edge (touches the lantern, so it is kept as is)
    out1, _ = call(g, "t/detail", {"boxes": [[815, 140, 3764, 815, 140, 3770, STONE]]})
    check("b: row kept at y=140", out1["boxes"][0][1] == 140, f"row={out1['boxes']}")
    # 2: merge call erases the row with an air box (these cells must not linger as phantom support)
    call(g, "t/detail", {"mode": "merge", "boxes": [[815, 140, 3764, 815, 140, 3770, "minecraft:air"]]})
    check("b: row cells erased", not any(c[1] == 140 for c in g.cells["t/detail"]))
    # 3: rod above the lantern + the 13x13 ring, both at y>=140 in one merge call
    out3, parts3 = call(g, "t/detail", {"mode": "merge", "boxes": ring + [[815, 141, 3770, 815, 143, 3770, "minecraft:lightning_rod"]]})
    rod = [b for b in out3["boxes"] if b[6] == "minecraft:lightning_rod"]
    check("b: rod snaps onto lantern (y=140..142)", rod and rod[0][1] == 140 and rod[0][4] == 142, f"rod={rod}")
    ys = {b[1] for b in out3["boxes"] if b[6] == STONE} | {b[4] for b in out3["boxes"] if b[6] == STONE}
    check("b: ring snaps down beside the real deck (y=128), not held at 140", ys == {128}, f"ys={ys} parts={parts3}")
    # nothing left hanging: re-check of every recorded cell against the rest finds no floating part
    hang = 0
    for gid in list(g.cells):
        others = set().union(*(s for k, s in g.cells.items() if k != gid))
        ground = g.ground()
        for c in g.cells[gid]:
            if c[1] > ground and not any((c[0] + d[0], c[1] + d[1], c[2] + d[2]) in (others | g.cells[gid]) for d in F.N6):
                hang += 1
    check("b: no isolated block left", hang == 0, f"hanging={hang}")

    print("FAILED:", check.failed) if check.failed else print("all ok")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
