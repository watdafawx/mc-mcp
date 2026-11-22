"""Offline tests for shapes.py: python test_shapes.py   (no Minecraft, no API; ~1 s).

Every generator (classic, styled volume and the new architectural parts) is run through shapes.build(), and the
output must be: non-empty; made of [x, y, z, str] cells with integer coordinates; blockstates with a real id and
only legal facing=/half=/shape=/type=/axis= values; stairs and slabs that carry their required properties; a sane
bounding box that agrees with the reported summary. Bad dimensions and unknown kinds must raise ShapeError.
A few form checks cover the new parts (machicolations, dormer window, buttress taper, spiral walk, arch, walkway).

Prints "ok"/"FAIL" per check and exits non-zero on any failure.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import shapes  # noqa: E402

FACING = {"north", "south", "east", "west"}
HALF = {"top", "bottom"}
STAIR_SHAPE = {"straight", "inner_left", "inner_right", "outer_left", "outer_right"}
SLAB_TYPE = {"top", "bottom", "double"}
AXIS = {"x", "y", "z"}
ID_RE = re.compile(r"^([a-z0-9_.-]+:[a-z0-9_./-]+)(?:\[(.*)\])?$")

failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  " + str(extra)))
    if not cond:
        failed += 1


def parse(state):
    """(id, props) for a blockstate string, or None when it is not a well-formed id[id=k=v,...]."""
    m = ID_RE.match(state or "")
    if not m:
        return None
    props = {}
    if m.group(2):
        for kv in m.group(2).split(","):
            k, _, v = kv.partition("=")
            if not k or not v:
                return None
            props[k] = v
    return m.group(1), props


def validate(tag, blocks, strict_cells=True):
    """Invariants every generator shares; returns (min, max) of the bbox. Older generators append over an earlier
    cell on purpose (a window cut into a wall, hip corners over straight stairs), so `strict_cells` is off for them."""
    if not blocks:
        check(f"{tag}: non-empty", False, "0 cells")
        return None
    bad, cells = [], {}
    for b in blocks:
        if not (isinstance(b, list) and len(b) == 4):
            bad.append(("not [x,y,z,state]", b))
            continue
        x, y, z, state = b
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (x, y, z)):
            bad.append(("non-int coords", b))
            continue
        got = parse(state) if isinstance(state, str) else None
        if got is None:
            bad.append(("bad blockstate", state))
            continue
        bid, props = got
        for k, v in props.items():
            legal = {"facing": FACING, "half": HALF, "shape": STAIR_SHAPE, "type": SLAB_TYPE, "axis": AXIS}.get(k)
            if legal is not None and v not in legal:
                bad.append((f"bad {k}= value", state))
        if bid.endswith("_stairs") and not {"facing", "half"} <= set(props):
            bad.append(("stairs without facing/half", state))
        if bid.endswith("_slab") and "type" not in props:
            bad.append(("slab without type", state))
        key = (x, y, z)
        if strict_cells and key in cells and cells[key] != state:
            bad.append(("two states in one cell", (key, cells[key], state)))
        cells[key] = state
    check(f"{tag}: {len(blocks)} cells, legal ids/states/cells", not bad, bad[:3])
    mn = [min(b[j] for b in blocks) for j in range(3)]
    mx = [max(b[j] for b in blocks) for j in range(3)]
    sane = (all(mx[j] >= mn[j] for j in range(3)) and all(mx[j] - mn[j] <= 420 for j in range(3))
            and mx[1] >= 0 and mn[1] >= -80)
    check(f"{tag}: bbox sane {mn}..{mx}", sane)
    return mn, mx


# ------------------------------------------------------------------------------------------ every generator

CASES = [
    # classic parts
    ("round_tower", {}),
    ("round_tower", {"r": 4, "h": 16, "hollow": False, "windows": 6, "window_every": 3}),
    ("cone_roof", {}),
    ("cone_roof", {"r": 5, "overhang": 2, "tip": None}),
    ("gable_roof", {}),
    ("gable_roof", {"stepped": True, "axis": "z", "w": 7, "d": 9}),
    ("pyramid_roof", {}),
    ("battlements", {}),
    ("battlements", {"corbel": True}),
    ("window_row", {}),
    ("window_row", {"along": "z", "outward": "east", "sill": "minecraft:stone_brick_stairs", "frame": "minecraft:oak_planks"}),
    ("arch", {}),
    ("arch", {"w": 5, "h": 5, "along": "z", "depth": 3}),
    ("dome", {}),
    ("dome", {"r": 3, "hollow": False, "tip": "minecraft:lantern"}),
    ("dome", {"r": 9, "tip": "minecraft:end_rod"}),
    ("pillar_row", {}),
    ("pillar_row", {"count": 3, "along": "z", "size": 2, "base": "minecraft:polished_blackstone"}),
    # new architectural parts
    ("square_tower", {}),
    ("square_tower", {"w": 8, "d": 6, "h": 20, "machicolations": False, "floor": "minecraft:oak_planks", "floors_every": 5}),
    ("dormer", {}),
    ("dormer", {"facing": "north", "w": 5, "h": 6, "depth": 3}),
    ("dormer", {"facing": "east"}),
    ("dormer", {"facing": "west", "w": 4, "depth": 6}),
    ("buttress_row", {}),
    ("buttress_row", {"axis": "z", "side": "west", "length": 9, "h": 6, "depth": 2, "spacing": 3}),
    ("spiral_stair", {}),
    ("spiral_stair", {"r": 4, "h": 14, "clockwise": False, "pillar": "minecraft:polished_deepslate"}),
    ("bridge", {}),
    ("bridge", {"axis": "z", "length": 17, "width": 7, "arch_rise": 5}),
    ("arch_bridge", {"length": 9, "width": 3, "arch_rise": 2, "rail": None, "lanterns": False}),
    ("wall_segment", {}),
    ("wall_segment", {"thickness": 1, "h": 5, "axis": "z", "crenel_side": "far"}),
    ("wall_segment", {"thickness": 5, "h": 9, "walkway": "minecraft:stone_brick_slab[type=top]", "crenel_side": "near"}),
    # styled volumes (massing)
    ("structure", {}),
    ("structure", {"shape": "round", "r": 7, "kit": "gothic", "roof": "dome"}),
    ("platform", {}),
    ("bridge", {"length": 10, "along": "x", "width": 5, "height": 4, "kit": "hextech"}),   # kit -> styled sky-bridge
    ("slope", {}),
    ("spire", {}),
]

print("== every generator through shapes.build()")
# the new parts build into a dict, so one cell can never carry two states; the older ones append over earlier cells
STRICT = {"square_tower", "dormer", "buttress_row", "spiral_stair", "arch_bridge", "wall_segment"}
for kind, kw in CASES:
    tag = kind + (" " + str(kw) if kw else "")
    try:
        blocks, summ = shapes.build([{"kind": kind, **kw}])
    except Exception as e:  # noqa: BLE001 - a raise here is a test failure, not a crash
        check(f"{tag}: builds", False, f"{type(e).__name__}: {e}")
        continue
    mn, mx = validate(tag, blocks, kind in STRICT)
    ok = mn is not None and summ and summ[0]["kind"] == kind and summ[0]["min"] == mn and summ[0]["max"] == mx
    check(f"{tag}: summary matches the blocks", ok, summ)

print("== `at` offsets the whole part")
b, summ = shapes.build([{"kind": "square_tower", "at": [10, 64, -5]}])
off = {(x - 10, y - 64, z + 5) for (x, y, z, s) in b}
base = {(x, y, z) for (x, y, z, s) in shapes.build([{"kind": "square_tower"}])[0]}
check("at: same shape, only the coordinates move", off == base and summ[0]["min"] == [9, 64, -6])

# ------------------------------------------------------------------------------------------ new part forms

print("== square_tower")
cells = {(x, y, z): s for (x, y, z, s) in shapes.square_tower(w=5, d=5, h=12)}
check("square_tower: shaft is hollow", (2, 5, 2) not in cells and (0, 5, 2) in cells)
check("square_tower: windows cut all four faces", sum("glass_pane" in s for s in cells.values()) == 16,
      sum("glass_pane" in s for s in cells.values()))
check("square_tower: overhang is 1 proud on every side",
      min(x for (x, y, z) in cells) == -1 and max(x for (x, y, z) in cells) == 5 and
      min(z for (x, y, z) in cells) == -1 and max(z for (x, y, z) in cells) == 5)
check("square_tower: corbel is upside-down stairs under the overhang",
      all("half=top" in cells[(x, 11, z)] for x, z in ((-1, -1), (2, -1), (5, 5))))
check("square_tower: drop opening in each overhang side, the rest solid",
      (2, 12, -1) not in cells and (1, 12, -1) in cells and (2, 12, 5) not in cells
      and (-1, 12, 2) not in cells and (5, 12, 2) not in cells)
check("square_tower: merlons alternate above the parapet",
      sorted({x for (x, y, z) in cells if y == 13 and z == -1}) == [-1, 1, 3, 5])
plain = {(x, y, z): s for (x, y, z, s) in shapes.square_tower(w=5, d=5, h=12, machicolations=False)}
check("square_tower: without machicolations it stays on the wall line",
      min(x for (x, y, z) in plain) == 0 and max(x for (x, y, z) in plain) == 4)
floored = {(x, y, z): s for (x, y, z, s) in shapes.square_tower(w=6, d=6, h=11, floor="minecraft:oak_planks",
                                                              floors_every=5)}
check("square_tower: floors land inside the shell", all(floored[(2, y, 2)] == "minecraft:oak_planks" for y in (0, 5, 10)))

print("== dormer")
cells = {(x, y, z): s for (x, y, z, s) in shapes.dormer(w=3, h=4, depth=4)}
front = 3                                       # the front wall plane = depth - 1; the rooflet eaves past it
check("dormer: window is set back one behind the front plane",
      cells.get((1, 1, front - 1)) == "minecraft:glass_pane" and (1, 1, front) not in cells)
check("dormer: proud sill and jambs frame the opening",
      "slab" in cells[(1, 0, front + 1)] and cells[(0, 1, front + 1)] == "minecraft:stone_bricks")
check("dormer: rooflet is stairs climbing to a slab ridge",
      any("_stairs[facing=east" in s for s in cells.values()) and any("_stairs[facing=west" in s for s in cells.values())
      and any("_slab[type=bottom]" in s for s in cells.values()))
check("dormer: rooflet overhangs the sides", min(x for (x, y, z) in cells) < 0 and max(x for (x, y, z) in cells) > 2)
n = {(x, y, z): s for (x, y, z, s) in shapes.dormer(facing="north")}
check("dormer: facing north puts the front at z=0",
      n[(1, 1, 1)] == "minecraft:glass_pane" and (1, 1, 0) not in n and max(z for (x, y, z) in n) > 2)
e = {(x, y, z): s for (x, y, z, s) in shapes.dormer(facing="east")}
check("dormer: facing east turns the box (front on the +x side)",
      min(x for (x, y, z) in e) == 0 and max(x for (x, y, z) in e) == 4 and e[(2, 1, 1)] == "minecraft:glass_pane")
check("dormer: east/west roof stairs face north/south, not east/west",
      any("_stairs[facing=south" in s or "_stairs[facing=north" in s for s in e.values()))

print("== buttress_row")
cells = {(x, y, z): s for (x, y, z, s) in shapes.buttress_row(length=15, h=9, depth=3, spacing=4)}
tops = {z: max(y for (x, y, z2) in cells if z2 == z and x == 0) for z in (1, 2, 3)}
check("buttress_row: tapers as it reaches out from the wall", tops[1] > tops[2] > tops[3], tops)
check("buttress_row: a buttress every spacing blocks",
      sorted({x for (x, y, z) in cells if y == 0}) == [0, 4, 8, 12])
check("buttress_row: caps are stairs climbing back toward the wall",
      all("facing=north" in s for s in cells.values() if "stairs" in s))
check("buttress_row: stays on the outside of the wall plane", min(z for (x, y, z) in cells) == 1)
w = {(x, y, z): s for (x, y, z, s) in shapes.buttress_row(axis="z", side="west", length=9, h=6, depth=2)}
check("buttress_row: side=west projects to negative x, caps face east",
      max(x for (x, y, z) in w) == -1 and all("facing=east" in s for s in w.values() if "stairs" in s))

print("== spiral_stair")
blocks = shapes.spiral_stair(r=2, h=10)
solid = {(x, y, z) for (x, y, z, s) in blocks}
stairs = [(x, y, z, s) for (x, y, z, s) in blocks if "stairs" in s]
check("spiral_stair: central pillar from the floor to the top", all((2, y, 2) in solid for y in range(0, 11)))
check("spiral_stair: tops out at h", max(y for (x, y, z) in solid) == 10)
check("spiral_stair: one stair per rise", len(stairs) == 9, len(stairs))
check("spiral_stair: no floating tread (every stair has support)", all((x, y - 1, z) in solid for (x, y, z, s) in stairs))
check("spiral_stair: every stair faces along the walk, never into the pillar",
      all(("facing=%s" % f) in s for (x, y, z, s) in stairs for f in [s.split("facing=")[1][:5]]))

print("== arch bridge")
cells = {(x, y, z): s for (x, y, z, s) in shapes.arch_bridge(length=15, width=5, arch_rise=3)}
void = {y: sum(1 for x in range(15) if (x, y, 2) not in cells) for y in range(-4, 0)}
check("arch bridge: deck is one flat course at y=0", all((x, 0, 2) in cells for x in range(15))
      and not any((x, 1, 2) in cells for x in range(15)))
check("arch bridge: the opening narrows toward the deck (a real arch)",
      void[-1] == 13 and void[-2] == 13 and void[-3] == 7, void)
check("arch bridge: intrados is chamfered with upside-down stairs at the springing",
      sum("half=top" in s for s in cells.values()) == 30
      and sorted({x for (x, y, z), s in cells.items() if "half=top" in s}) == [0, 3, 11, 14])
check("arch bridge: railings down both sides, lanterns on the ends and the crown",
      sum("_wall" in s for s in cells.values()) == 30 and sum("lantern" in s for s in cells.values()) == 6)
z = {(x, y, z): s for (x, y, z, s) in shapes.arch_bridge(length=17, width=5, arch_rise=5, axis="z")}
check("arch bridge: axis=z builds along z", max(z_key[2] for z_key in z) == 16 and max(k[0] for k in z) == 4)

print("== wall_segment")
h, t = 8, 4
cells = {(x, y, z): s for (x, y, z, s) in shapes.wall_segment(length=15, h=h, thickness=t,
                                                             walkway="minecraft:stone_brick_slab[type=top]")}
check("wall_segment: body is solid up to the walkway", all((0, y, 1) in cells for y in range(h - 1)))
check("wall_segment: walkway floor runs down the middle",
      all(cells[(x, h - 1, 2)] == "minecraft:stone_brick_slab[type=top]" for x in range(15)))
check("wall_segment: parapet on both edges, merlons alternating above",
      all((x, h - 1, 0) in cells and (x, h - 1, t - 1) in cells for x in range(15))
      and sorted({x for (x, y, z) in cells if y == h and z == 0}) == list(range(0, 15, 2)))
near = {(x, y, z) for (x, y, z, s) in shapes.wall_segment(length=15, h=h, thickness=t, crenel_side="near")}
check("wall_segment: crenel_side=near leaves the far parapet plain",
      not any((x, h, t - 1) in near for x in range(15)) and any((x, h, 0) in near for x in range(15)))
thin = {(x, y, z) for (x, y, z, s) in shapes.wall_segment(length=9, h=5, thickness=1)}
check("wall_segment: a thin wall has no walkway, merlons on the whole top",
      (0, 4, 0) in thin and (0, 5, 0) in thin and not any((x, 5, 0) in thin for x in range(1, 9, 2)))

print("== smoothed gable_roof and dome")
cells = {(x, y, z): s for (x, y, z, s) in shapes.gable_roof(w=9, d=7, stepped=True)}
top = {z: max(y for (x, y, z2) in cells if z2 == z and x == 0) for z in range(7)}
check("gable_roof stepped: crow-steps rise 1 at a time", all(abs(top[z + 1] - top[z]) <= 1 for z in range(6)), top)
check("gable_roof stepped: each step's top is an upside-down stair facing out of the gable",
      all("half=top" in cells[(-1, top[z], z)] and "facing=west" in cells[(-1, top[z], z)] for z in range(7)),
      [cells.get((-1, top[z], z)) for z in range(7)])
check("gable_roof stepped: apex sits on the ridge height", max(y for (x, y, z) in cells) == top[3])
zc = {(x, y, z): s for (x, y, z, s) in shapes.gable_roof(w=7, d=9, axis="z", stepped=True)}
top_z = {x: max(y for (xx, y, zz) in zc if xx == x and zz == -1) for x in range(7)}
check("gable_roof stepped: axis=z turns the steps with the gable (facing north at z=-1)",
      all("facing=north" in zc[(x, top_z[x], -1)] and "half=top" in zc[(x, top_z[x], -1)] for x in range(7)),
      [zc.get((x, top_z[x], -1)) for x in range(7)])
small = {(x, y, z): s for (x, y, z, s) in shapes.dome(r=3)}
check("dome r<=5: rim and crown are slabs, so the curve reads",
      sum("_slab[type=bottom]" in s for s in small.values()) >= 4 and any("type=top" in s for s in small.values()))
check("dome r<=5: the centre crown is a half block", "type=bottom" in small[(3, max(y for (x, y, z) in small if (x, z) == (3, 3)), 3)])
big = shapes.dome(r=9)
check("dome r>5: still full blocks (no slabs to place)", not any("_slab" in s for (x, y, z, s) in big))
hollow_small = {(x, y, z): s for (x, y, z, s) in shapes.dome(r=4)}
slab_levels = sorted({y for (x, y, z), s in hollow_small.items() if "_slab" in s})
check("dome r<=5: slabs round the shoulder and cap layers", len(slab_levels) >= 3, slab_levels)
check("dome r<=5 hollow: the inner skin is cut with top slabs",
      any("type=top" in s for (x, y, z), s in hollow_small.items()))
check("dome r<=5: the crown is a half block",
      "type=bottom" in hollow_small[(4, max(yy for (xx, yy, zz) in hollow_small if (xx, zz) == (4, 4)), 4)])

# ------------------------------------------------------------------------------------------ ShapeError

print("== bad dimensions raise ShapeError")
BAD = [
    ("round_tower", {"r": 0}),
    ("round_tower", {"h": 0}),
    ("dome", {"r": 0}),
    ("dome", {"r": 99}),
    ("square_tower", {"w": 2}),
    ("square_tower", {"d": 99}),
    ("square_tower", {"h": 1}),
    ("square_tower", {"floors_every": 1}),
    ("dormer", {"w": 2}),
    ("dormer", {"h": 2}),
    ("dormer", {"depth": 1}),
    ("dormer", {"facing": "up"}),
    ("buttress_row", {"depth": 0}),
    ("buttress_row", {"h": 0}),
    ("buttress_row", {"axis": "y"}),
    ("buttress_row", {"axis": "x", "side": "east"}),
    ("buttress_row", {"axis": "z", "side": "north"}),
    ("spiral_stair", {"r": 0}),
    ("spiral_stair", {"h": 0}),
    ("wall_segment", {"thickness": 0}),
    ("wall_segment", {"h": 1}),
    ("wall_segment", {"axis": "y"}),
    ("wall_segment", {"crenel_side": "sideways"}),
    ("bridge", {"length": 4}),
    ("bridge", {"width": 2}),
    ("bridge", {"arch_rise": 0}),
    ("bridge", {"axis": "y"}),
    ("arch_bridge", {"length": 99, "arch_rise": 60}),
    ("not_a_kind", {}),
    ("pillar_row", {"count": 2, "bogus": 1}),
]
for kind, kw in BAD:
    try:
        shapes.build([{"kind": kind, **kw}])
    except shapes.ShapeError:
        check(f"ShapeError: {kind} {kw}", True)
    except Exception as e:  # noqa: BLE001
        check(f"ShapeError: {kind} {kw}", False, f"raised {type(e).__name__} instead: {e}")
    else:
        check(f"ShapeError: {kind} {kw}", False, "built without raising")

print()
print(f"FAILED: {failed}" if failed else "all ok")
sys.exit(1 if failed else 0)
