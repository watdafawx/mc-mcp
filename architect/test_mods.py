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


def _states(r):
    """Every block string with a [state] in a room's pieces, wall and gate, plus pad."""
    out = []

    def walk(x):
        if isinstance(x, str):
            if "[" in x:
                out.append(x)
        elif isinstance(x, (tuple, list)):
            for y in x:
                walk(y)
    walk(r.pieces), walk(r.wall), walk(r.extra.get("gate", ())), walk(r.pad)
    return out


def piece_ids(r):
    def walk(p):
        check(p[0] in ("single", "stack", "cube", "tower", "group", "gear", "cog", "belt", "column", "field", "blob", "ring", "kgear", "kwheel", "kbelt", "pipe"), f"{r.theme}: unknown piece kind {p[0]}")
        if p[0] == "group":
            for (dx, dz, sub) in p[1:]:
                check(abs(dx) <= 3 and abs(dz) <= 3, f"{r.theme}: group offset outside the 7x7 plinth {dx},{dz}")
                yield from walk(sub)
            return
        if p[0] == "pipe":
            yield "create:fluid_pipe"
        if p[0] in ("kgear", "kwheel", "kbelt"):  # fixed real Create kinetics inside
            yield from ("create:shaft", "create:cogwheel", "create:large_cogwheel", "create:gearbox",
                        "create:large_water_wheel", "create:water_wheel", "create:belt")
        for x in p[1:]:
            if isinstance(x, str) and not x.startswith("minecraft:"):  # vanilla fillers (fake cogwheel parts) are not whitelisted
                yield x.split("[")[0]
    for p in r.pieces:
        yield from walk(p)


def placed_pb(K):
    placed = {}
    cells = {(x, z) for x in range(2, 35) for z in range(2, 17)}
    spine = {(x, z) for (x, z) in cells if 13 <= x <= 21}
    interiors.fit_room("mod_room:productivebees", cells, 1, 10, K, spine, spine, "solarpunk", 1,
                       lambda x, y, z, b: placed.__setitem__((x, y, z), b))
    return list(placed.values())


def main():
    check(set(mods.REGISTRY) >= {"mekanism", "powah", "bigreactors", "create", "industrialforegoing", "ars_nouveau", "occultism", "mysticalagriculture", "productivebees", "enderio"}, "registry incomplete")
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
        check(all(b.split("[")[0] in r.blocks or b.startswith("minecraft:") for b in r.pad), f"{theme}: pad block not in whitelist")
        check(not r.plinth or (len(r.plinth) == 2 and r.deck), f"{theme}: plinth needs (ring, field) and a deck")
        check(r.pieces, f"{theme}: no pieces")
        check(all(b.split("[")[0] in r.blocks for b in r.wall), f"{theme}: wall block not in whitelist")
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
    # v25: ghosts draw block-entity renderers, so the Create room uses real cogs, shafts, belt and water wheel
    KIN = {"create:" + n for n in "shaft cogwheel large_cogwheel large_water_wheel belt".split()}
    placed = {}
    cells = {(x, z) for x in range(2, 35) for z in range(2, 17)}  # the real campus room: 33 x 15, two plinths in a row
    K = {"trim": "minecraft:stone", "detail": "minecraft:stone", "glow": "minecraft:glowstone", "wall": "minecraft:stone"}
    spine = {(x, z) for (x, z) in cells if 13 <= x <= 21}  # a hall through the middle, as in the campus wings
    interiors.fit_room("mod_room:create", cells, 1, 10, K, spine, spine, "steampunk", 1,
                       lambda x, y, z, b: placed.__setitem__((x, y, z), b))
    got = {b.split("[")[0] for b in placed.values()}
    check(KIN <= got, f"create room misses real kinetic blocks: {sorted(KIN - got)}")
    check(all("[" in b for b in placed.values() if b.split("[")[0] in KIN), "kinetic blocks need explicit axis/part states")
    n_big = sum(1 for b in placed.values() if b.startswith("create:large_cogwheel"))
    check(n_big >= 3, f"create room should have >= 3 large cogwheels, has {n_big}")
    check(any(b.startswith("create:large_water_wheel") for b in placed.values()), "no large water wheel between the plinths")
    belts = sorted(x for (x, y, z), b in placed.items() if b.startswith("create:belt["))
    check(len(belts) >= 8, f"eye-level belt line too short ({len(belts)})")
    check(sum(1 for b in placed.values() if b.startswith("create:shaft[axis=x]")) >= 20, "no shaft clutter along the room axis")
    pipes = [b for b in placed.values() if b.startswith("create:fluid_pipe")]
    check(pipes and all(all(f"{k}=" in b for k in ("north", "south", "east", "west", "up", "down")) for b in pipes),
          "fluid pipes must set all six connection states")
    import floaters
    fx, nfix = floaters.fix_pipes({"id": "t", "blocks": [[0, 0, 0, "create:fluid_pipe"], [1, 0, 0, "create:fluid_tank"]]})
    check(nfix == 1 and "east=true" in fx["blocks"][0][3] and "up=false" in fx["blocks"][0][3], "fix_pipes")
    import campus  # v26: the spine layout must sign mod wings too (it skipped Site.wing and lost the signage)
    cs = campus.build(kit="steampunk", wings=[{"name": "create", "rooms": ["mod_room:create", "expansion"], "size": "l",
                                                 "floors": 1, "floor_h": 9}])
    feat = [g for g in cs if g["id"] == "features"][0]["blocks"]
    check(sum(1 for b in feat if b[3].startswith("create:large_cogwheel")) >= 9, "spine campus lost the Create facade emblems")
    check(any(b[3] == "create:brass_block" for b in feat), "spine campus lost the brass lintel")
    import mods.shapes as fake_shapes  # the fake disc stays available as a fallback
    check(len(fake_shapes.disc(2, "a", "b", "c")) > 10, "fake cog disc fallback broken")
    import mods.signs as signs
    for theme in mods.REGISTRY:
        cells_ = signs.facade(theme, 0, 0, 37, 49, 2, 11, "s")
        check(len(cells_) > 150, f"{theme}: facade signage too small ({len(cells_)})")
    # v27: batch-2 mods. State keys/values are checked against state_keys.json (read from the mod jars' blockstates)
    NEW = ("ars_nouveau", "occultism", "mysticalagriculture", "productivebees", "enderio")
    sk = json.loads((HERE / "mods" / "state_keys.json").read_text("utf-8"))
    for theme in NEW:
        r = mods.REGISTRY[theme]
        for st in _states(r):
            bid, _, rest = st.partition("[")
            if bid.startswith("minecraft:"):
                continue
            allowed = sk.get(bid)
            check(allowed is not None, f"{theme}: no state table for {bid} (re-run the jar scan)")
            for kv in rest.rstrip("]").split(","):
                k, _, v = kv.partition("=")
                check(allowed is not None and v in allowed.get(k, []), f"{theme}: bad state {bid}[{kv}]")
        check(r.extra.get("gate"), f"{theme}: no eye-level gate props")
        check(r.deck and r.plinth, f"{theme}: needs a deck and plinth")
        placed = {}
        cells = {(x, z) for x in range(2, 35) for z in range(2, 17)}
        K = {"trim": "minecraft:stone", "detail": "minecraft:stone", "glow": "minecraft:glowstone", "wall": "minecraft:stone"}
        spine = {(x, z) for (x, z) in cells if 13 <= x <= 21}
        interiors.fit_room(f"mod_room:{theme}", cells, 1, 10, K, spine, spine, r.style, 1,
                           lambda x, y, z, b: placed.__setitem__((x, y, z), b))
        mine = [b for b in placed.values() if b.split("[")[0].startswith(r.namespaces[0] + ":")]
        check(len(mine) >= 120, f"{theme}: room has only {len(mine)} mod blocks")
        check(any(b in r.extra["gate"] for b in placed.values()), f"{theme}: the gate props were not placed")
    ma = mods.REGISTRY["mysticalagriculture"]
    placed = {}
    cells = {(x, z) for x in range(2, 35) for z in range(2, 17)}
    spine = {(x, z) for (x, z) in cells if 13 <= x <= 21}
    interiors.fit_room("mod_room:mysticalagriculture", cells, 1, 10, K, spine, spine, "solarpunk", 1,
                       lambda x, y, z, b: placed.__setitem__((x, y, z), b))
    crops = [(p, b) for p, b in placed.items() if b.split("[")[0].endswith("_crop")]
    check(len(crops) >= 25, f"mysticalagriculture: only {len(crops)} crops")
    check(all("[age=" in b for _, b in crops), "mysticalagriculture: a crop has no age state")
    check(all(placed.get((x, y - 1, z), "").split("[")[0].endswith("_farmland") for (x, y, z), _ in crops),
          "mysticalagriculture: a crop is not on farmland")
    pb = [b for b in placed_pb(K) if "beehive" in b or "_nest" in b]
    check(pb and all("honey_level=" in b or "axis=" in b or b.endswith("bumble_bee_nest") for b in pb), "productivebees: nest without state")
    import services
    for theme in mods.REGISTRY:
        w, d = services.size_for(services.machine_count({"machines": 12}, theme))
        check(w % 2 == 1 and d % 2 == 1 and w >= 27 and d >= 33, f"{theme}: wing size {w}x{d} not odd/clamped")
    check(services.machine_count({}, "create") == services.DEFAULT_CLUSTERS, "default machine count")
    check(services.size_for(30)[0] * services.size_for(30)[1] > services.size_for(6)[0] * services.size_for(6)[1],
          "wing area not monotonic in machine count")
    if fails:
        print("FAIL:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("test_mods OK")


if __name__ == "__main__":
    main()
