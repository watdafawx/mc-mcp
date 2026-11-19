"""Offline check of the service infrastructure (no API, no Minecraft): python test_services.py

Builds a campus per style with several mod wings and checks the trench connects every wing to the hub, nothing else overlaps it,
the port wall faces the hub, wing size grows with the machine count, and (when knowledge/blocklib.json exists) every block id the
services use exists in the library.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import campus  # noqa: E402
import services  # noqa: E402

fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


# --- sizing: monotonic in the machine count, odd, inside the clamp
prev = None
for c in range(1, 41):
    w, d = services.size_for(c)
    check(w % 2 == 1 and d % 2 == 1, f"size_for({c}) not odd: {w}x{d}")
    check(27 <= w <= 65 and 33 <= d <= 81, f"size_for({c}) out of range: {w}x{d}")
    if prev:
        check(w * d >= prev, f"size_for not monotonic at {c}: {w * d} < {prev}")
    prev = w * d
check(services.size_for(20)[0] * services.size_for(20)[1] > services.size_for(8)[0] * services.size_for(8)[1] * 1.3,
      "20 clusters not clearly bigger than 8")

WINGS = [{"name": "ae2", "rooms": ["mod_room:ae2", "expansion"]},
         {"name": "mek", "rooms": ["mod_room:mekanism", "expansion"], "machines": 8},
         {"name": "pow", "rooms": ["mod_room:powah", "expansion"], "machines": 20},
         {"name": "cre", "rooms": ["mod_room:create", "expansion"]},
         {"name": "er", "rooms": ["mod_room:bigreactors", "expansion"], "machines": 10}]  # er: a mod room with no plinth
MODS = ("mek", "pow", "cre", "er")


def bbox(ghost):
    ox, oy, oz = ghost["origin"]
    xs = [b[0] + ox for b in ghost["blocks"]]
    zs = [b[2] + oz for b in ghost["blocks"]]
    return max(xs) - min(xs) + 1, max(zs) - min(zs) + 1


for kit in ("steampunk", "hextech", "gothic", "station_white", "solarpunk"):
    g = campus.build(kit, [dict(w) for w in WINGS], seed=3)
    by = {x["id"]: x for x in g}
    check("services" in by, f"{kit}: no services ghost")
    if "services" not in by:
        continue
    meta = by["services"]["meta"]
    paths = meta["paths"]
    # 4-connected centre lines
    for p in paths:
        cells = [tuple(c) for c in p["cells"]]
        check(all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(cells, cells[1:])), f"{kit}: path {p['name']} not 4-connected")
    # every mod wing's manifold is reachable from the hub through the union of paths
    union = {tuple(c) for p in paths for c in p["cells"]}
    hub = tuple(meta["hub"])
    check(hub in union, f"{kit}: hub {hub} not on the trench")
    seen, todo = {hub}, [hub]
    while todo:
        a = todo.pop()
        for dx, dz in services.N4:
            n = (a[0] + dx, a[1] + dz)
            if n in union and n not in seen:
                seen.add(n)
                todo.append(n)
    check(len(meta["wings"]) == len(MODS), f"{kit}: {len(meta['wings'])} service wings, want {len(MODS)}")
    for w in meta["wings"]:
        check(any(tuple(m) in seen for m in w["manifold"]), f"{kit}: wing {w['name']} not connected to the hub by the trench")
        check(len(w["bays"]) >= 3, f"{kit}: wing {w['name']} has {len(w['bays'])} port bays")
        # port wall faces the hub: the bays are on the hub side of the wing centre
        bx = sum(b[0] for b in w["bays"]) / len(w["bays"])
        bz = sum(b[1] for b in w["bays"]) / len(w["bays"])
        cx, cz = w["centre"]
        if w["ty"] == 0:
            check((bx - cx) * (hub[0] - cx) + (bz - cz) * (hub[1] - cz) > 0, f"{kit}: wing {w['name']} port wall faces away from the hub")
        else:  # terrace tiers: the door side is toward the stairs (south, +z)
            check(bz > cz, f"{kit}: tier wing {w['name']} port wall not toward the stairs")
        check(all(b[2] in "MPFI" for b in w["bays"]), f"{kit}: bay letters {w['bays']}")
    # the trench overlaps nothing: services cells are disjoint from every other ghost's cells
    occ = {}
    for x in g:
        if x["id"] == "services":
            continue
        ox, oy, oz = x["origin"]
        for b in x["blocks"]:
            occ[(b[0] + ox, b[1] + oy, b[2] + oz)] = x["id"]
    ox, oy, oz = by["services"]["origin"]
    clash = [(b[0] + ox, b[1] + oy, b[2] + oz) for b in by["services"]["blocks"] if (b[0] + ox, b[1] + oy, b[2] + oz) in occ]
    check(not clash, f"{kit}: services overlap other ghosts at {clash[:3]}")
    # and none of it climbs into a room: ground-tier trench blocks stay at or below the hall floor
    ymax = max(b[1] for b in by["services"]["blocks"] if True)
    check(ymax <= services.TOP + 2 * campus.RISE + 1, f"{kit}: services block at y={ymax}")
    # sizing in the build: the 20-cluster wing is bigger than the 8-cluster one
    wing_by = {k: v for k, v in by.items() if k.startswith("wing_")}
    a8, a20 = bbox(wing_by["wing_mek"]), bbox(wing_by["wing_pow"])
    check(a20[0] * a20[1] > a8[0] * a8[1], f"{kit}: wing for 20 clusters {a20} not bigger than for 8 {a8}")
    sx, sz = services.size_for(8)
    check(min(a8) >= min(sx, sz) - 1, f"{kit}: wing for 8 clusters {a8} smaller than size_for {sx}x{sz}")

# library check for the ids the services place
lib = HERE / "knowledge" / "blocklib.json"
if lib.exists():
    ids = json.load(open(lib, encoding="utf-8"))
    used = set()
    src = (HERE / "services.py").read_text(encoding="utf-8")
    for m in re.finditer(r'"((?:minecraft|ae2|powah|create):[a-z_0-9]+)(?:\[[^"]*)?"', src):
        used.add(m.group(1))
    for b in sorted(used):
        check(b in ids, f"services uses {b}: not in the block library")
else:
    print("blocklib.json missing: library checks skipped")

if fails:
    print("FAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("test_services OK")
