"""Floating-part guard: the architect remembers every cell its ghosts fill (per ghost id, world coordinates) and
drops parts of a new ghost_set that touch nothing: no block of any ghost next to them (6 faces) and not standing
on the ground level of the build. A floating part is a run of boxes/blocks of one call that are connected only to
each other.
"""
from __future__ import annotations

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

    def ground(self) -> int | None:
        ys = [c[1] for s in self.cells.values() for c in s]
        return min(ys) + 1 if ys else None

    def record(self, gid: str, args: dict, replace: bool):
        s = set() if replace else self.cells.get(gid, set())
        for _, _, cells in entries(args):
            if cells:
                s.update(cells)
        self.cells[gid] = s

    def site_bounds(self):
        """Bounding box (lo, hi) of every recorded ghost cell, or None."""
        cs = [c for s in self.cells.values() for c in s]
        if not cs:
            return None
        return [min(c[i] for c in cs) for i in range(3)], [max(c[i] for c in cs) for i in range(3)]

    def localize(self, gid: str, args: dict, margin: int = 80) -> dict:
        """Stray-block guard: a model-written ghost_set sometimes lands near world origin (forgotten/wrong origin).
        Entries farther than `margin` blocks (x/z) from the site are dropped; if EVERY entry is far and the origin is
        missing/near 0,0,0 the whole call is translated onto the site's south-west corner instead. Logs a line."""
        sb = self.site_bounds()
        if not sb or not (args.get("blocks") or args.get("boxes")):
            return args
        lo, hi = sb

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
