"""Post-build sanity helpers for the architect (pure python, no Minecraft or API needed, deterministic).

They run on the ghosts a `--prompt` / reference build has already placed, before/while it is viewed:

    proportion_check(plan, ghosts)
        Compares the build's real world bounding box with the footprint / proportions the plan promised
        (a reference brief or an explicit target size) and returns short warning strings. Call it right before
        view(): a build that is 8 wide where the reference wanted 20, or a 10x10x2 pancake, still looks fine in
        the ghost list but nothing like the reference.

    local_foundation(blocks, origin, ground_fn)
        Same idea as site.apply() but for ONE structure/component: keeps the base on the surveyed ground by
        filling a stone-brick retaining wall along the footprint edge and cobblestone pillars on a 4-block grid
        inside it. Only columns near the structure's base count as footprint, so balconies and overhangs high
        up never grow stilts.

    python postcheck.py demo

Both helpers are pure: no world access. The caller passes the `ghost_list` entries and a `ground_fn(x, z)`.
"""
from __future__ import annotations

import re

WALL_BLOCK = "minecraft:stone_bricks"      # retaining wall / plinth (same as site.FOUND_EDGE)
PILLAR_BLOCK = "minecraft:cobblestone"     # cheap support columns (same as site.FOUND_PILLAR)
MAX_DEPTH = 16
AIR = {"air", "cave_air", "void_air", "minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
FOOTPRINT_SLACK = 2      # a column belongs to the footprint when it starts within this many blocks of the base
RATIO_TOL = 0.35         # aspect-ratio mismatch worth warning about
SCALE_TOL = 0.45         # per-axis scale mismatch worth warning about


# ---------------------------------------------------------------- proportion check

_SEP = r"(?:x|×|X|\*|by)"
_TRIPLE = re.compile(r"(\d{1,4})\s*" + _SEP + r"\s*(\d{1,4})\s*" + _SEP + r"\s*(\d{1,4})", re.I)
_PAIR = re.compile(r"(\d{1,4})\s*" + _SEP + r"\s*(\d{1,4})", re.I)
_KW = re.compile(r"\b(width|wide|height|tall|depth|deep)\b\D{0,14}?(\d{1,4})", re.I)
_KW_AXIS = {"width": "w", "wide": "w", "height": "h", "tall": "h", "depth": "d", "deep": "d"}
_AXIS_KEYS = {
    "w": "w", "width": "w", "wide": "w", "size_x": "w", "footprint_w": "w", "x_size": "w",
    "h": "h", "height": "h", "tall": "h", "size_y": "h", "levels": "h", "storeys": "h", "stories": "h",
    "d": "d", "depth": "d", "deep": "d", "size_z": "d", "footprint_d": "d", "z_size": "d",
    "length": "d", "long": "d",
}
_CONTAINER_KEYS = {"footprint", "size", "dims", "dimensions", "proportions", "target_size", "massing_size"}


def _int(v) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return 0
    return n if 0 < n <= 2048 else 0


def _dims_from(value, out: dict | None = None) -> dict:
    """Read w/h/d (blocks) out of a string ("20x15", "20 x 15 x 12"), a dict or a [w, h, d] / [w, d] list."""
    out = {} if out is None else out
    if value is None or isinstance(value, bool):
        return out
    if isinstance(value, str):
        m = _TRIPLE.search(value)
        if m:
            out.setdefault("w", int(m.group(1)))
            out.setdefault("d", int(m.group(2)))
            out.setdefault("h", int(m.group(3)))
        else:
            m = _PAIR.search(value)
            if m:
                out.setdefault("w", int(m.group(1)))
                out.setdefault("d", int(m.group(2)))
        for kw, num in _KW.findall(value):
            axis = _KW_AXIS.get(kw.lower())
            if axis:
                out.setdefault(axis, int(num))
        return out
    if isinstance(value, dict):
        for key, v in value.items():
            k = str(key).strip().lower()
            axis = _AXIS_KEYS.get(k)
            if axis:
                n = _int(v)
                if n:
                    out.setdefault(axis, n)
            elif k in _CONTAINER_KEYS:
                _dims_from(v, out)
        return out
    if isinstance(value, (list, tuple)):
        # [w, h, d] as used by target_size; a 2-number list is a footprint [w, d]
        nums = [n for n in value if isinstance(n, (int, float)) and not isinstance(n, bool)]
        if len(nums) == len(value) == 3:
            out.setdefault("w", int(nums[0]))
            out.setdefault("h", int(nums[1]))
            out.setdefault("d", int(nums[2]))
        elif len(nums) == len(value) == 2:
            out.setdefault("w", int(nums[0]))
            out.setdefault("d", int(nums[1]))
        return out
    return out


def expected_dims(plan: dict) -> dict:
    """{w/h/d} the plan asks for, from plan['reference'] (brief text or dict) and plan['size'/'target_size']."""
    out: dict = {}
    if not isinstance(plan, dict):
        return out
    ref = plan.get("reference")
    if isinstance(ref, (str, dict, list, tuple)):
        _dims_from(ref, out)
    for key in ("target_size", "size", "dims", "dimensions", "footprint", "proportions"):
        if key in plan:
            _dims_from(plan[key], out)
    return out


def ghost_bounds(ghosts: list) -> tuple[list | None, list | None]:
    """Combined [x, y, z] min/max of the ghosts that have world bounds, ignoring the auto-foundation ghost."""
    lo = hi = None
    for g in ghosts or []:
        if not isinstance(g, dict) or "world_min" not in g or "world_max" not in g:
            continue
        gid = str(g.get("id") or "")
        if gid == "foundation" or gid.endswith("/foundation"):
            continue
        try:
            a = [int(v) for v in g["world_min"]]
            b = [int(v) for v in g["world_max"]]
        except (TypeError, ValueError):
            continue
        if len(a) < 3 or len(b) < 3:
            continue
        lo = a[:3] if lo is None else [min(lo[i], a[i]) for i in range(3)]
        hi = b[:3] if hi is None else [max(hi[i], b[i]) for i in range(3)]
    return lo, hi


def proportion_check(plan: dict, ghosts: list) -> list[str]:
    """Warning strings when the built ghosts do not match the plan's footprint/proportions ([] when fine).

    `ghosts` is the `ghost_list` output; only entries with world_min/world_max count and the auto-foundation ghost
    is ignored. With no expected dimensions in the plan only degenerate builds (e.g. a 10x10x2 pancake) warn.
    """
    lo, hi = ghost_bounds(ghosts)
    if lo is None:
        return []
    W, H, D = (hi[i] - lo[i] + 1 for i in range(3))
    out: list[str] = []
    if H <= 2 and W >= 6 and D >= 6:
        out.append(f"very flat (H={H} on {W}x{D} footprint)")
    pw, ph, pd = (expected_dims(plan).get(a, 0) for a in ("w", "h", "d"))
    for name, act_a, want_a, act_b, want_b in (("H/W", H, ph, W, pw), ("W/D", W, pw, D, pd)):
        if not want_a or not want_b:
            continue
        got, want = act_a / act_b, want_a / want_b
        dev = (got - want) / want
        if abs(dev) > RATIO_TOL:
            what = "squashed" if dev < 0 else "too tall/narrow"
            out.append(f"{what}: {name} is {got:.2f} vs planned {want:.2f}")
    for axis, act, want in (("width", W, pw), ("height", H, ph), ("depth", D, pd)):
        if not want:
            continue
        dev = (act - want) / want
        if abs(dev) > SCALE_TOL:
            out.append(f"{axis} {act} vs planned {want} ({dev * 100:+.0f}%)")
    return out


# ---------------------------------------------------------------- local foundation

def _is_air(state) -> bool:
    if not isinstance(state, str):
        return False
    base = state.split("[", 1)[0].strip().lower()
    return base in AIR or base.split(":")[-1] in ("air", "cave_air", "void_air")


def column_bottoms(blocks: list) -> dict:
    """{(lx, lz): lowest non-air ly} for a ghost's [lx, ly, lz, state] block list."""
    cols: dict = {}
    for b in blocks or []:
        if not isinstance(b, (list, tuple)) or len(b) < 4 or _is_air(b[3]):
            continue
        try:
            lx, ly, lz = int(b[0]), int(b[1]), int(b[2])
        except (TypeError, ValueError):
            continue
        k = (lx, lz)
        if k not in cols or ly < cols[k]:
            cols[k] = ly
    return cols


def local_foundation(blocks: list, origin: tuple, ground_fn, wall_block: str = WALL_BLOCK,
                     pillar_block: str = PILLAR_BLOCK, max_depth: int = MAX_DEPTH) -> list:
    """Foundation blocks ([lx, ly, lz, state], local to `origin`) that carry a structure's base down to the ground.

    `ground_fn(wx, wz)` -> top solid ground world y, or None (unknown / water / unloaded: that column is skipped).
    Only columns within FOOTPRINT_SLACK blocks of the lowest block take part, so a balcony or overhang high above
    the base is never given stilts. A footprint column standing above ground gets, from the ground up:
    `wall_block` on the footprint edge (4-neighbour rule) and `pillar_block` on a 4-block interior grid.

    The fill always starts one block above the ground, so every returned column touches the ground; a gap deeper
    than `max_depth` yields a shorter pier instead of a block hover. Returns [] on flat ground.
    """
    ox, oy, oz = (int(v) for v in origin)
    cols = column_bottoms(blocks)
    if not cols:
        return []
    depth_cap = max(0, int(max_depth))
    base_y = min(cols.values())
    foot = {k for k, y in cols.items() if y <= base_y + FOOTPRINT_SLACK}
    out = []
    for lx, lz in sorted(foot):
        world_base_y = oy + cols[(lx, lz)]
        g = ground_fn(ox + lx, oz + lz)
        if g is None:
            continue
        g = int(g)
        gap = world_base_y - 1 - g
        if gap < 1:
            continue  # already touching the ground (or dug in): nothing to add
        edge = any((lx + dx, lz + dz) not in foot for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if not (edge or (lx % 4 == 0 and lz % 4 == 0)):
            continue
        state = wall_block if edge else pillar_block
        for wy in range(g + 1, g + 1 + min(gap, depth_cap)):
            out.append([lx, wy - oy, lz, state])
    return out


# ---------------------------------------------------------------- cli

def demo() -> None:
    """Tiny smoke run: python postcheck.py demo"""
    ghosts = [{"id": "demo/tower", "world_min": [100, 64, 200], "world_max": [109, 73, 209], "blocks": []}]
    plan = {"reference": {"footprint": "20x15", "height": 12}}
    print("proportions:", proportion_check(plan, ghosts) or "ok")
    slab = [[lx, 0, lz, WALL_BLOCK] for lx in range(4) for lz in range(4)]
    found = local_foundation(slab, (0, 64, 0), lambda x, z: 63 - max(0, x))
    print(f"local foundation: {len(found)} blocks, first {found[:2]}")
    print("flat ground:", local_foundation(slab, (0, 64, 0), lambda x, z: 63) or "none")


if __name__ == "__main__":
    demo()
