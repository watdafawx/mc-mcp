"""Offline tests for palette.py: python test_palette.py   (no Minecraft, no network; ~1 s)."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import palette as P  # noqa: E402

STONE = "minecraft:stone_bricks"
GLASS = "minecraft:glass"
STAIRS = "minecraft:stone_brick_stairs[facing=south,half=top]"
STAIRS_PROPS = "[facing=south,half=top]"
BLOCKLIB = Path(P.__file__).resolve().parent / "knowledge" / "blocklib.json"


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


def wall_box(mode="walls", state=STONE, lo=(0, 0, 0), hi=(14, 11, 10)):
    return list(lo) + list(hi) + [state, mode]


def wall_args(gid="test/wall", blocks=None):
    return {"id": gid, "boxes": [wall_box()], "blocks": list(blocks or [])}


def wall_surface(lo=(0, 0, 0), hi=(14, 11, 10)):
    """The cells a "walls" box owns on its outer x/z faces: 15 x 12 x 11 -> 576 cells."""
    x1, y1, z1 = lo
    x2, y2, z2 = hi
    return {(x, y, z) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1) for z in range(z1, z2 + 1)
            if x in (x1, x2) or z in (z1, z2)}


def cells(entries):
    return {(e[0], e[1], e[2]) for e in entries}


# -------------------------------------------------------------------------------------------------------- 1. RAMPS

def test_ramps_in_blocklib():
    if not BLOCKLIB.exists():
        print("note: {} missing -> skipping the RAMPS/blocklib cross-check".format(BLOCKLIB))
        return
    lib = P._lib()
    check("ramps: blocklib loaded", bool(lib), f"{len(lib)} ids")
    bad = sorted({m for base, members in P.RAMPS.items() for m in [base] + [mm for mm, _ in members]
                  if m not in lib})
    check("ramps: every key + member exists in blocklib", not bad, bad[:8])
    check("ramps: every key is its own base ramp", all(base in P._build()["ramp"] or not lib
                                                      for base in P.RAMPS), sorted(set(P.RAMPS) - set(P._build()["ramp"])))
    check("ramps: weights are positive ints", all(isinstance(w, int) and w > 0
                                                 for ms in P.RAMPS.values() for _, w in ms))
    check("ramps: every base carries the biggest weight",
          all(max(ms, key=lambda mw: mw[1])[0] == base for base, ms in P.RAMPS.items()))


# ---------------------------------------------------------------------------------------------------- 2. determinism

def test_determinism():
    a = wall_args()
    first, n1 = P.texture(a)
    second, n2 = P.texture(a)
    check("determinism: same id + args -> identical output", first["blocks"] == second["blocks"] and n1 == n2,
          f"{len(first['blocks'])} blocks / {n1} changed")
    check("determinism: retexturing does not mutate the input", a["blocks"] == [] and len(a["boxes"]) == 1)

    other, _ = P.texture(wall_args(gid="test/other"))
    check("determinism: a different ghost id gives a different output", other["blocks"] != first["blocks"],
          f"{sum(1 for x, y in zip(first['blocks'], other['blocks']) if x[3] != y[3])} cells differ")


# --------------------------------------------------------------------------------------------- 3. base dominance

def test_base_dominates():
    surf = wall_surface()
    check("base: walls box owns 576 surface cells", len(surf) == 576, len(surf))
    out, n = P.texture(wall_args())
    ov = out["blocks"]
    ov_cells = cells(ov)
    shaded = ov_cells & surf
    base = surf - shaded
    check("base: overlay only touches surface cells", ov_cells <= surf, sorted(ov_cells - surf)[:4])
    check("base: stone_bricks keeps >= 55% of the surface", len(base) >= 0.55 * len(surf),
          f"{len(base)}/{len(surf)} = {len(base) / len(surf):.1%}")
    check("base: >= 15% of the surface is shaded", len(shaded) >= 0.15 * len(surf),
          f"{len(shaded)}/{len(surf)} = {len(shaded) / len(surf):.1%}")
    check("base: reported count matches the overlay", n == len(ov), f"{n} vs {len(ov)}")
    check("base: shaded cells are same-family blocks, never air",
          all(b[3].startswith("minecraft:") or b[3].startswith("create:") or b[3].startswith("ae2:")
              for b in ov), sorted({b[3] for b in ov}))


# ----------------------------------------------------------------------------------------------------- 4. gradient

def test_gradient():
    out, _ = P.texture(wall_args())
    ov = out["blocks"]
    bottom = [P._lum(b[3]) for b in ov if b[1] == 0]
    top = [P._lum(b[3]) for b in ov if b[1] == 11]
    check("gradient: bottom and top rows both got shaded", bool(bottom) and bool(top),
          f"{len(bottom)} bottom / {len(top)} top")
    if bottom and top:
        mb, mt = sum(bottom) / len(bottom), sum(top) / len(top)
        check("gradient: bottom row is darker than the top row", mb < mt, f"{mb:.1f} vs {mt:.1f}")


# ------------------------------------------------------------------------------------------------- 5. ownership

def test_box_ownership():
    args = wall_args(blocks=[[1, 1, 1, STONE]])
    args["boxes"].append([4, 2, 0, 6, 5, 0, GLASS])
    out, n = P.texture(args)
    cut = {(x, y, 0) for x in range(4, 7) for y in range(2, 6)}
    inside = [b for b in out["blocks"] if (b[0], b[1], b[2]) in cut]
    check("ownership: the later glass box takes its cells", not inside, inside[:4])
    check("ownership: the rest of the wall is still textured",
          n > 0 and any((b[0], b[1], b[2]) not in cut for b in out["blocks"]), f"{n} changed")
    check("ownership: glass itself is never retextured", all(b[3] != GLASS for b in out["blocks"]),
          sorted({b[3] for b in out["blocks"]}))


# ------------------------------------------------------------------------------------------------ 6. explicit wins

def test_explicit_blocks_win():
    orig = [[1, 1, 1, STONE], [2, 0, 2, "minecraft:cobblestone"], [3, 11, 3, "ae2:controller"]]
    args = wall_args(blocks=orig)
    out, n = P.texture(args)
    allb = out["blocks"]
    ov_len = len(allb) - len(orig)
    ov, tail = allb[:ov_len], allb[ov_len:]
    check("explicit: overlay comes first, the call's blocks last", ov_len > 0, f"{ov_len} overlay + {len(tail)} own")
    check("explicit: the tail is the original list, in order",
          [(b[0], b[1], b[2]) for b in tail] == [(b[0], b[1], b[2]) for b in orig],
          [(b[0], b[1], b[2]) for b in tail])
    check("explicit: an unramped own block is untouched", tail[2][3] == "ae2:controller", tail[2])
    check("explicit: the overlay prefix is real overlay, not a copy of the own blocks",
          all(b[3] != GLASS for b in ov) and len(cells(ov) - wall_surface()) == 0)


# ----------------------------------------------------------------------------------------------------- 7. stairs

def test_stairs():
    coords = [(x, y, z) for x in (0, 5, 10, 14) for y in (0, 3, 6, 11) for z in (0, 10)]
    args = {"id": "test/stairs", "boxes": [], "blocks": [[x, y, z, STAIRS] for x, y, z in coords]}
    out, n = P.texture(args)
    got = out["blocks"]
    check("stairs: one output block per input block", len(got) == len(coords), f"{len(got)} vs {len(coords)}")
    check("stairs: coords are kept", [(b[0], b[1], b[2]) for b in got] == coords)
    bad_props = [b[3] for b in got if not b[3].endswith(STAIRS_PROPS)]
    check("stairs: facing/half properties survive", not bad_props, bad_props[:3])
    bad_kind = [b[3] for b in got if not b[3].split("[")[0].endswith("_stairs") or "_slab" in b[3]]
    check("stairs: still a stairs block", not bad_kind, bad_kind[:3])
    lib = P._lib()
    missing = sorted({b[3].split("[")[0] for b in got if lib and b[3].split("[")[0] not in lib})
    check("stairs: every returned id exists in blocklib", not missing, missing[:5])
    check("stairs: at least one stair got a shaded family member", n > 0,
          sorted({b[3].split("[")[0] for b in got}))
    # a plain stair with no family stays as it is
    lone = P.retexture("minecraft:oak_stairs[facing=north]", 0, 0, 0, 0.5, 1)
    check("stairs: a stair with no ramp family is untouched", lone == "minecraft:oak_stairs[facing=north]", lone)


# ----------------------------------------------------------------------------------------------- 8. palette keys

def test_palette_keys():
    args = {"id": "test/palette", "boxes": [wall_box(mode="fill", lo=(0, 0, 0), hi=(5, 5, 5), state="w")],
            "blocks": [], "palette": {"w": "minecraft:deepslate_bricks"}}
    out, n = P.texture(args)
    got = out["blocks"]
    check("palette: a keyed box gets textured", n > 0 and got is not args["blocks"], f"{n} changed")
    check("palette: the composed key is resolved through the palette, never kept",
          all(b[3] != "w" for b in got), sorted({b[3] for b in got})[:4])
    lib = P._lib()
    ids = {b[3].split("[")[0] for b in got}
    check("palette: members come from the deepslate_bricks ramp",
          ids <= {m for m, _ in P.RAMPS["minecraft:deepslate_bricks"]} and ids, sorted(ids))
    check("palette: unknown palette keys resolve to themselves (no ramp -> untouched)",
          P.texture({"id": "x", "boxes": [], "blocks": [[0, 0, 0, "z"]], "palette": {}})[1] == 0)


# --------------------------------------------------------------------------------------------------- 9. untouched

def test_untouched():
    args = {"id": "test/untouched",
            "boxes": [[0, 0, 0, 3, 3, 3, GLASS], [0, 0, 0, 3, 3, 3, "ae2:controller"]],
            "blocks": [[0, 0, 0, GLASS], [1, 0, 0, "ae2:controller"], [2, 0, 0, "minecraft:air"]]}
    out, n = P.texture(args)
    check("untouched: no ramp -> (args, 0)", out is args and n == 0, n)
    check("untouched: blocks come back unchanged", out["blocks"] == args["blocks"], out["blocks"])
    for state in (GLASS, "ae2:controller", "minecraft:air", "create:zinc_block"):
        check(f"untouched: has_ramp({state}) is False", not P.has_ramp(state))
    check("untouched: has_ramp(stone_bricks) is True", P.has_ramp(STONE))
    for empty in ({}, {"id": "e"}, {"boxes": [], "blocks": []}, {"id": "e", "boxes": "nope", "blocks": None}):
        got, n = P.texture(empty)
        check(f"untouched: nothing to texture -> (args, 0) {sorted(empty)}", got is empty and n == 0)
    check("untouched: retexture of an unramped state is identity",
          P.retexture(GLASS, 3, 4, 5, 0.5, 7) == GLASS and P.retexture("ae2:controller", 0, 0, 0, 0, 1) == "ae2:controller")


# ------------------------------------------------------------------------------------------------------- 10. env

def test_env_off():
    before = os.environ.get("ARCHITECT_TEXTURE")
    args = wall_args()
    try:
        os.environ["ARCHITECT_TEXTURE"] = "0"
        out, n = P.texture(args)
        check("env: ARCHITECT_TEXTURE=0 -> (args, 0)", out is args and n == 0, n)
    finally:
        if before is None:
            os.environ.pop("ARCHITECT_TEXTURE", None)
        else:
            os.environ["ARCHITECT_TEXTURE"] = before
    check("env: the variable is restored", os.environ.get("ARCHITECT_TEXTURE") == before,
          os.environ.get("ARCHITECT_TEXTURE"))
    out, n = P.texture(args)
    check("env: texture is back on after the restore", n > 0, n)


# -------------------------------------------------------------------------------------------------- 11. size cap

def test_size_cap():
    cap = P.MAX_SIM
    side = int(round(cap ** (1 / 3))) + 2  # a fill box just past the cap
    args = {"id": "test/huge", "boxes": [wall_box(mode="fill", lo=(0, 0, 0), hi=(side, side, side))], "blocks": []}
    t0 = time.time()
    out, n = P.texture(args)
    dt = time.time() - t0
    check("size: a box over MAX_SIM is not simulated", out is args and n == 0, f"{n} changed, {dt:.3f}s")
    check("size: it returns fast (< 1 s)", dt < 1.0, f"{dt:.3f}s")
    check("size: MAX_SIM is a sane positive cap", isinstance(cap, int) and 0 < cap < 10_000_000, cap)
    # exactly at the cap is still simulated, one cell past is not: the wall box below stays textured
    small = wall_args()
    check("size: a normal call still textures", P.texture(small)[1] > 0)


def main():
    test_ramps_in_blocklib()
    test_determinism()
    test_base_dominates()
    test_gradient()
    test_box_ownership()
    test_explicit_blocks_win()
    test_stairs()
    test_palette_keys()
    test_untouched()
    test_env_off()
    test_size_cap()
    print()
    print("FAILED" if check.failed else "ALL OK", check.failed)
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
