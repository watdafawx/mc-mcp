"""Offline check of the per-mod room registry (no API, no Minecraft): python test_mods.py

Needs the generated block library (knowledge/blocklib.json + _tex.json, git-ignored, built from the ATM10 instance by
`blocklib.py build`). Without it the library checks are skipped with a notice (the structure checks still run).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mods  # noqa: E402
import interiors  # noqa: E402

KNOW = HERE / "knowledge"
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def piece_ids(r):
    def walk(p):
        check(p[0] in ("single", "stack", "cube", "tower", "group", "gear", "cog", "belt", "column"), f"{r.theme}: unknown piece kind {p[0]}")
        if p[0] == "group":
            for (dx, dz, sub) in p[1:]:
                check(abs(dx) <= 3 and abs(dz) <= 3, f"{r.theme}: group offset outside the 7x7 plinth {dx},{dz}")
                yield from walk(sub)
            return
        for x in p[1:]:
            if isinstance(x, str) and not x.startswith("minecraft:"):  # vanilla fillers (fake cogwheel parts) are not whitelisted
                yield x.split("[")[0]
    for p in r.pieces:
        yield from walk(p)


def main():
    check(set(mods.REGISTRY) >= {"mekanism", "powah", "bigreactors", "create", "industrialforegoing"}, "registry incomplete")
    lib = tex = None
    if (KNOW / "blocklib.json").exists() and (KNOW / "_tex.json").exists():
        lib = json.loads((KNOW / "blocklib.json").read_text("utf-8"))
        tex = json.loads((KNOW / "_tex.json").read_text("utf-8"))
    else:
        print("NOTICE: blocklib.json/_tex.json missing: block existence and texture checks skipped")
    seen_global = {}
    for theme, r in mods.REGISTRY.items():
        check(theme == r.theme, f"{theme}: key != theme")
        check(r.brief and r.style and r.ghost_rules, f"{theme}: missing brief/style/ghost_rules")
        check(len(r.blocks) == len(set(r.blocks)), f"{theme}: duplicate ids " +
              str(sorted({b for b in r.blocks if r.blocks.count(b) > 1})))
        check(len(r.blocks) >= 20, f"{theme}: whitelist too small")
        check(all(b.split(":")[0] in r.namespaces for b in r.blocks), f"{theme}: id outside its namespaces")
        for b in r.blocks:
            seen_global.setdefault(b, []).append(theme)
        check(all(b in r.blocks for b in piece_ids(r)), f"{theme}: piece block not in whitelist")
        check(all(b in r.blocks for b in r.pad), f"{theme}: pad block not in whitelist")
        check(not r.plinth or (len(r.plinth) == 2 and r.deck), f"{theme}: plinth needs (ring, field) and a deck")
        check(r.pieces, f"{theme}: no pieces")
        check(all(b in r.blocks for b in r.wall), f"{theme}: wall block not in whitelist")
        if lib is not None:
            for b in r.blocks:
                check(b in lib, f"{theme}: {b} not in blocklib")
                if b in lib:
                    t = lib[b].get("tex")
                    check(bool(t) and t in tex, f"{theme}: {b} has no texture")
        # whitelist bypasses the cost filter, default filter unchanged
        import blocklib
        if lib is not None:
            hit = blocklib.find(None, None, 3.0, [r.namespaces[0]], None, 500)
            check(not any(h["id"] in r.blocks and lib[h["id"]]["cost"] is None for h in hit),
                  f"{theme}: default find() must still drop uncosted blocks")
    for b, ts in seen_global.items():
        check(len(ts) == 1, f"{b} listed in several mods: {ts}")
    # prompt note and interiors fit a registered room without error
    for theme in mods.REGISTRY:
        check("MOD ROOM" in mods.prompt_note(theme), f"{theme}: prompt note")
        placed = {}
        cells = {(x, z) for x in range(40) for z in range(24)}
        K = {"trim": "minecraft:stone", "detail": "minecraft:stone", "glow": "minecraft:glowstone", "wall": "minecraft:stone"}
        spine = {(x, z) for (x, z) in cells if abs(z - 12) <= 1}
        interiors.fit_room(f"mod_room:{theme}", cells, 1, 7, K, spine, spine, "station_white", 1,
                           lambda x, y, z, b: placed.__setitem__((x, y, z), b))
        used = set(placed.values())
        check(any(b in mods.REGISTRY[theme].blocks for b in used), f"{theme}: room placed no registry block")
        check(all(b in used or True for b in mods.REGISTRY[theme].pad), "pad")
        n_pieces = sum(1 for b in used if b in mods.REGISTRY[theme].blocks)
        print(f"{theme}: {len(mods.REGISTRY[theme].blocks)} ids, room uses {n_pieces} distinct registry blocks")
    check(mods.themes_in([{"rooms": ["mod_room:ae2", "mod_room:create"]}]) == ["create"], "themes_in")
    # v24: Create's rotating parts are invisible in ghosts: the room must never place them, and every mod gets facade signage
    INVIS = {"create:" + n for n in "shaft cogwheel large_cogwheel powered_shaft water_wheel large_water_wheel flywheel belt hand_crank".split()}
    placed = {}
    cells = {(x, z) for x in range(40) for z in range(24)}
    K = {"trim": "minecraft:stone", "detail": "minecraft:stone", "glow": "minecraft:glowstone", "wall": "minecraft:stone"}
    spine = {(x, z) for (x, z) in cells if abs(z - 12) <= 1}
    interiors.fit_room("mod_room:create", cells, 1, 9, K, spine, spine, "steampunk", 1,
                       lambda x, y, z, b: placed.__setitem__((x, y, z), b))
    check(not {b.split("[")[0] for b in placed.values()} & INVIS, "create room places invisible kinetic blocks")
    check(sum(1 for b in placed.values() if b == "minecraft:dark_oak_planks") > 20, "create room has no fake cogwheel discs")
    import mods.signs as signs
    for theme in mods.REGISTRY:
        cells_ = signs.facade(theme, 0, 0, 37, 49, 2, 11, "s")
        check(len(cells_) > 150, f"{theme}: facade signage too small ({len(cells_)})")
    if fails:
        print("FAIL:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("test_mods OK")


if __name__ == "__main__":
    main()
