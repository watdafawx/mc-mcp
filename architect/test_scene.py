"""Offline tests for kits.json, palettes.py and scene.py: python test_scene.py   (no Minecraft, no API; ~2 s).

Covers: every kit resolves with an ATM10-like registry (preferred blocks) and with vanilla only (every block
minecraft:, and a real 1.21.1 id); kits.json element 0 == massing.KITS (the consolidation changed nothing);
overrides, state suffixes and registry formats; Scene round trip; apply_patch (add, resize, swap kit, remove,
pin, atomic failure); anchor attachment (roof_deck, wall:north, floor, pad, door, nested, inside, align) with
cycle / missing-target / bad-surface errors; compiling every node kind into ghost specs with no floating nodes;
diff, compact ghost_set args, describe().

Prints "ok"/"FAIL" per check and exits non-zero on any failure.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import scene  # noqa: E402  (imports shapes before massing)
import massing  # noqa: E402
import interiors  # noqa: E402
import palettes  # noqa: E402
from scene import Scene, SceneError  # noqa: E402

failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  " + str(extra)))
    if not cond:
        failed += 1


def raises(name, fn, *needles):
    try:
        fn()
    except (SceneError, palettes.PaletteError) as e:
        msg = str(e)
        check(name, all(n in msg for n in needles), f"message {msg!r} lacks {needles}")
        return msg
    except Exception as e:  # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")
    else:
        check(name, False, "did not raise")


DATA = palettes.load_kits()
KITS = palettes.list_kits()
VANILLA = palettes.vanilla_blocks()


def all_chains(kit):
    info = palettes.kit_info(kit)
    yield from info["roles"].items()
    for i, c in enumerate(info["meta"].get("roof_mats", [])):
        yield f"roof_mats[{i}]", c
    yield from ((f"wing_roles.{r}", c) for r, c in info["meta"].get("wing_roles", {}).items())


ATM10 = set(VANILLA)
for k in KITS:
    for _, c in all_chains(k):
        ATM10.update(palettes.base_id(b) for b in c)

# ------------------------------------------------------------------------------------------ kits.json

print("== kits.json")
check("kits.json validates", palettes.validate(DATA) == [], palettes.validate(DATA))
check("all massing kits present", set(massing.KITS) <= set(KITS), set(massing.KITS) - set(KITS))
for k in KITS:
    bad = [(r, c) for r, c in all_chains(k) if not palettes.base_id(c[-1]).startswith("minecraft:")]
    check(f"{k}: every chain ends vanilla", not bad, bad)
    unreal = [b for _, c in all_chains(k) for b in c
              if palettes.base_id(b).startswith("minecraft:") and palettes.base_id(b) not in VANILLA]
    check(f"{k}: vanilla ids exist in 1.21.1", not unreal, unreal)
    missing = [r for r in DATA["required"] if r not in palettes.kit_info(k)["roles"]]
    check(f"{k}: required roles", not missing, missing)
    if k in massing.KITS:  # consolidation: preferred blocks are exactly what massing builds with today
        pref = palettes.resolve_kit(k)
        check(f"{k}: preferred == massing.KITS", pref == massing.KITS[k],
              {r: (pref.get(r), massing.KITS[k].get(r)) for r in set(pref) | set(massing.KITS[k])
               if pref.get(r) != massing.KITS[k].get(r)})
    meta = palettes.kit_info(k)["meta"]
    check(f"{k}: roof_default matches massing", meta.get("roof_default", "flat") == massing.ROOF_DEFAULT.get(k, "flat"))
    check(f"{k}: wood/colour match interiors", meta.get("wood") == interiors.WOOD.get(k)
          and meta.get("colour") == interiors.COLOUR.get(k), (meta.get("wood"), meta.get("colour")))

try:  # campus tables (v15/v16): compare where campus still defines them (another refactor may move them)
    import campus
except Exception as e:  # noqa: BLE001
    campus = None
    print(f"skip campus table checks: {e}")
if campus is not None:
    for k in KITS:
        meta = palettes.kit_info(k)["meta"]
        for attr, key in (("ROOF_CYCLE", "roof_cycle"), ("TOWER_ROOF", "tower_roof"), ("ALT_ROOF", "alt_roof"),
                          ("HUB_ROOF", "hub_roof")):
            table = getattr(campus, attr, None)
            if isinstance(table, dict) and k in table:
                check(f"{k}: meta.{key} == campus.{attr}", meta.get(key) == table[k], (meta.get(key), table[k]))
        mats = getattr(campus, "ROOF_MATS", {}).get(k)
        if mats:
            check(f"{k}: meta.roof_mats preferred == campus.ROOF_MATS", palettes.resolve_list(meta["roof_mats"]) == mats)
        glass = getattr(campus, "GLASS", {}).get(k)
        if glass:
            check(f"{k}: meta.glass_cycle == campus.GLASS", meta["glass_cycle"] ==
                  [f"minecraft:{g}_stained_glass" for g in glass])

# ------------------------------------------------------------------------------------------ palettes

print("== palettes")
for k in KITS:
    atm = palettes.resolve_report(k, ATM10)
    check(f"{k}: ATM10-like set -> every role first choice", all(v["index"] == 0 and v["found"] for v in atm.values()),
          palettes.fallbacks(atm))
    van = palettes.resolve_kit(k, "vanilla")
    check(f"{k}: vanilla-only -> every block minecraft:", all(b.startswith("minecraft:") for b in van.values()), van)
    check(f"{k}: vanilla-only -> every block real", all(palettes.base_id(b) in VANILLA for b in van.values()))
    rm = palettes.resolve_meta(k, "vanilla")
    check(f"{k}: vanilla meta tables minecraft:",
          all(b.startswith("minecraft:") for b in rm.get("roof_mats", []) + list(rm.get("wing_roles", {}).values())))
    check(f"{k}: same roles with or without registry", set(van) == set(palettes.resolve_kit(k)))

sp = palettes.resolve_kit("solarpunk", "vanilla")
check("state suffix kept on vanilla pick", sp["detail"] == "minecraft:oak_leaves[persistent=true]", sp["detail"])
check("mod block falls back (solarpunk wall)", sp["wall"] == "minecraft:calcite", sp["wall"])
check("station tip state kept", palettes.resolve_kit("station_white", "vanilla")["tip"] == "minecraft:redstone_lamp[lit=true]")
over = palettes.resolve_report("hextech", ["minecraft:stone"],
                               {"glass": "ae2:quartz_glass", "trim": ["create:x", "stone"], "new_role": "minecraft:oak_log[axis=x]"})
check("override missing in pack -> kit chain", over["glass"]["block"] == "minecraft:purple_stained_glass"
      and over["glass"]["source"] == "kit", over["glass"])
check("override chain picks available (bare id normalized)", over["trim"]["block"] == "minecraft:stone"
      and over["trim"]["source"] == "override", over["trim"])
check("override adds a role, state kept", over["new_role"]["block"] == "minecraft:oak_log[axis=x]")
check("override honoured without registry", palettes.resolve_kit("gothic", None, {"glass": "ae2:quartz_glass"})["glass"]
      == "ae2:quartz_glass")
check("None override ignored", palettes.resolve_kit("gothic", None, {"glass": None})["glass"]
      == massing.KITS["gothic"]["glass"])
reg = {"matched": 2, "blocks": ["ae2:quartz_glass", "minecraft:white_concrete"]}
check("registry_blocks dict accepted", palettes.resolve_kit("ae_sky", reg)["glass"] == "ae2:quartz_glass")
check("dict ids accepted", palettes.resolve_kit("ae_sky", [{"id": "ae2:quartz_glass", "props": {}}])["glass"]
      == "ae2:quartz_glass")
check("nothing found -> last entry", palettes.pick(["a:b", "minecraft:glass"], []) == ("minecraft:glass", 1, False))
check("with_state merges", palettes.with_state("minecraft:oak_log[axis=y]", "axis=x,foo=1")
      == "minecraft:oak_log[axis=x,foo=1]")
check("base_id strips state + adds ns", palettes.base_id("oak_stairs[facing=east]") == "minecraft:oak_stairs")
raises("unknown kit raises", lambda: palettes.resolve_kit("nope"), "unknown kit", "station_white")
raises("bad override raises", lambda: palettes.resolve_kit("gothic", None, {"glass": []}), "override glass")
check("kit_info is a copy", palettes.kit_info("gothic")["roles"] is not DATA["kits"]["gothic"]["roles"])
check("list_kits sorted", KITS == sorted(KITS) and len(KITS) == 8, KITS)

# ------------------------------------------------------------------------------------------ scene fixtures

ROOFLESS = {"roof_details": 0, "antennas": 0}


def base_scene():
    return {"id": "demo", "origin": [100, 64, -40], "kit": "cyber_dark", "nodes": [
        {"id": "hub", "kind": "structure",
         "params": {"w": 21, "d": 15, "floors": 2, **ROOFLESS, "program": [["workshop", "storage", "lab"], "living"],
                    "entrances": ["s", "e"]}},
        {"id": "wing", "kind": "structure", "tag": "wing",
         "attach": {"target": "hub", "surface": "wall:east", "offset": [2, 0, 0]},
         "params": {"w": 13, "d": 11, "floors": 1, "floor_h": 6, **ROOFLESS}},
        {"id": "dish", "kind": "shape", "attach": "wing.roof_deck",
         "params": {"shape": "dome", "r": 3, "block": "$glass"}},
        {"id": "cpu", "kind": "multiblock", "attach": {"target": "hub", "surface": "pad[2]"},
         "params": {"kind": "crafting_cpu"}},
        {"id": "crate", "kind": "boxes", "attach": {"target": "hub", "surface": "wall:north", "align": "min"},
         "params": {"boxes": [[0, 0, 0, 2, 2, 2, "$detail"]]}},
    ]}


def A(res, nid, name):
    return res.ghost(nid)["anchors"][name]


def B(res, nid):
    return res.ghost(nid)["bounds"]


# ------------------------------------------------------------------------------------------ IR

print("== scene IR")
sc = Scene.from_dict(base_scene())
d1 = sc.to_dict()
check("to_dict is JSON", json.loads(json.dumps(d1)) == d1)
check("round trip from_dict(to_dict)", Scene.from_dict(d1).to_dict() == d1)
check("round trip via json", Scene.from_json(sc.to_json()).to_dict() == d1)
check("attach shorthand normalised", d1["nodes"][2]["attach"] == {"target": "wing", "surface": "roof_deck"},
      d1["nodes"][2]["attach"])
check("order: targets first", sc.order().index("wing") < sc.order().index("dish"))
check("dependents transitive", sc.dependents("hub") == ["wing", "dish", "cpu", "crate"], sc.dependents("hub"))
lift = Scene.from_dict({"nodes": [{"id": "a", "kind": "structure", "params": {"kit": "gothic", "roles": {"glass": "minecraft:glass"}}}]})
check("kit/roles lifted out of params", lift.nodes[0].kit == "gothic" and lift.nodes[0].roles == {"glass": "minecraft:glass"}
      and "kit" not in lift.nodes[0].params)
check("surface aliases", scene.canon_surface("wall:n") == "wall:north" and scene.canon_surface("pad:1") == "pad[1]"
      and scene.canon_surface("roof") == "roof_deck" and scene.canon_surface("door:e") == "door:east")
raises("unknown node key", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes", "parms": {}}]}),
       "parms", "params")
raises("unknown kind", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "structur"}]}), "structure")
raises("duplicate id", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes"}, {"id": "a", "kind": "boxes"}]}),
       "duplicate")
raises("at + attach", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes", "at": [0, 0, 0],
                                                            "attach": "b.top"}]}), "either at or attach")
raises("bad align", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes",
                                                         "attach": {"target": "b", "surface": "top", "align": "middle"}}]}),
       "align")
raises("unknown scene kit", lambda: Scene.from_dict({"kit": "gothik"}), "gothic")

# ------------------------------------------------------------------------------------------ compile + anchors

print("== compile + anchors")
res = sc.compile()
check("one ghost per node, scene order", [g["id"] for g in res.ghosts] == ["hub", "wing", "dish", "cpu", "crate"])
need = {"id", "ghost_id", "origin", "palette", "boxes", "blocks", "bounds", "anchors"}
check("ghost specs carry the fields", all(need <= set(g) for g in res.ghosts))
check("ghost ids prefixed by scene", res.ghost("dish")["ghost_id"] == "demo/dish")
check("no floating nodes", res.floating == [] and res.ok, res.floating)
check("no overlaps", res.overlaps == [], res.overlaps)
check("compile deterministic", sc.compile().hashes() == res.hashes())
hub = B(res, "hub")
check("root at scene origin", res.ghost("hub")["origin"] == [100, 64, -40] and hub["min"] == [100, 64, -40], hub)
names = set(res.ghost("hub")["anchors"])
for n in ("roof_deck", "floor", "interior", "wall:north", "wall:south", "wall:east", "wall:west", "center", "top",
          "ground", "floor[0]", "floor[1]", "door:south", "door:east", "pad[0]", "pad[1]", "pad[2]"):
    check(f"hub anchor {n}", n in names)
check("pad labels = program rooms", A(res, "hub", "pad[0]").get("label") == "workshop")
# wall:east + offset 2: wing starts 1 + 2 past the hub's east face, wing min y on the hub's base
check("wall:east attach x", B(res, "wing")["min"][0] == hub["max"][0] + 1 + 2, (B(res, "wing"), hub))
check("wall attach y = base (align_y min)", B(res, "wing")["min"][1] == hub["min"][1])
hz = (hub["min"][2] + hub["max"][2]) / 2
wz = (B(res, "wing")["min"][2] + B(res, "wing")["max"][2]) / 2
check("wall attach centred on z", abs(hz - wz) <= 0.5, (hz, wz))
# roof_deck: dome stands on the deck, centred on it
deck = A(res, "wing", "roof_deck")
db = B(res, "dish")
check("roof_deck attach y", db["min"][1] == deck["max"][1] + 1, (db, deck))
for i, ax in ((0, "x"), (2, "z")):
    check(f"roof_deck centred {ax}", abs((db["min"][i] + db["max"][i]) - (deck["min"][i] + deck["max"][i])) <= 1)
check("$glass substituted in shape", all(b[3].startswith("connectedglass:borderless_glass_cyan")
                                         for b in res.ghost("dish")["blocks"]))
# wall:north + align min: crate west edges line up, crate sits just north of the hub
cb = B(res, "crate")
check("wall:north attach z", cb["max"][2] == A(res, "hub", "wall:north")["min"][2] - 1, cb)
check("align min x", cb["min"][0] == hub["min"][0], cb)
# pad: cpu stands on the ground floor inside pad[2]
pad = A(res, "hub", "pad[2]")
pb = B(res, "cpu")
check("pad attach y", pb["min"][1] == pad["max"][1] + 1)
check("pad attach inside pad", all(pad["min"][i] <= pb["min"][i] and pb["max"][i] <= pad["max"][i] for i in (0, 2)),
      (pb, pad))
check("multiblock keeps palette keys", res.ghost("cpu")["palette"] and res.ghost("cpu")["blocks"][0][3] in
      res.ghost("cpu")["palette"])
# door anchor lines up with the doorway massing cut: the cells inside it are air in the compiled ghost
door = A(res, "hub", "door:south")
o = res.ghost("hub")["origin"]
hub_cells = {(b[0] + o[0], b[1] + o[1], b[2] + o[2]): b[3] for b in res.ghost("hub")["blocks"]}
door_cells = [(x, y, z) for x in range(door["min"][0], door["max"][0] + 1) for y in range(door["min"][1], door["max"][1] + 1)
              for z in range(door["min"][2], door["max"][2] + 1)]
check("door:south is the cut doorway", len(door_cells) == 18 and all(hub_cells.get(c) == "minecraft:air" for c in door_cells),
      [(c, hub_cells.get(c)) for c in door_cells if hub_cells.get(c) != "minecraft:air"])
check("door:south on the south face", door["max"][2] == hub["max"][2] and door["normal"] == [0, 0, 1])
wn = A(res, "hub", "wall:north")
check("wall anchor spans the wall thickness", wn["max"][2] - wn["min"][2] == 1, wn)

# floor anchor (generic interior attach) + nested chain + inside side
nest = Scene.from_dict({"kit": "cyber_dark", "nodes": [
    {"id": "hall", "kind": "structure", "params": {"w": 15, "d": 15, "floors": 1, "floor_h": 6, **ROOFLESS,
                                                  "entrances": []}},
    {"id": "tower", "kind": "boxes", "attach": {"target": "hall", "surface": "roof_deck", "align": {"x": "max", "z": "min"}},
     "params": {"boxes": [[0, 0, 0, 2, 5, 2, "$wall"]]}},
    {"id": "flag", "kind": "boxes", "attach": {"target": "tower", "surface": "top"},
     "params": {"blocks": [[0, 0, 0, "$tip"]]}},
    {"id": "statue", "kind": "boxes", "attach": {"target": "hall", "surface": "floor"},
     "params": {"boxes": [[0, 0, 0, 0, 2, 0, "$trim"]]}},
    {"id": "sign", "kind": "boxes", "attach": {"target": "hall", "surface": "wall:north", "side": "inside",
                                               "align_y": "max", "offset": [0, -2, 0]},
     "params": {"blocks": [[0, 0, 0, "$accent"]]}},
]})
rn = nest.compile()
check("nested: no floating", rn.floating == [], rn.floating)
tb, fb, hd = B(rn, "tower"), B(rn, "flag"), A(rn, "hall", "roof_deck")
check("nested: tower on deck, align max x / min z", tb["min"][1] == hd["max"][1] + 1 and tb["max"][0] == hd["max"][0]
      and tb["min"][2] == hd["min"][2], (tb, hd))
check("nested: flag on tower top centre", fb["min"][1] == tb["max"][1] + 1 and fb["min"][0] == tb["min"][0] + 1
      and fb["min"][2] == tb["min"][2] + 1, (fb, tb))
fl, stb = A(rn, "hall", "floor"), B(rn, "statue")
check("floor attach: stands on the floor", stb["min"][1] == fl["max"][1] + 1, (stb, fl))
check("floor attach: inside the interior", all(fl["min"][i] <= stb["min"][i] <= fl["max"][i] for i in (0, 2)))
sg, wn = B(rn, "sign"), A(rn, "hall", "wall:north")
check("side inside: just inside the wall", sg["min"][2] == wn["max"][2] + 1, (sg, wn))
check("align_y max + offset", sg["max"][1] == wn["max"][1] - 2, (sg, wn))
check("roof overlap check sees nothing on a bare deck", rn.overlaps == [], rn.overlaps)

# errors
cyc = base_scene()
cyc["nodes"][0]["attach"] = {"target": "dish", "surface": "top"}
raises("cycle detected", lambda: Scene.from_dict(cyc).compile(), "attach cycle", "hub", "wing", "dish")
selfc = {"nodes": [{"id": "a", "kind": "boxes", "attach": "a.top", "params": {"blocks": [[0, 0, 0, "minecraft:stone"]]}}]}
raises("self-attach is a cycle", lambda: Scene.from_dict(selfc).compile(), "attach cycle", "a -> a")
miss = base_scene()
miss["nodes"][2]["attach"] = "wingg.roof_deck"
raises("missing target", lambda: Scene.from_dict(miss).compile(), "unknown node 'wingg'", "did you mean 'wing'")
bad = base_scene()
bad["nodes"][2]["attach"] = "wing.roof_dek"
raises("unknown surface lists anchors", lambda: Scene.from_dict(bad).compile(), "no anchor 'roof_dek'", "roof_deck",
       "wall:north")
typo = {"nodes": [{"id": "a", "kind": "structure", "params": {"widht": 9}}]}
raises("param typo caught", lambda: Scene.from_dict(typo).compile(), "unknown param 'widht'", "params:")
raises("unknown $role", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes",
                                                             "params": {"blocks": [[0, 0, 0, "$glas"]]}}]}).compile(),
       "$glas", "glass")
raises("generator error wrapped", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "multiblock",
                                                                       "params": {"kind": "controller_frame", "size": 9}}]}).compile(),
       "node 'a'", "7x7x7")
raises("empty node", lambda: Scene.from_dict({"nodes": [{"id": "a", "kind": "boxes"}]}).compile(), "no blocks")

# floating detection
fly = Scene.from_dict({"nodes": [
    {"id": "base", "kind": "boxes", "params": {"boxes": [[0, 0, 0, 4, 0, 4, "minecraft:stone"]]}},
    {"id": "cloud", "kind": "boxes", "at": [0, 20, 0], "params": {"boxes": [[0, 0, 0, 2, 0, 2, "minecraft:white_wool"]]}},
    {"id": "ship", "kind": "boxes", "at": [10, 30, 0], "floating": True, "params": {"blocks": [[0, 0, 0, "minecraft:oak_planks"]]}},
    {"id": "rider", "kind": "boxes", "attach": "ship.top", "params": {"blocks": [[0, 0, 0, "minecraft:lantern"]]}},
]}).compile()
check("unattached node in the air is floating", fly.floating == ["cloud"], fly.floating)
check("floating flag + things on it are fine", "ship" not in fly.floating and "rider" not in fly.floating)
check("floating shows up in warnings", any("floating" in w for w in fly.warnings))

# ------------------------------------------------------------------------------------------ every kind

print("== node kinds")
kinds = Scene.from_dict({"kit": "steampunk", "nodes": [
    {"id": "plat", "kind": "platform", "params": {"shape": "rect", "w": 41, "d": 31, "steps": 2}},
    {"id": "house", "kind": "structure", "attach": {"target": "plat", "surface": "roof_deck", "align": "min",
                                                    "offset": [2, 0, 2]},
     "params": {"w": 11, "d": 9, "floors": 1, "floor_h": 5}},
    {"id": "span", "kind": "bridge", "attach": {"target": "house", "surface": "wall:east", "align_y": "min"},
     "params": {"length": 6, "along": "x", "width": 5, "height": 4}},
    {"id": "ramp", "kind": "slope", "attach": {"target": "plat", "surface": "roof_deck", "align": "max"},
     "params": {"w": 5, "run": 6, "rise": 4}},
    {"id": "needle", "kind": "spire", "attach": {"target": "plat", "surface": "roof_deck", "align": {"x": "min", "z": "max"}},
     "params": {"h": 12, "base": 5}},
    {"id": "tower", "kind": "shape", "attach": {"target": "plat", "surface": "roof_deck", "offset": [6, 0, 0]},
     "params": {"parts": [{"kind": "round_tower", "r": 3, "h": 8, "block": "$wall"},
                          {"kind": "cone_roof", "at": [-1, 8, -1], "r": 4, "block": "$roof"}]}},
    {"id": "core", "kind": "multiblock", "attach": {"target": "plat", "surface": "roof_deck", "offset": [-8, 0, 0]},
     "params": {"kind": "controller_frame", "size": 4}},
    {"id": "deck_box", "kind": "boxes", "attach": {"target": "plat", "surface": "roof_deck", "offset": [0, 0, 8]},
     "params": {"palette": {"F": "$base"}, "boxes": [[0, 0, 0, 3, 0, 3, "F"], [0, 1, 0, 3, 3, 3, "F", "frame"]],
                "blocks": [[1, 1, 1, "$glow"]]}},
]})
rk = kinds.compile()
for g in rk.ghosts:
    check(f"kind {g['kind']}: compiled ({g['count']} blocks)", g["count"] > 0 and (g["blocks"] or g["boxes"]))
check("all kinds: no floating", rk.floating == [], rk.floating)
pd = A(rk, "plat", "roof_deck")
check("platform roof_deck = top step", pd["max"][1] == 1 and pd["normal"] == [0, 1, 0], pd)
check("structure on platform deck", B(rk, "house")["min"][1] == 2)
check("massing kit roles reach the generator", any(b[3] == "minecraft:polished_blackstone_bricks"
                                                    for b in rk.ghost("house")["blocks"]))
check("shape parts get $role", any(b[3] == "minecraft:deepslate_bricks" for b in rk.ghost("tower")["blocks"]))
check("boxes palette $role", rk.ghost("deck_box")["palette"]["F"] == "minecraft:polished_blackstone_bricks")
check("box modes expanded (16 floor + 28 frame edges + 1 block)", rk.ghost("deck_box")["count"] == 45,
      rk.ghost("deck_box")["count"])
check("bridge flush with house east wall", B(rk, "span")["min"][0] == B(rk, "house")["max"][0] + 1)
check("multiblock info passes through", rk.ghost("core")["info"] is None or isinstance(rk.ghost("core")["info"], str))

# vanilla compile: palette is vanilla, mod blocks the generators emit are reported / dropped
rv = sc.compile("vanilla")
check("vanilla scene palette all minecraft:", all(b.startswith("minecraft:") for b in rv.palette.values()), rv.palette)
check("vanilla: $glass falls back in shapes", all(b[3].startswith("minecraft:cyan_stained_glass")
                                                   for b in rv.ghost("dish")["blocks"]))
check("geometry independent of the pack", [g["bounds"] for g in rv.ghosts] == [g["bounds"] for g in res.ghosts])
check("vanilla: fallbacks listed", any(f["role"] == "glass" for f in rv.fallbacks))
check("vanilla: ae2 multiblock blocks reported", any(k.startswith("ae2:") for k in rv.missing_blocks), rv.missing_blocks)
rd = sc.compile("vanilla", on_missing="drop")
left = {palettes.base_id(scene._state_of(b[3], g["palette"])) for g in rd.ghosts for b in g["blocks"]} | \
       {palettes.base_id(scene._state_of(b[6], g["palette"])) for g in rd.ghosts for b in g["boxes"]}
check("on_missing=drop leaves only vanilla", all(b in VANILLA for b in left), sorted(b for b in left if b not in VANILLA))
raises("on_missing=error", lambda: sc.compile("vanilla", on_missing="error"), "not in this pack", "ae2:")
check("ATM10-like registry: no palette fallbacks", sc.compile(ATM10).fallbacks == [])

# ------------------------------------------------------------------------------------------ patches

print("== apply_patch")
p = Scene.from_dict(base_scene())
r0 = p.compile()
out = p.apply_patch({"op": "add_node", "node": {"id": "lamp", "kind": "boxes", "attach": "crate.top",
                                                 "params": {"blocks": [[0, 0, 0, "$glow"]]}}})
check("add: changed/dirty", out["changed"] == ["lamp"] and out["dirty"] == ["lamp"], out)
r1 = p.compile()
check("add: diff sets only the new ghost", r1.diff(r0) == {"set": ["demo/lamp"], "clear": [],
                                                           "keep": [g for g in r0.hashes()]}, r1.diff(r0))
check("add: lamp on crate", B(r1, "lamp")["min"][1] == B(r1, "crate")["max"][1] + 1)
raises("add existing id fails", lambda: p.apply_patch({"op": "add_node", "node": {"id": "lamp", "kind": "boxes"}}),
       "already exists")
# resize the hub: its dependents move with it
out = p.apply_patch({"op": "patch_node", "id": "hub", "patch": {"params": {"w": 27}}})
check("resize: dirty = hub + dependents", out["dirty"] == ["hub", "wing", "dish", "cpu", "crate", "lamp"], out)
r2 = p.compile()
check("resize: hub wider", B(r2, "hub")["size"][0] == 27)
check("resize: wing follows the east wall", B(r2, "wing")["min"][0] == B(r2, "hub")["max"][0] + 3)
check("resize: dish follows the wing", B(r2, "dish")["min"][0] - B(r2, "wing")["min"][0]
      == B(r1, "dish")["min"][0] - B(r1, "wing")["min"][0])
check("resize: still no floating", r2.floating == [], r2.floating)
check("resize: other params kept (merge patch)", p.get("hub").params["d"] == 15 and p.get("hub").params["floors"] == 2)
# null deletes; moving with at detaches
p.apply_patch({"op": "patch_node", "id": "crate", "patch": {"at": [-10, 0, 0]}})
check("patch at detaches", p.get("crate").attach is None and p.get("crate").at == [-10, 0, 0])
p.apply_patch({"op": "patch_node", "id": "hub", "patch": {"params": {"entrances": None}}})
check("null deletes a param", "entrances" not in p.get("hub").params)
# swap kit: same geometry, new blocks
before = p.compile()
out = p.apply_patch({"op": "set_palette", "kit": "gothic", "roles": {"roof": "minecraft:bricks"}})
after = p.compile()
check("swap kit: every inheriting node dirty", set(out["dirty"]) == {n.id for n in p.nodes}, out)
check("swap kit: scene kit + palette", after.kit == "gothic" and after.palette["roof"] == "minecraft:bricks")
check("swap kit: blocks changed", after.ghost("hub")["blocks"] != before.ghost("hub")["blocks"])
check("swap kit: multiblock untouched", after.hashes()["demo/cpu"] == before.hashes()["demo/cpu"])
p.apply_patch({"op": "set_palette", "roles": {"roof": None}})
check("role null removes override", "roof" not in p.roles)
p.apply_patch({"op": "set_palette", "id": "wing", "kit": "hextech"})
check("node kit override", p.compile().ghost("wing")["kit"] == "hextech")
# remove
raises("remove with dependents fails", lambda: p.apply_patch({"op": "remove_node", "id": "wing"}), "dish", "orphans")
q = p.copy()
out = q.apply_patch({"op": "remove_node", "id": "wing", "orphans": "remove"})
check("remove cascade", out["removed"] == ["wing", "dish"] and "dish" not in [n.id for n in q.nodes], out)
q = p.copy()
was = p.compile().ghost("dish")["origin"]
q.apply_patch({"op": "remove_node", "id": "wing", "orphans": "pin"})
check("remove pin keeps the child in place", q.compile().ghost("dish")["origin"] == was and q.get("dish").at is not None)
rq = q.compile()
check("pinned child on a removed roof now floats (reported)", rq.floating == ["dish"], rq.floating)
check("diff clears removed ghost", "demo/wing" in rq.diff(p.compile())["clear"])
out = p.apply_patch({"op": "remove_node", "id": "lamp"})
check("remove leaf", out["removed"] == ["lamp"])
# atomic: a failing op leaves the scene unchanged
snap = p.to_dict()
raises("atomic failure", lambda: p.apply_patch([{"op": "patch_node", "id": "hub", "patch": {"params": {"w": 31}}},
                                                 {"op": "patch_node", "id": "nope", "patch": {}}]), "op 1", "nope")
check("atomic: nothing applied", p.to_dict() == snap)
raises("patch creating a cycle rejected", lambda: p.apply_patch({"op": "patch_node", "id": "hub",
                                                                  "patch": {"attach": {"target": "dish", "surface": "top"}}}),
       "attach cycle")
check("cycle patch left scene unchanged", p.to_dict() == snap)
raises("unknown op", lambda: p.apply_patch({"op": "patch_nod"}), "patch_node")
p.apply_patch({"op": "set_scene", "origin": [0, 70, 0]})
check("set_scene moves every ghost", p.compile().ghost("hub")["origin"] == [0, 70, 0])

# ------------------------------------------------------------------------------------------ outputs

print("== outputs")
args = res.ghost_set_args()
check("ghost_set args per node", [a["id"] for a in args] == [g["ghost_id"] for g in res.ghosts])
a0 = args[0]
check("compact: every key in palette", all(b[3] in a0["palette"] for b in a0["blocks"]))
check("compact: same states", sorted(a0["palette"][b[3]] for b in a0["blocks"])
      == sorted(b[3] for b in res.ghost("hub")["blocks"]))
check("compact: fewer bytes", len(json.dumps(a0)) < len(json.dumps(res.ghost_set_args(compact=False)[0])))
check("compact keeps multiblock keys", all(b[3] in args[3]["palette"] for b in args[3]["blocks"]))
text = res.describe()
check("describe names every node", all(f"- {g['id']} " in text for g in res.ghosts), text)
check("describe lists anchors compactly", "wall:north|south" in text and "pad[0-2]" in text and "floor[0-1]" in text, text)
check("describe has no block dumps", "minecraft:" not in text and len(text) < 2500, len(text))
check("describe shows attach", "on wing.roof_deck" in text and "on hub.wall:east offset [2, 0, 0]" in text, text)
check("describe verbose shows anchor boxes", "roof_deck: [" in res.describe(verbose=True))
td = res.to_dict(blocks=False)
check("to_dict(blocks=False) is small JSON", "blocks" not in td["ghosts"][0] and json.dumps(td))
check("HELP mentions anchors", "roof_deck" in scene.HELP and "attach" in scene.HELP)
doc = Path(__file__).resolve().parent.parent / "docs" / "SCENE_GRAPH_DESIGN.md"
if doc.exists():  # the design doc's example scene must compile clean
    import re
    m = re.search(r'```json\n(\{\n  "version".*?)\n```', doc.read_text(encoding="utf-8"), re.S)
    rx = Scene.from_dict(json.loads(m.group(1))).compile() if m else None
    check("design doc example compiles clean", rx is not None and rx.floating == [] and rx.overlaps == [],
          rx and (rx.floating, rx.overlaps))

print()
print(f"FAILED: {failed}" if failed else "all ok")
sys.exit(1 if failed else 0)
