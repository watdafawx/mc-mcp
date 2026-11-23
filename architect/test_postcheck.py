"""Offline tests for postcheck.py: python test_postcheck.py   (no Minecraft, no API; <1 s)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import postcheck as P  # noqa: E402

STONE = "minecraft:stone_bricks"
COBBLE = "minecraft:cobblestone"


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def ghost(gid, lo, hi):
    return {"id": gid, "world_min": list(lo), "world_max": list(hi), "blocks": []}


def slab(w, d, y=0, state=STONE):
    """Solid w x d slab at local y (the bottom of the structure)."""
    return [[lx, y, lz, state] for lx in range(w) for lz in range(d)]


def columns(found):
    """{(lx, lz): sorted local ys} of foundation blocks."""
    out = {}
    for b in found:
        out.setdefault((b[0], b[2]), []).append(b[1])
    return {k: sorted(v) for k, v in out.items()}


def test_proportions():
    plan = {"reference": {"footprint": "20x15", "height": 10}}
    good = [ghost("base/tower", (0, 64, 0), (19, 73, 14))]  # 20 W x 10 H x 15 D
    check("proportion: good match -> []", P.proportion_check(plan, good) == [], P.proportion_check(plan, good))

    # the auto-foundation ghost must not widen the bounds
    with_found = good + [ghost("base/foundation", (0, 55, 0), (19, 63, 14))]
    check("proportion: foundation ghost ignored", P.proportion_check(plan, with_found) == [],
          P.proportion_check(plan, with_found))

    # squashed: same 20x15 footprint but only 4 high (planned ratio 10/20 = 0.50)
    squashed = [ghost("base/tower", (0, 64, 0), (19, 67, 14))]
    w = P.proportion_check(plan, squashed)
    check("proportion: squashed height -> warning", any(s.startswith("squashed: H/W") for s in w), w)

    # stretched / too small: 8 x 6 x 6 against a planned 20 x 15 x 12
    plan3 = {"reference": "a keep with a footprint 20 x 15 x 12, stone walls"}
    small = [ghost("base/keep", (100, 64, 200), (107, 69, 205))]
    w = P.proportion_check(plan3, small)
    check("proportion: too small -> width warning", any(s.startswith("width 8 vs planned 20") for s in w), w)
    check("proportion: too small -> depth warning", any(s.startswith("depth 6 vs planned 15") for s in w), w)
    check("proportion: too small -> height warning", any(s.startswith("height 6 vs planned 12") for s in w), w)

    # flat pancake warns even with no plan at all
    flat = [ghost("base/deck", (0, 64, 0), (9, 65, 9))]
    w = P.proportion_check({}, flat)
    check("proportion: flat 10x10x2 -> very flat warning", any("very flat (H=2 on 10x10" in s for s in w), w)

    # too tall/narrow the other way
    plan_tall = {"target_size": [8, 30, 8]}  # [w, h, d]: ratio 3.75
    tall = [ghost("base/spire", (0, 64, 0), (7, 78, 7))]  # 8 x 15 x 8: ratio 1.875
    w = P.proportion_check(plan_tall, tall)
    check("proportion: squashed against a tall plan", any(s.startswith("squashed: H/W") for s in w), w)

    # empty / no plan / no ghosts
    check("proportion: empty ghosts -> []", P.proportion_check({}, []) == [])
    check("proportion: no plan -> []", P.proportion_check({}, good) == [], P.proportion_check({}, good))
    check("proportion: no world_min -> []", P.proportion_check(plan, [{"id": "a/b", "blocks": []}]) == [])

    # 2-number footprint plans and dict sizes parse too
    check("proportion: 2-number reference footprint ok",
          P.proportion_check({"reference": "footprint 20x15"}, good) == [])
    check("proportion: dict size parses",
          P.proportion_check({"size": {"width": 20, "depth": 15, "height": 10}}, good) == [])
    check("proportion: size tier string ignored", P.proportion_check({"size": "m"}, good) == [])


def test_local_foundation():
    struct = slab(12, 12) + [[lx, 1, lz, STONE] for lx in range(12) for lz in (0, 11)]
    flat = lambda x, z: 63  # noqa: E731
    check("foundation: flat ground -> []", P.local_foundation(struct, (0, 64, 0), flat) == [])

    slope = lambda x, z: 63 - max(0, x)  # noqa: E731
    found = P.local_foundation(struct, (0, 64, 0), slope)
    cols = columns(found)
    check("foundation: slope -> blocks", len(found) > 0, f"{len(found)} blocks")
    states = {b[3] for b in found}
    check("foundation: only wall + pillar blocks", states <= {STONE, COBBLE}, states)
    ground = {(lx, lz): 63 - max(0, lx) for lx in range(12) for lz in range(12)}
    check("foundation: every column starts one above the ground",
          all(min(ys) == ground[k] + 1 - 64 for k, ys in cols.items()),
          {k: cols[k][0] for k in list(cols)[:3]})
    check("foundation: every column reaches the structure base",
          all(max(ys) == -1 for ys in cols.values()), sorted({max(v) for v in cols.values()}))
    # perimeter of the footprint (lx 0/11 or lz 0/11) -> stone bricks, from the ground up
    perim = [(11, 5), (1, 0), (5, 0), (5, 11)]
    check("foundation: perimeter columns are stone bricks",
          all(k in cols and all(b[3] == STONE for b in found if (b[0], b[2]) == k) for k in perim),
          {k: cols.get(k) for k in perim})
    check("foundation: far perimeter column is deep", cols[(11, 5)] == list(range(-11, 0)), cols.get((11, 5)))
    # interior 4-block grid -> cobblestone pillars (lx 4/8, lz 4/8), edge ones stay stone
    check("foundation: interior 4-grid pillar is cobblestone",
          (4, 4) in cols and all(b[3] == COBBLE for b in found if (b[0], b[2]) == (4, 4)),
          cols.get((4, 4)))
    check("foundation: interior pillar touches ground",
          cols[(4, 4)][0] == ground[(4, 4)] + 1 - 64, cols.get((4, 4)))
    check("foundation: non-grid interior column skipped", (5, 5) not in cols and (6, 6) not in cols,
          [k for k in cols if k not in perim][:8])
    check("foundation: columns already on the ground are skipped", not any(k[0] == 0 for k in cols),
          sorted(k for k in cols if k[0] == 0))

    # high balcony / overhang: base slab at ly=0, a deck far above at ly=6 hanging outside the footprint
    base = slab(6, 6)
    balcony = [[lx, 6, lz, STONE] for lx in range(8, 11) for lz in range(6)]
    deep = lambda x, z: 40  # noqa: E731
    found = P.local_foundation(base + balcony, (0, 64, 0), deep, max_depth=64)
    cols = columns(found)
    check("foundation: balcony gets no stilts", not any(k[0] >= 8 for k in cols), sorted(cols))
    check("foundation: base still gets foundations", (0, 0) in cols and (5, 5) in cols, sorted(cols))
    check("foundation: deep base column reaches the ground", min(cols[(0, 0)]) == 41 - 64, cols.get((0, 0)))
    check("foundation: deep base column reaches the slab", max(cols[(0, 0)]) == -1, cols.get((0, 0)))

    # max_depth caps a deep gap, still anchored on the ground
    capped = P.local_foundation(base, (0, 64, 0), deep, max_depth=4)
    ccols = columns(capped)
    check("foundation: max_depth respected", all(len(v) == 4 for v in ccols.values()), sorted({len(v) for v in ccols.values()}))
    check("foundation: capped pier starts at the ground", all(min(v) == 41 - 64 for v in ccols.values()),
          {k: v for k, v in list(ccols.items())[:2]})
    check("foundation: max_depth 0 -> []", P.local_foundation(base, (0, 64, 0), deep, max_depth=0) == [])

    # unknown ground / water / unloaded columns are skipped, never guessed
    check("foundation: ground_fn None -> []", P.local_foundation(struct, (0, 64, 0), lambda x, z: None) == [])
    half = P.local_foundation(struct, (0, 64, 0), lambda x, z: None if x >= 6 else 60)
    check("foundation: unknown columns skipped", half and all(b[0] < 6 for b in half),
          sorted({b[0] for b in half}))

    # air blocks are not part of the structure
    hollow = [[lx, 0, lz, "minecraft:air"] for lx in range(8) for lz in range(8)]
    hollow += [[2, 0, 2, STONE], [2, 6, 2, STONE]]
    cols = columns(P.local_foundation(hollow, (0, 64, 0), deep))
    check("foundation: air ignored for column bottoms", (2, 0) not in cols and (2, 2) in cols, sorted(cols))
    check("foundation: air-only ghost -> []",
          P.local_foundation([[0, 0, 0, "minecraft:cave_air"]], (0, 64, 0), deep) == [])

    # origin is honoured (local x/z offset) and both block ids are overridable
    off = P.local_foundation(slab(8, 8), (100, 70, -50), lambda x, z: 68,
                             wall_block="minecraft:deepslate_bricks", pillar_block="minecraft:oak_log")
    offc = columns(off)
    want = {(lx, lz) for lx in range(8) for lz in range(8)
            if lx in (0, 7) or lz in (0, 7) or (lx % 4 == 0 and lz % 4 == 0)}
    check("foundation: origin offset used (edges + 4-grid only)", set(offc) == want, f"{len(offc)} vs {len(want)}")
    check("foundation: custom wall/pillar blocks",
          all(b[3] == "minecraft:deepslate_bricks" for b in off if (b[0], b[2]) != (4, 4))
          and all(b[3] == "minecraft:oak_log" for b in off if (b[0], b[2]) == (4, 4))
          and {b[3] for b in off} == {"minecraft:deepslate_bricks", "minecraft:oak_log"}, {b[3] for b in off})
    check("foundation: local y relative to origin", all(b[1] == -1 for b in off), {b[1] for b in off})


def main():
    test_proportions()
    test_local_foundation()
    print()
    print("FAILED" if check.failed else "ALL OK", check.failed)
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
