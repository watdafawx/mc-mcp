"""Floating-part guard: the architect remembers every cell its ghosts fill (per ghost id, world coordinates) and
drops parts of a new ghost_set that touch nothing: no block of any ghost next to them (6 faces) and not standing
on the ground level of the build. A floating part is a run of boxes/blocks of one call that are connected only to
each other.
"""
from __future__ import annotations

import re

AIR = {"minecraft:air", "air", "minecraft:cave_air", "minecraft:void_air"}
BIG = 250_000  # boxes bigger than this are never expanded (treated as supported, never floating)
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _state(key, pal):
    s = pal.get(key, key) if isinstance(pal, dict) else key
    return s if isinstance(s, str) else str(s)


def entries(args: dict):
    """Yield (kind, index, cells) per box/block entry of a ghost_set call, cells in world coordinates.
    cells is None for an entry too big to expand."""
    ox, oy, oz = args.get("origin") or (0, 0, 0)
    pal = args.get("palette") or {}
    for i, b in enumerate(args.get("boxes") or []):
        if len(b) < 7 or _state(b[6], pal).split("[")[0] in AIR:
            continue
        x1, y1, z1, x2, y2, z2 = (int(v) for v in b[:6])
        x1, x2 = sorted((x1, x2)); y1, y2 = sorted((y1, y2)); z1, z2 = sorted((z1, z2))
        vol = (x2 - x1 + 1) * (y2 - y1 + 1) * (z2 - z1 + 1)
        if vol > BIG:
            yield "boxes", i, None
            continue
        yield "boxes", i, [(ox + x, oy + y, oz + z) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1)
                           for z in range(z1, z2 + 1)]
    for i, b in enumerate(args.get("blocks") or []):
        if len(b) < 4 or _state(b[3], pal).split("[")[0] in AIR:
            continue
        yield "blocks", i, [(ox + int(b[0]), oy + int(b[1]), oz + int(b[2]))]


class Guard:
    def __init__(self):
        self.cells: dict[str, set] = {}  # ghost id -> filled world cells
        self.campus_ids: set[str] = set()  # ghosts the procedural campus generated (the site footprint)
        self.last_reject: str | None = None
        self.last_note: str | None = None  # v17: set when a stray ghost was translated into its campus room
        self.origins: dict[str, list] = {}  # last explicit origin per ghost id
        self.wings: dict[str, dict] = {}  # v17: campus wing/hub ghosts: {id, lo, hi, floor_y, rooms}

    def add_wing(self, gid, lo, hi, floor_y, rooms=None, kind="wing"):
        self.wings[gid] = {"id": gid, "lo": list(lo), "hi": list(hi), "floor_y": floor_y, "rooms": list(rooms or []), "kind": kind}

    @staticmethod
    def _label(r):
        return str(r.get("name") or r.get("room") or r) if isinstance(r, dict) else str(r)

    def room_slots(self, wing: dict) -> list[dict]:
        """Interior split of a wing into one slot per listed room (along the longer axis)."""
        lo, hi = wing["lo"], wing["hi"]
        x0, x1, z0, z1 = lo[0] + 2, hi[0] - 2, lo[2] + 2, hi[2] - 2
        rooms = wing["rooms"] or ["room"]
        n = len(rooms)
        out = []
        along_x = (x1 - x0) >= (z1 - z0)
        for k, r in enumerate(rooms):
            if along_x:
                a = x0 + (x1 - x0 + 1) * k // n
                b = x0 + (x1 - x0 + 1) * (k + 1) // n - 2
                bx0, bx1, bz0, bz1 = a, max(a, b), z0, z1
            else:
                a = z0 + (z1 - z0 + 1) * k // n
                b = z0 + (z1 - z0 + 1) * (k + 1) // n - 2
                bx0, bx1, bz0, bz1 = x0, x1, a, max(a, b)
            out.append({"room": self._label(r), "origin": [bx0, wing["floor_y"], bz0],
                        "max_size": [bx1 - bx0 + 1, 12, bz1 - bz0 + 1], "wing": wing["id"]})
        return out

    def _match_slot(self, gid: str):
        """Best campus room slot for a model ghost id, by word overlap (ae2_storage -> 'ae2 storage room')."""
        toks = [t for t in re.split(r"[^a-z0-9]+", gid.split("/", 1)[-1].lower()) if len(t) >= 3]
        best, bs = None, 0
        for w in self.wings.values():
            if w["kind"] == "hub":
                continue
            wname = w["id"].split("/")[-1].lower()
            for sl in self.room_slots(w):
                lab = sl["room"].lower()
                sc = sum(2 for t in toks if t in lab or any(len(u) >= 4 and u in t for u in re.split(r"[^a-z0-9]+", lab)))
                sc += sum(1 for t in toks if t in wname)
                if sc > bs:
                    best, bs = sl, sc
        return best if bs >= 2 else None

    def retarget(self, gid: str, args: dict, allc: list, bbox):
        """v17: a ghost the footprint guard would drop. Try (a) absolute coords + origin (double offset), (b) moving it into
        the matching campus room. Returns (new_args | None, message)."""
        bx0, bx1, bz0, bz1, by0 = bbox
        ox, oy, oz = (int(v) for v in (args.get("origin") or (0, 0, 0)))
        cb = self.site_bounds(campus_only=True)

        def inside(x0, x1, z0, z1):
            ix = max(0, min(x1, cb[1][0] + 8) - max(x0, cb[0][0] - 8) + 1)
            iz = max(0, min(z1, cb[1][2] + 8) - max(z0, cb[0][2] - 8) + 1)
            return ix * iz / max(1, (x1 - x0 + 1) * (z1 - z0 + 1))
        if (ox or oz) and inside(bx0 - ox, bx1 - ox, bz0 - oz, bz1 - oz) >= 0.5:  # blocks were already world coords
            out = dict(args, origin=[0, 0, 0])
            return out, (f"ghost {gid}: your blocks were WORLD coordinates but you also set origin {[ox, oy, oz]}; origin forced to "
                         f"[0,0,0] so it sits on the site. Use EITHER world coords with origin [0,0,0] OR local coords with the origin.")
        sl = self._match_slot(gid)
        sx, sz = bx1 - bx0 + 1, bz1 - bz0 + 1
        if sl is None:
            return None, (f"ghost {gid} rejected: its footprint ({bx0},{bz0})-({bx1},{bz1}) is off the campus "
                          f"({cb[0][0]},{cb[0][2]})-({cb[1][0]},{cb[1][2]}). Use the origins the campus call gave: room origins "
                          f"{[(w['id'], self.room_slots(w)[0]['origin']) for w in list(self.wings.values())[:6]]}; local coords from 0,0,0.")
        mx, _, mz = sl["max_size"]
        if sx > mx + 6 or sz > mz + 6:
            return None, (f"ghost {gid} rejected: it is {sx}x{sz} blocks but room '{sl['room']}' in {sl['wing']} has an interior of "
                          f"{mx}x{mz}. Retry with origin {sl['origin']} (world coords of the room's min corner, y = floor) and local "
                          f"coords inside 0..{mx - 1} x 0..11 x 0..{mz - 1}; keep aisles clear.")
        nx, ny, nz = sl["origin"]
        out = dict(args, origin=[ox + nx - bx0, oy + ny - by0, oz + nz - bz0])
        return out, (f"ghost {gid} was ~{abs(bx0 - nx) + abs(bz0 - nz)} blocks off the campus; MOVED into room '{sl['room']}' of "
                     f"{sl['wing']}: new origin {out['origin']} (room min corner {sl['origin']}, interior {mx}x{mz}). "
                     f"Next time use origin {sl['origin']} with local coords from 0,0,0.")

    def ground(self) -> int | None:
        ys = [c[1] for s in self.cells.values() for c in s]
        return min(ys) + 1 if ys else None

    def record(self, gid: str, args: dict, replace: bool):
        s = set() if replace else self.cells.get(gid, set())
        for _, _, cells in entries(args):
            if cells:
                s.update(cells)
        self.cells[gid] = s
        if args.get("origin") is not None:
            self.origins[gid] = list(args["origin"])

    def site_bounds(self, campus_only: bool = False):
        """Bounding box (lo, hi) of every recorded ghost cell (campus ghosts only when asked and any exist), or None."""
        src = [s for k, s in self.cells.items() if k in self.campus_ids] if campus_only and self.campus_ids else list(self.cells.values())
        cs = [c for s in src for c in s]
        if not cs:
            return None
        return [min(c[i] for c in cs) for i in range(3)], [max(c[i] for c in cs) for i in range(3)]

    def localize(self, gid: str, args: dict, margin: int = 80) -> dict:
        """Stray-block guard: a model-written ghost_set sometimes lands near world origin (forgotten/wrong origin).
        Entries farther than `margin` blocks (x/z) from the site are dropped; if EVERY entry is far and the origin is
        missing/near 0,0,0 the whole call is translated onto the site's south-west corner instead. Logs a line."""
        self.last_reject = None
        self.last_note = None
        if args.get("origin") is None and gid in self.origins and (args.get("blocks") or args.get("boxes")):
            args = dict(args, origin=self.origins[gid])  # merge call that relies on the ghost's earlier origin
            self.last_note = f"ghost {gid}: no origin given, reused its earlier origin {self.origins[gid]} (always pass origin)"
        sb = self.site_bounds()
        if not sb or not (args.get("blocks") or args.get("boxes")):
            return args
        lo, hi = sb
        # v16 footprint rule: a model ghost whose x/z bounding box lies mostly outside the campus footprint is rejected whole
        cb = self.site_bounds(campus_only=True)
        allc = [c for _, _, cs in entries(args) if cs for c in cs]
        if cb and allc:
            pad = 8
            bx0, bx1 = min(c[0] for c in allc), max(c[0] for c in allc)
            bz0, bz1 = min(c[2] for c in allc), max(c[2] for c in allc)
            ix = max(0, min(bx1, cb[1][0] + pad) - max(bx0, cb[0][0] - pad) + 1)
            iz = max(0, min(bz1, cb[1][2] + pad) - max(bz0, cb[0][2] - pad) + 1)
            frac = (ix * iz) / max(1, (bx1 - bx0 + 1) * (bz1 - bz0 + 1))
            if frac < 0.5:
                new, msg = self.retarget(gid, args, allc, (bx0, bx1, bz0, bz1, min(c[1] for c in allc)))
                if new is not None:
                    self.last_note = msg
                    print(f"  [retarget] {msg}", flush=True)
                    return new
                self.last_reject = msg
                print(f"  [footprint] {self.last_reject}", flush=True)
                return dict(args, blocks=[], boxes=[])

        def far(c):
            return c[0] < lo[0] - margin or c[0] > hi[0] + margin or c[2] < lo[2] - margin or c[2] > hi[2] + margin
        ents = [(k, i, cs) for k, i, cs in entries(args) if cs]
        bad = {(k, i) for k, i, cs in ents if far(cs[len(cs) // 2])}
        if not bad:
            return args
        ox, oy, oz = args.get("origin") or (0, 0, 0)
        if len(bad) == len(ents) and abs(ox) + abs(oz) < 200:
            sx = lo[0] - min(c[0] for _, _, cs in ents for c in cs)
            sz = lo[2] - min(c[2] for _, _, cs in ents for c in cs)
            out = dict(args, origin=[ox + sx, oy, oz + sz])
            print(f"  [stray] {gid}: {len(ents)} entries near world origin, translated by ({sx},0,{sz}) onto the site", flush=True)
            return out
        out = dict(args)
        for kind in ("boxes", "blocks"):
            if args.get(kind):
                out[kind] = [e for i, e in enumerate(args[kind]) if (kind, i) not in bad]
        print(f"  [stray] {gid}: dropped {len(bad)} entries > {margin} blocks from the site", flush=True)
        return out

    def check(self, gid: str, args: dict) -> tuple[dict, list]:
        """Returns (args without floating entries, [floating part summaries])."""
        args = self.localize(gid, args)
        if self.last_reject:
            return args, [{"rejected": self.last_reject, "blocks": 0}]
        replace = args.get("mode", "replace") == "replace"
        others = set()
        for k, s in self.cells.items():
            if k != gid or not replace:
                others |= s
        ground = self.ground()
        if not others or ground is None:
            return args, []
        ents = list(entries(args))
        owner = {}  # cell -> entry index in ents
        for j, (_, _, cells) in enumerate(ents):
            for c in cells or ():
                owner.setdefault(c, j)
        # union entries that touch each other
        parent = list(range(len(ents)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for c, j in owner.items():
            for d in N6:
                k = owner.get((c[0] + d[0], c[1] + d[1], c[2] + d[2]))
                if k is not None and find(k) != find(j):
                    parent[find(k)] = find(j)
        supported = set()
        for j, (_, _, cells) in enumerate(ents):
            if cells is None:
                supported.add(find(j))
                continue
            for c in cells:
                if c[1] <= ground or any((c[0] + d[0], c[1] + d[1], c[2] + d[2]) in others for d in N6):
                    supported.add(find(j))
                    break
        groups: dict[int, list] = {}
        for j in range(len(ents)):
            if find(j) not in supported:
                groups.setdefault(find(j), []).append(j)
        if not groups:
            return args, []
        # snap: slide a floating group straight down until it touches a building or the ground (max 40); else drop it
        snap, snapped = {}, []
        for js in groups.values():
            cs = [c for j in js if ents[j][2] for c in ents[j][2]]
            for dy in range(1, 41):
                if any(c[1] - dy <= ground or any((c[0] + d[0], c[1] - dy + d[1], c[2] + d[2]) in others for d in N6)
                       for c in cs):
                    for j in js:
                        snap[(ents[j][0], ents[j][1])] = dy
                    snapped.append({"blocks": len(cs), "snapped_down": dy})
                    break
        drop = {(ents[j][0], ents[j][1]) for js in groups.values() for j in js} - set(snap)
        out = dict(args)
        for kind in ("boxes", "blocks"):
            if args.get(kind):
                lst = []
                for i, e in enumerate(args[kind]):
                    if (kind, i) in drop:
                        continue
                    dy = snap.get((kind, i), 0)
                    if dy:
                        e = list(e)
                        if kind == "boxes":
                            e[1] -= dy; e[4] -= dy
                        else:
                            e[1] -= dy
                    lst.append(e)
                out[kind] = lst
        parts = []
        for js in groups.values():
            if all((ents[j][0], ents[j][1]) in snap for j in js):
                continue
            cs = [c for j in js for c in ents[j][2]]
            lo = [min(c[i] for c in cs) for i in range(3)]
            hi = [max(c[i] for c in cs) for i in range(3)]
            part = {"blocks": len(cs), "min": lo, "max": hi}
            if others:  # where the nearest existing block is, and how far to move the part to touch it
                mid = cs[len(cs) // 2]
                nb = min(others, key=lambda o: abs(o[0] - mid[0]) + abs(o[1] - mid[1]) + abs(o[2] - mid[2]))
                part["nearest_building_block"] = list(nb)
                part["move_by_approx"] = [nb[i] - mid[i] for i in range(3)]
            parts.append(part)
        return out, parts + [dict(s, note='floating part snapped down to touch the building') for s in snapped]


# ---------------------------------------------------------------------------------------- hextech no-gold filter
import re as _re

_GOLDY = _re.compile(r"(gold|yellow|honey|brass_block|glowstone|amber|sunstone|sols_block)")


def _gold_swap(state):
    """Return a quartz/purple/cyan equivalent for a gold/yellow block state, or the state unchanged."""
    if not isinstance(state, str):
        return state
    base, _, props = state.partition("[")
    path = base.split(":")[-1]
    if not _GOLDY.search(path) or "golden_" in path and "gold_block" not in path and "gold_" not in path:
        return state
    suf = "[" + props if props else ""
    if "glass_pane" in path:
        return "minecraft:purple_stained_glass_pane" + suf
    if "glass" in path:
        return "minecraft:purple_stained_glass"
    if "concrete" in path:
        return "minecraft:purple_concrete"
    if "terracotta" in path:
        return "minecraft:purple_terracotta" + suf
    if "wool" in path or "carpet" in path:
        return "minecraft:purple_" + ("carpet" if "carpet" in path else "wool")
    if path in ("glowstone",) or "light" in path or "lamp" in path or "lantern" in path:
        return "luminax:light_blue_luminax_block"
    for kind, rep in (("stairs", "minecraft:quartz_stairs"), ("slab", "minecraft:quartz_slab"),
                      ("wall", "minecraft:diorite_wall"), ("pillar", "minecraft:quartz_pillar")):
        if path.endswith(kind):
            return rep + suf
    if "bars" in path or "chain" in path or "rod" in path:
        return "minecraft:iron_bars" if "bars" in path else "minecraft:lightning_rod"
    if "ore" in path or "raw_" in path:
        return "minecraft:smooth_quartz"
    return "minecraft:quartz_block" if "block" in path else "minecraft:smooth_quartz"


def swap_gold(args: dict) -> tuple[dict, int]:
    """Hextech has no gold: swap gold/yellow blocks in a ghost_set call for quartz/purple/cyan equivalents.
    Returns (new args, number of swapped entries)."""
    n = 0
    out = dict(args)
    pal = args.get("palette")
    if isinstance(pal, dict):
        newp = {}
        for k, v in pal.items():
            nv = _gold_swap(v)
            n += nv != v
            newp[k] = nv
        out["palette"] = newp
    for kind, idx in (("blocks", 3), ("boxes", 6)):
        lst = args.get(kind)
        if lst:
            new = []
            for e in lst:
                if len(e) > idx and isinstance(e[idx], str):
                    ns = _gold_swap(e[idx])
                    if ns != e[idx]:
                        e = list(e); e[idx] = ns; n += 1
                new.append(e)
            out[kind] = new
    return out, n
