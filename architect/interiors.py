"""Room fit-out for styled structures: furniture, floors, lights and walkways inside one floor of a building.

structure(program=[...]) calls fit_floor() per floor. A floor's interior cells are split along the long axis into
one segment per room kind, with partition walls and a 3-wide doorway on the central spine. The spine (3 wide, along
the long axis) stays clear on every floor so the entrance, the stair/lift core and every room connect. Furniture
goes along the walls, facing into the room; centre pieces stay off the spine.

All blocks are cheap in survival (see blocklib.py): wood furniture from mcwfurnitures, barrels, chests, vanilla
workstations, luminax/kit glow in the ceiling. Wood and bed colour come from the kit (keys "wood", "colour").
"""
from __future__ import annotations

import random

KINDS = ("living", "workshop", "storage", "machine_hall", "expansion", "lab", "hall", "mod_room")
# mod_room:<theme> pad blocks (border, centre); all cheap. Unknown themes use the kit's trim/detail.
MOD_PADS = {"ae2": ("ae2:smooth_sky_stone_block", "ae2:sky_stone_brick"),
            "create": ("create:andesite_casing", "create:industrial_iron_block"),
            "power": ("create:copper_casing", "create:industrial_iron_block"),
            "processing": ("create:industrial_iron_block", "minecraft:polished_blackstone_bricks"),
            "magic": ("minecraft:polished_blackstone_bricks", "minecraft:amethyst_block"),
            "farming": ("minecraft:mud_bricks", "minecraft:moss_block")}
DIRS = {(0, -1): "north", (0, 1): "south", (-1, 0): "west", (1, 0): "east"}
WOOD = {"station_white": "birch", "cyber_dark": "dark_oak", "ae_sky": "dark_oak", "hextech": "dark_oak",
        "steampunk": "spruce", "gothic": "dark_oak", "solarpunk": "oak", "rust_industrial": "spruce"}
COLOUR = {"station_white": "orange", "cyber_dark": "cyan", "ae_sky": "purple", "hextech": "blue",
          "steampunk": "brown", "gothic": "purple", "solarpunk": "lime", "rust_industrial": "orange"}


def spine_of(cells: set) -> tuple[str, set]:
    """Long axis ('x' or 'z') and the 3-wide central corridor cells along it."""
    xs = [x for x, _ in cells]
    zs = [z for _, z in cells]
    ax = "x" if (max(xs) - min(xs)) >= (max(zs) - min(zs)) else "z"
    if ax == "x":
        c = round((min(zs) + max(zs)) / 2)
        return ax, {(x, z) for (x, z) in cells if abs(z - c) <= 1}
    c = round((min(xs) + max(xs)) / 2)
    return ax, {(x, z) for (x, z) in cells if abs(x - c) <= 1}


def split(cells: set, ax: str, n: int) -> list[set]:
    """n segments along the long axis, roughly equal."""
    key = (lambda p: p[0]) if ax == "x" else (lambda p: p[1])
    lo = min(key(p) for p in cells)
    hi = max(key(p) for p in cells)
    span = hi - lo + 1
    segs = [set() for _ in range(n)]
    for p in cells:
        segs[min(n - 1, (key(p) - lo) * n // span)].add(p)
    return segs


def _face_in(p, cells):
    """Facing (away from the nearest wall) for a cell on the room edge, or None if it isn't on the edge."""
    x, z = p
    for (dx, dz), _ in DIRS.items():
        if (x + dx, z + dz) not in cells:  # wall on that side: face the opposite way
            return DIRS[(-dx, -dz)]
    return None


def fit_room(kind: str, cells: set, fy: int, h: int, K: dict, keep: set, spine: set, kit: str = "",
             seed: int = 1, put=None, ceiling_y: int | None = None):
    """Fit one room. cells: floor cells (x,z) of the room; fy: y of the floor surface block; h: clear headroom
    (air cells above the floor); keep: cells that must stay walkable (spine, doorways, core landing)."""
    rnd = random.Random(seed)
    kind, _, theme = kind.partition(":")
    wood = K.get("wood") or WOOD.get(kit, "oak")
    col = K.get("colour") or COLOUR.get(kit, "white")
    fur = lambda name: f"mcwfurnitures:{wood}_{name}"
    edge = [p for p in sorted(cells) if _face_in(p, cells) and p not in keep]
    centre = [p for p in sorted(cells) if p not in keep and not _face_in(p, cells)]
    used: set = set()
    cy = ceiling_y if ceiling_y is not None else fy + h + 1

    def place(p, block, dy=1):
        put(p[0], fy + dy, p[1], block)
        used.add(p)

    # floor finish: border ring in trim, the rest stays as laid
    for p in cells:
        if _face_in(p, cells):
            put(p[0], fy, p[1], K["trim"])
    # ceiling lights: a glow block in the ceiling every 4-5 cells (lights the whole room, hidden in the slab)
    for (x, z) in cells:
        if x % 5 == 2 and z % 5 == 2:
            put(x, cy, z, K["glow"])
            if kit == "hextech" and h >= 4:  # v17: visible lit fixture under the ceiling: chain + hanging lantern
                put(x, cy - 1, z, "minecraft:lantern[hanging=true]")

    if kind == "living":
        seq = ["bed", "nightstand", "wardrobe", "drawer", "chest", "gap",
               "counter", "sink", "counter", "smoker", "furnace", "gap", "bookshelf", "chest", "drawer"]
        i = 0
        for p in edge:
            if p in used:
                continue
            f = _face_in(p, cells)
            item = seq[i % len(seq)]
            i += 1
            if item == "bed":
                dx, dz = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[f]
                foot = (p[0] + dx, p[1] + dz)
                if foot in cells and foot not in keep and foot not in used:
                    place(p, f"minecraft:{col}_bed[facing={_opp(f)},part=head]")
                    place(foot, f"minecraft:{col}_bed[facing={_opp(f)},part=foot]")
                continue
            if item == "gap":
                continue
            block = {"nightstand": fur("end_table"), "wardrobe": f"{fur('wardrobe')}[facing={f}]",
                     "drawer": f"{fur('drawer')}[facing={f}]", "chest": f"minecraft:chest[facing={f}]",
                     "counter": f"{fur('counter')}[facing={f}]", "sink": f"{fur('kitchen_sink')}[facing={f}]",
                     "smoker": f"minecraft:smoker[facing={f}]", "furnace": f"minecraft:furnace[facing={f}]",
                     "bookshelf": f"{fur('bookshelf')}[facing={f}]"}[item]
            place(p, block)
            if item in ("counter", "sink"):  # wall cabinet above the kitchen run
                place(p, f"{fur('kitchen_cabinet')}[facing={f}]", dy=3)
        _table_set(centre, cells, used, keep, place, fur, col, put, fy)
    elif kind == "workshop":
        seq = ["crafting_table", "barrel", "barrel", "furnace", "blast_furnace", "gap", "smithing_table", "grindstone",
               "stonecutter", "chest", "chest", "gap", "loom", "cartography_table", "barrel", "anvil"]
        anvils = 0
        for i, p in enumerate(edge):
            item = seq[i % len(seq)]
            f = _face_in(p, cells)
            if item == "gap":
                continue
            if item == "anvil":
                if anvils:
                    continue
                anvils += 1
            facing = f if item in ("barrel", "furnace", "blast_furnace", "chest", "stonecutter", "anvil") else None
            block = f"minecraft:{item}" + (f"[facing={f}]" if facing else "")
            if item == "grindstone":
                block = f"minecraft:grindstone[face=floor,facing={f}]"
            place(p, block)
        # work island: counters with a crafting table in the middle
        isl = [p for p in centre if p not in used][:6]
        for j, p in enumerate(isl):
            place(p, "minecraft:crafting_table" if j == len(isl) // 2 else f"{fur('counter')}[facing=north]")
    elif kind == "storage":
        for p in edge:
            f = _face_in(p, cells)
            for dy in (1, 2, 3):
                if dy <= h:
                    place(p, f"minecraft:barrel[facing={f}]", dy)
        # back-to-back shelf rows off the spine, with 2-wide aisles
        for p in centre:
            if p in used:
                continue
            if (p[0] + p[1]) % 4 == 0:
                for dy in (1, 2):
                    place(p, "minecraft:barrel[facing=up]", dy)
    elif kind == "machine_hall":
        # 3x3 machine pads (trim border, base centre) on a 5-cell grid either side of the spine; aisles stay clear
        for (x, z) in centre:
            if (x, z) in keep:
                continue
            gx, gz = x % 5, z % 5
            if gx in (0, 1, 2) and gz in (0, 1, 2):
                put(x, fy, z, K["detail"] if (gx, gz) == (1, 1) else K["trim"])
        # glow strip down the spine floor, cable tray (girder) along the ceiling over it
        sp = spine & cells
        if sp:
            xs = sorted({x for x, _ in sp}); zs = sorted({z for _, z in sp})
            along_x = len(xs) >= len(zs)
            mid = zs[len(zs) // 2] if along_x else xs[len(xs) // 2]
            for (x, z) in sp:
                if (z if along_x else x) == mid and (x if along_x else z) % 2 == 0:
                    put(x, fy, z, K["glow"])
        for (x, z) in spine & cells:
            put(x, cy - 1, z, "create:metal_girder") if (x + z) % 2 == 0 else None
    elif kind == "expansion":
        # empty, marked bay: hazard border, cable stub at the wall, nothing else
        for p in cells:
            if _face_in(p, cells):
                put(p[0], fy, p[1], "chipped:hazard_yellow_concrete")
        if edge:
            p = edge[len(edge) // 2]
            place(p, "create:metal_girder", 1)
    elif kind == "lab":
        seq = ["desk", "chair", "bookshelf", "lectern", "desk", "chair", "gap", "brewing", "bookshelf", "gap"]
        for i, p in enumerate(edge):
            item = seq[i % len(seq)]
            f = _face_in(p, cells)
            if item == "gap":
                continue
            block = {"desk": f"{fur('desk')}[facing={ {'south': 'north', 'west': 'east'}.get(f, f)}]", "chair": f"{fur('chair')}[facing={_opp(f)}]",
                     "bookshelf": f"{fur('bookshelf')}[facing={f}]", "lectern": f"minecraft:lectern[facing={f}]",
                     "brewing": "minecraft:brewing_stand"}[item]
            place(p, block)
        _table_set(centre, cells, used, keep, place, fur, col, put, fy)
    elif kind == "mod_room":
        # one mod (or mod group) per room: big open floor, 5x5 machine pads on an 8-grid with 3-wide aisles,
        # a themed pad material, wall racks of barrels for that mod's buffers, cable tray over the spine
        reg = _registered(theme)
        if reg and reg.pieces:
            _mod_room_registered(reg, cells, centre, edge, keep, fy, h, K, put, used, place, seed)
        else:
            pad, mid = MOD_PADS.get(theme, (K["trim"], K["detail"]))
            for (x, z) in centre:
                if (x, z) in keep:
                    continue
                gx, gz = x % 8, z % 8
                if gx in range(5) and gz in range(5):
                    put(x, fy, z, mid if (gx, gz) == (2, 2) else pad)
            for i, p in enumerate(edge):
                if i % 6 in (0, 1):  # buffer racks along the walls, gaps between for wall-mounted machines
                    f = _face_in(p, cells)
                    for dy in (1, 2):
                        if dy <= h:
                            place(p, f"minecraft:barrel[facing={f}]", dy)
        for (x, z) in spine & cells:
            if (x + z) % 2 == 0:
                put(x, cy - 1, z, "create:metal_girder")
    elif kind == "hall":
        # showcase floor: inlay lines leading to the centre (for a multiblock placed later)
        for (x, z) in cells:
            if (x, z) not in keep and (x + z) % 4 == 0 and not _face_in((x, z), cells):
                put(x, fy, z, K["wall2"])
    return used


def _mod_room_registered(reg, cells, centre, edge, keep, fy, h, K, put, used, place, seed):
    """Registered mod room (mods/): 3x3 pads on a 6-grid (3-wide aisles between), a centrepiece on every pad (the mod's
    `pieces`, cycled, offset per room), wall machines along the edges (`wall`, else the single pieces)."""
    pad, mid = reg.pad
    cset, pads = set(centre), []
    for (x, z) in sorted(centre):
        if (x, z) in keep:
            continue
        gx, gz = x % 6, z % 6
        if gx < 3 and gz < 3:
            put(x, fy, z, mid if (gx, gz) == (1, 1) else pad)
            if (gx, gz) == (1, 1):
                pads.append((x, z))
    fp = lambda c: {(c[0] + dx, c[1] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    k = 0
    for c in pads:
        if fp(c) <= cset and not (fp(c) & keep):
            _mod_piece(reg.pieces[(k + seed) % len(reg.pieces)], c[0], c[1], fy, h, put)
            used |= fp(c)
            k += 1
    wall = reg.wall or tuple(p[1] for p in reg.pieces if p[0] == "single")
    for i, p in enumerate(edge):
        if wall and i % 3 != 2 and p not in used:
            for dy in (1, 2 if h >= 3 else 1):
                place(p, wall[(i // 3 + seed) % len(wall)], dy)


def _registered(theme: str):
    """The mods/ registry entry for a mod_room theme, or None (AE2 and unregistered themes keep the generic pads)."""
    try:
        import mods
        return mods.get(theme)
    except ImportError:
        return None


def _mod_piece(piece, cx, cz, fy, h, put):
    """One registry centrepiece on a 5x5 pad, anchored on its centre (cx, cz); see mods/__init__.py for the kinds."""
    kind = piece[0]
    if kind == "single":
        put(cx, fy + 1, cz, piece[1])
    elif kind == "stack":
        for dy in range(1, min(int(piece[2]), h) + 1):
            put(cx, fy + dy, cz, piece[1])
    else:  # cube (3 high, core mid-layer) / tower (n high, optional core column): casing shell, glass faces
        casing, glass = piece[1], piece[2]
        n = 3 if kind == "cube" else max(3, min(int(piece[3]), h))
        core = piece[3] if kind == "cube" else (piece[4] if len(piece) > 4 else None)
        for dy in range(1, n + 1):
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    side = abs(dx) + abs(dz)
                    if side == 0:  # centre column
                        if core and (dy == 2 if kind == "cube" else 1 < dy < n):
                            put(cx, fy + dy, cz, core)
                        elif dy in (1, n):
                            put(cx, fy + dy, cz, casing)
                        continue
                    ring = dy in (1, n) or side == 2
                    put(cx + dx, fy + dy, cz + dz, casing if ring else glass)


def _opp(f):
    return {"north": "south", "south": "north", "east": "west", "west": "east"}[f]


def _table_set(centre, cells, used, keep, place, fur, col, put, fy):
    """Dining table with 4 chairs and a rug under it, in the biggest free patch off the spine."""
    free = set(p for p in centre if p not in used)
    for (x, z) in sorted(free, key=lambda p: (p[0] + p[1]) % 7):
        block = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
        if all(b in free for b in block):
            for b in block:
                put(b[0], fy + 1, b[1], f"minecraft:{col}_carpet")
            place((x, z), fur("table"))
            for (dx, dz), f in DIRS.items():
                c = (x + dx, z + dz)
                place(c, f"{fur('chair')}[facing={_opp(f)}]")
            return


def fit_floor(program, inner_cells: set, fy: int, h: int, K: dict, reserved: set, kit: str = "",
              seed: int = 1, put=None, ceiling_y: int | None = None, wall_block: str | None = None):
    """Split a floor into rooms along the long axis (partition walls with 3-wide doorways on the spine) and fit
    each. program: a kind or a list of kinds. reserved: core/entrance cells left untouched."""
    kinds = [program] if isinstance(program, str) else list(program or [])
    kinds = [k for k in kinds if k.split(":")[0] in KINDS] or []
    if not kinds or len(inner_cells) < 9:
        return
    ax, spine = spine_of(inner_cells)
    segs = split(inner_cells, ax, len(kinds))
    keep = spine | reserved
    for i, (kind, seg) in enumerate(zip(kinds, segs)):
        if i > 0:  # partition wall on the first row of this segment, doorway where it crosses the spine
            key = (lambda p: p[0]) if ax == "x" else (lambda p: p[1])
            first = min(key(p) for p in seg)
            for p in seg:
                if key(p) == first and p not in keep:
                    for dy in range(1, h + 1):
                        put(p[0], fy + dy, p[1], wall_block or K["wall"])
            seg = {p for p in seg if key(p) != first or p in keep}
        fit_room(kind, seg, fy, h, K, keep, spine, kit, seed + i, put, ceiling_y)
