"""Offline checks for the architect/layouts package (the split campus.py): python test_campus_layouts.py  (no Minecraft, no API).

Builds all five layouts twice with a sample wing list and checks they are deterministic, keep the block counts / ghost ids /
metadata (meta.kind, floor_y, deck_y, door) the pre-split monolith produced, that no global kit state is left (CUR_KIT is
gone and the kit reaches _tree explicitly), that kit tables come from kits.json, and that campus.py stays a thin shim.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import campus  # noqa: E402
import layouts  # noqa: E402
import palettes  # noqa: E402
from layouts import common  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)
        print("FAIL", msg)


WINGS = [{"name": "storage", "rooms": ["mod_room", "expansion"]},
         {"name": "magic", "rooms": ["living", "workshop"], "size": "l"},
         {"name": "farm", "rooms": ["storage", "expansion"], "size": "s", "floors": 2}]

# layout -> (kit that defaults to it, total blocks, ghost ids, {ghost id: (floor_y, deck_y, door)}); captured from the
# pre-split campus.py (home wing + WINGS, tower, seed 1), so any drift in a layout shows up here.
GOLDEN = {
    "spine": ("steampunk", 70048,
              ["platform", "wing_home", "wing_storage", "wing_magic", "wing_farm", "gallery_w", "gallery_e", "hub", "tower",
               "tower_mid", "tower_top", "tower_gears", "grounds", "features"], None),
    "radial": ("hextech", 73172,
               ["platform", "hub", "tower", "tower_mid", "tower_mid2", "tower_top", "tower_trim", "airdock", "wing_home",
                "wing_storage", "wing_magic", "wing_farm", "halls", "features", "grounds"],
               {"hub": (3, 15, None), "wing_home": (3, 12, "w"), "wing_storage": (3, 14, "n"), "wing_magic": (3, 16, "e"),
                "wing_farm": (3, 18, "w")}),
    "cloister": ("gothic", 87142,
                 ["platform", "hub", "tower", "tower_mid", "tower_top", "tower_trim", "wing_home", "wing_farm", "wing_storage",
                  "wing_magic", "halls", "porch_0", "porch_3", "porch_1", "porch_2", "features", "grounds"],
                 {"hub": (3, 15, None), "wing_home": (3, 12, "e"), "wing_farm": (3, 18, "e"), "wing_storage": (3, 14, "w"),
                  "wing_magic": (3, 16, "n")}),
    "linear": ("station_white", 63390,
               ["platform", "hub", "tower", "tower_top", "tower_trim", "wing_home", "wing_storage", "wing_magic", "wing_farm",
                "halls", "radar", "features", "grounds"],
               {"hub": (3, 15, None), "wing_home": (3, 19, "ring"), "wing_storage": (3, 14, "s"), "wing_magic": (3, 16, "n"),
                "wing_farm": (3, 18, "s")}),
    "terraces": ("solarpunk", 58388,
                 ["platform", "hub", "wing_home", "wing_storage", "wing_magic", "wing_farm", "tower", "tower_top", "halls",
                  "roofgarden", "features", "grounds", "tiers", "stairs"],
                 {"hub": (3, 15, None), "wing_home": (3, 12, "e"), "wing_storage": (3, 14, "w"), "wing_magic": (8, 21, "s"),
                  "wing_farm": (13, 28, "s")}),
}


def build(kit, layout):
    return campus.build(kit, [dict(w) for w in WINGS], True, "tower", None, seed=1, layout=layout)


# ------------------------------------------------------------------------------------------ files and sizes
print("== package layout")
src = (HERE / "campus.py").read_text(encoding="utf-8")
check(len(src.splitlines()) < 150, f"campus.py is {len(src.splitlines())} lines, want < 150")
for name in ("__init__", "common", "yards", "spine", "radial", "cloister", "linear", "terraces"):
    check((HERE / "layouts" / f"{name}.py").is_file(), f"layouts/{name}.py missing")
check(tuple(layouts.LAYOUTS) == ("spine", "radial", "cloister", "linear", "terraces"), f"registry keys {tuple(layouts.LAYOUTS)}")
check(all(callable(f) for f in layouts.LAYOUTS.values()), "registry values must be callable build functions")
check(layouts.build is campus.build, "campus.build is layouts.build")

# ------------------------------------------------------------------------------------------ no global kit state
print("== no CUR_KIT")
for p in [HERE / "campus.py", *sorted((HERE / "layouts").glob("*.py"))]:
    check("CUR_KIT" not in p.read_text(encoding="utf-8"), f"CUR_KIT still mentioned in {p.name}")
check(not hasattr(campus, "CUR_KIT") and not hasattr(common, "CUR_KIT"), "CUR_KIT attribute still exists")

solar, plain = [], []
common._tree(solar, 0, 0, 0, "oak", 0, "solarpunk")
common._tree(plain, 0, 0, 0, "oak", 0)
check(solar != plain and len(solar) < len(plain), "solarpunk tree should be the thin crown, default the full one")
after = []
common._tree(after, 0, 0, 0, "oak", 0)
check(after == plain, "a solarpunk _tree call must not change later default trees (no leaked kit state)")

# ------------------------------------------------------------------------------------------ kit tables come from kits.json
print("== kit tables from kits.json")
kits = palettes.load_kits()["kits"]
for kit, k in kits.items():
    meta = k.get("meta") or {}
    for attr, key in (("ROOF_CYCLE", "roof_cycle"), ("TOWER_ROOF", "tower_roof"), ("ALT_ROOF", "alt_roof"), ("HUB_ROOF", "hub_roof")):
        check(getattr(campus, attr).get(kit) == meta.get(key), f"{kit}: campus.{attr} != kits.json meta.{key}")
    check(campus.ROOF_MATS.get(kit) == (palettes.resolve_list(meta["roof_mats"]) if "roof_mats" in meta else None),
          f"{kit}: ROOF_MATS differs from kits.json")
    check(campus.GLASS.get(kit) == ([g[len("minecraft:"):-len("_stained_glass")] for g in meta["glass_cycle"]]
                                    if "glass_cycle" in meta else None), f"{kit}: GLASS differs from kits.json")
check(set(campus.ROOF_CYCLE) >= {"steampunk", "gothic", "hextech", "solarpunk", "station_white"}, "ROOF_CYCLE lost a kit")
check(campus.HALL_STYLE == {"gothic": "open"}, f"HALL_STYLE {campus.HALL_STYLE}")
check(common.WING_ROLES["gothic"]["wall"] == "minecraft:stone_bricks", "gothic wing roles not read from kits.json")
for table in ("ROOF_CYCLE =", "ROOF_MATS =", "TOWER_ROOF =", "ALT_ROOF =", "GLASS ="):  # no hardcoded copies left behind
    for p in sorted((HERE / "layouts").glob("*.py")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith(table):
                check("_meta_table" in line or "palettes." in line or "_stained_glass" in line, f"{p.name}: hardcoded {table}")

# ------------------------------------------------------------------------------------------ shim surface
print("== campus shim")
for name in ("build", "STEPS", "SIZES", "RISE", "ROOF_CYCLE", "ROOF_MATS", "ALT_ROOF", "TOWER_ROOF", "HUB_ROOF", "GLASS",
             "GAP", "GD", "HUB", "LAYOUTS", "LAYOUT_NAMES", "summary"):
    check(hasattr(campus, name), f"campus.{name} missing")
check(campus.STEPS == 2 and campus.RISE == 5 and campus.SIZES["x"] == (37, 49), "campus constants changed")
check(campus.LAYOUTS == {"steampunk": "spine", "hextech": "radial", "gothic": "cloister", "station_white": "linear",
                         "solarpunk": "terraces"}, f"default layouts {campus.LAYOUTS}")
try:
    campus.build("steampunk", [], layout="nope")
    check(False, "unknown layout must raise ValueError")
except ValueError as e:
    check("unknown layout" in str(e), f"unexpected message {e}")

# ------------------------------------------------------------------------------------------ the five layouts
for layout, (kit, total, ids, metas) in GOLDEN.items():
    print(f"== {layout} ({kit})")
    a = build(kit, layout)
    b = campus.build(kit, [dict(w) for w in WINGS], True, "tower", None, seed=1)  # default layout of the kit, second build
    check(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), f"{layout}: two builds differ (not deterministic)")
    check([g["id"] for g in a] == ids, f"{layout}: ghost ids {[g['id'] for g in a]}")
    check(sum(len(g["blocks"]) for g in a) == total, f"{layout}: {sum(len(g['blocks']) for g in a)} blocks, want {total}")
    check(len({g["id"] for g in a}) == len(a), f"{layout}: duplicate ghost ids")
    for g in a:
        ok = (isinstance(g["origin"], list) and len(g["origin"]) == 3 and all(isinstance(v, int) for v in g["origin"])
              and g["blocks"] and all(len(bl) == 4 and all(isinstance(v, int) for v in bl[:3]) and isinstance(bl[3], str)
                                      for bl in g["blocks"]))
        check(ok, f"{layout}/{g['id']}: malformed ghost")
    xs = [bl[0] + g["origin"][0] for g in a for bl in g["blocks"]]
    zs = [bl[2] + g["origin"][2] for g in a for bl in g["blocks"]]
    check(min(xs) == 0 and min(zs) == 0, f"{layout}: site min corner is ({min(xs)}, {min(zs)}), want (0, 0)")
    by = {g["id"]: g for g in a}
    if metas is None:  # spine keeps the legacy ghost shape: no meta
        check(all("meta" not in g for g in a), f"{layout}: spine ghosts grew a meta key")
        check(not any(g["id"] == "halls" for g in a), "spine has no halls ghost")
        continue
    kinds = {g["id"]: g["meta"].get("kind") for g in a}
    check(kinds["platform"] == "platform" and kinds["hub"] == "hub" and kinds["grounds"] == "grounds", f"{layout}: kinds {kinds}")
    check(all(kinds[i] == "wing" for i in by if i.startswith("wing_")), f"{layout}: wing ghosts need meta.kind == wing")
    for gid, (fy, dy, door) in metas.items():
        m = by[gid]["meta"]
        check((m.get("floor_y"), m.get("deck_y"), m.get("door")) == (fy, dy, door),
              f"{layout}/{gid}: (floor_y, deck_y, door) {(m.get('floor_y'), m.get('deck_y'), m.get('door'))} want {(fy, dy, door)}")
    for g in a:
        m = g["meta"]
        if "floor_y" in m and "deck_y" in m:
            check(m["deck_y"] > m["floor_y"] >= campus.STEPS + 1, f"{layout}/{g['id']}: floor/deck order {m}")
    if layout == "terraces":  # tiers climb RISE blocks apiece
        floors = sorted(by[i]["meta"]["floor_y"] for i in by if i.startswith("wing_"))
        check(floors == [3, 3, 8, 13] and 8 - 3 == campus.RISE, f"terraces: tier floors {floors}")

print("FAILED" if fails else "ALL OK", len(fails))
sys.exit(1 if fails else 0)
