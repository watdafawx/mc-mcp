"""Palette engine: texture pass for every ghost_set (step 1 of the quality plan).

Good builds never use one block per role. A wall of stone_bricks is a mix of stone/cracked/mossy bricks, slightly
darker at the bottom and lighter at the top, with small clusters instead of pure speckle. This module does that to any
ghost_set call, after the fact, so every generator (campus, massing, shapes, the LLM's own boxes) gets it for free:

- RAMPS maps a base block to a weighted family of blocks of the same look. Members are sorted dark -> light by their
  blocklib colour, so the choice can follow a vertical gradient.
- A block's pick = smooth 3D value noise (clusters) + per-block jitter + height gradient, mapped through the weights,
  so the base block keeps ~60% and the rest are shades.
- Stairs, slabs and walls follow their family: stone_brick_stairs can become mossy_stone_brick_stairs with the same
  facing/half/shape (only when that variant exists in blocklib).
- Boxes stay as they are; their visible surface cells (the cells each textured box still owns after all boxes of the
  call are applied) are added as single blocks before the call's own blocks, so explicit blocks still win.

Deterministic: same ghost id + same coordinates = same result. Disable with env ARCHITECT_TEXTURE=0.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
_LIB: dict | None = None

# base block -> [(member, weight)]. The base itself should carry the biggest weight. Order does not matter (sorted by
# luminance at load). Every member is a cheap survival block in ATM10 (see blocklib cost).
RAMPS: dict[str, list[tuple[str, int]]] = {
    "minecraft:stone_bricks": [("minecraft:stone_bricks", 6), ("minecraft:cracked_stone_bricks", 2),
                               ("minecraft:mossy_stone_bricks", 1), ("minecraft:stone", 1)],
    "minecraft:mossy_stone_bricks": [("minecraft:mossy_stone_bricks", 5), ("minecraft:stone_bricks", 2),
                                     ("minecraft:cracked_stone_bricks", 1), ("minecraft:mossy_cobblestone", 1)],
    "minecraft:cobblestone": [("minecraft:cobblestone", 6), ("minecraft:mossy_cobblestone", 2), ("minecraft:andesite", 1)],
    "minecraft:andesite": [("minecraft:andesite", 5), ("minecraft:polished_andesite", 2), ("minecraft:stone", 1),
                           ("minecraft:cobblestone", 1)],
    "minecraft:polished_andesite": [("minecraft:polished_andesite", 6), ("create:polished_cut_andesite", 2),
                                    ("minecraft:andesite", 1), ("minecraft:stone", 1)],
    "minecraft:tuff_bricks": [("minecraft:tuff_bricks", 6), ("minecraft:polished_tuff", 2), ("minecraft:tuff", 1)],
    "minecraft:deepslate_bricks": [("minecraft:deepslate_bricks", 6), ("minecraft:cracked_deepslate_bricks", 2),
                                   ("minecraft:polished_deepslate", 1), ("minecraft:cobbled_deepslate", 1)],
    "minecraft:deepslate_tiles": [("minecraft:deepslate_tiles", 6), ("minecraft:cracked_deepslate_tiles", 2),
                                  ("minecraft:deepslate_bricks", 1)],
    "minecraft:polished_deepslate": [("minecraft:polished_deepslate", 6), ("minecraft:deepslate_tiles", 1),
                                     ("minecraft:cobbled_deepslate", 1), ("minecraft:deepslate_bricks", 1)],
    "minecraft:cobbled_deepslate": [("minecraft:cobbled_deepslate", 6), ("minecraft:polished_deepslate", 1),
                                    ("minecraft:deepslate_bricks", 1)],
    "minecraft:polished_blackstone_bricks": [("minecraft:polished_blackstone_bricks", 6),
                                             ("minecraft:cracked_polished_blackstone_bricks", 2),
                                             ("minecraft:polished_blackstone", 1), ("minecraft:blackstone", 1)],
    "minecraft:polished_blackstone": [("minecraft:polished_blackstone", 6), ("minecraft:polished_blackstone_bricks", 2),
                                      ("minecraft:blackstone", 1)],
    "minecraft:bricks": [("minecraft:bricks", 6), ("minecraft:granite", 1), ("minecraft:terracotta", 1),
                         ("minecraft:polished_granite", 1)],
    "minecraft:mud_bricks": [("minecraft:mud_bricks", 6), ("minecraft:packed_mud", 2)],
    "minecraft:quartz_bricks": [("minecraft:quartz_bricks", 6), ("minecraft:smooth_quartz", 2), ("minecraft:calcite", 1),
                                ("create:polished_cut_calcite", 1)],
    "minecraft:smooth_quartz": [("minecraft:smooth_quartz", 6), ("minecraft:quartz_bricks", 2), ("minecraft:calcite", 1)],
    "minecraft:white_concrete": [("minecraft:white_concrete", 6), ("chisel:large_tile/white_concrete", 1),
                                 ("minecraft:calcite", 1), ("minecraft:white_concrete_powder", 1)],
    "minecraft:light_gray_concrete": [("minecraft:light_gray_concrete", 6), ("minecraft:polished_andesite", 1),
                                      ("minecraft:stone", 1)],
    "minecraft:gray_concrete": [("minecraft:gray_concrete", 6), ("minecraft:polished_deepslate", 1),
                                ("minecraft:deepslate_tiles", 1)],
    "minecraft:smooth_sandstone": [("minecraft:smooth_sandstone", 6), ("minecraft:cut_sandstone", 2),
                                   ("minecraft:sandstone", 1)],
    "minecraft:cut_copper": [("minecraft:cut_copper", 5), ("minecraft:exposed_cut_copper", 2),
                             ("minecraft:weathered_cut_copper", 1)],
    "minecraft:exposed_cut_copper": [("minecraft:exposed_cut_copper", 5), ("minecraft:cut_copper", 1),
                                     ("minecraft:weathered_cut_copper", 2)],
    "minecraft:weathered_cut_copper": [("minecraft:weathered_cut_copper", 5), ("minecraft:exposed_cut_copper", 1),
                                       ("minecraft:oxidized_cut_copper", 2)],
    "minecraft:oxidized_cut_copper": [("minecraft:oxidized_cut_copper", 6), ("minecraft:weathered_cut_copper", 2)],
    "minecraft:spruce_planks": [("minecraft:spruce_planks", 6), ("minecraft:dark_oak_planks", 1)],
    "create:cut_limestone_bricks": [("create:cut_limestone_bricks", 6), ("create:polished_cut_limestone", 2),
                                    ("create:limestone", 1)],
    "create:polished_cut_limestone": [("create:polished_cut_limestone", 6), ("create:cut_limestone_bricks", 2),
                                      ("create:cut_limestone", 1)],
    "ae2:sky_stone_brick": [("ae2:sky_stone_brick", 6), ("ae2:sky_stone_small_brick", 2),
                            ("ae2:smooth_sky_stone_block", 1)],
}

_VARIANTS = ("stairs", "slab", "wall")
_built: dict | None = None  # {"ramp": {base: [(member, cum_weight_frac)]}, "var": {variant_id: (base, kind)}}


def _lib() -> dict:
    global _LIB
    if _LIB is None:
        try:
            _LIB = json.loads((HERE / "knowledge" / "blocklib.json").read_text("utf-8"))
        except (OSError, ValueError):
            _LIB = {}
    return _LIB


def _lum(block: str) -> float:
    c = (_lib().get(block) or {}).get("colour") or ""
    if len(c) == 7 and c.startswith("#"):
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    return 128.0


def variant_id(block: str, kind: str) -> str:
    """stone_bricks + stairs -> stone_brick_stairs, spruce_planks -> spruce_stairs, cut_copper -> cut_copper_stairs."""
    ns, name = block.split(":", 1)
    if name.endswith("_planks"):
        name = name[: -len("_planks")]
    elif name.endswith("bricks") or name.endswith("tiles"):
        name = name[:-1]
    elif name.endswith("_block") and not name.startswith("smooth"):
        name = name[: -len("_block")]
    return f"{ns}:{name}_{kind}"


def _build() -> dict:
    global _built
    if _built is not None:
        return _built
    lib = _lib()
    ramp, var = {}, {}
    for base, members in RAMPS.items():
        ms = [(m, w) for m, w in members if not lib or m in lib]
        if len(ms) < 2:
            continue
        ms.sort(key=lambda mw: _lum(mw[0]))
        tot = float(sum(w for _, w in ms))
        acc, out = 0.0, []
        for m, w in ms:
            acc += w / tot
            out.append((m, acc))
        ramp[base] = out
    # stairs/slab/wall of a ramp base use that base's ramp (stone_brick_stairs -> stone_bricks ramp)
    for base in ramp:
        for k in _VARIANTS:
            v = variant_id(base, k)
            if lib and v in lib:
                var[v] = (base, k)
    _built = {"ramp": ramp, "var": var}
    return _built


# ---------------------------------------------------------------------------------------------------- noise

def _h(*xs: int) -> float:
    """Integer hash -> [0, 1)."""
    h = 2166136261
    for x in xs:
        h ^= (x * 0x9E3779B1) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= h >> 15
    return (h & 0xFFFFFF) / float(0x1000000)


def _vnoise(x: int, y: int, z: int, seed: int, s: int = 3) -> float:
    """Trilinear value noise on a lattice of size s, in [-1, 1]: clusters of a few blocks."""
    fx, fy, fz = x / s, y / s, z / s
    x0, y0, z0 = math.floor(fx), math.floor(fy), math.floor(fz)
    tx, ty, tz = fx - x0, fy - y0, fz - z0
    tx, ty, tz = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty), tz * tz * (3 - 2 * tz)
    v = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (tx if dx else 1 - tx) * (ty if dy else 1 - ty) * (tz if dz else 1 - tz)
                v += w * _h(x0 + dx, y0 + dy, z0 + dz, seed)
    return v * 2 - 1


def _seed(gid: str) -> int:
    return int(_h(*[ord(c) for c in (gid or "ghost")]) * 1e9)


GRADIENT = 0.35  # how much height shifts the pick (bottom darker, top lighter)


def pick(base: str, x: int, y: int, z: int, t: float, seed: int, grad: float = GRADIENT) -> str:
    """Member of base's ramp for this cell. t = 0 (bottom) .. 1 (top) of the textured extent."""
    ramp = _build()["ramp"].get(base)
    if not ramp:
        return base
    u = 0.5 + 0.42 * _vnoise(x, y, z, seed) + 0.45 * (_h(x, y, z, seed + 1) - 0.5) + grad * (t - 0.5)
    u = min(0.999, max(0.0, u))
    for m, acc in ramp:
        if u < acc:
            return m
    return ramp[-1][0]


def _split(state: str) -> tuple[str, str]:
    i = state.find("[")
    return (state, "") if i < 0 else (state[:i], state[i:])


def retexture(state: str, x: int, y: int, z: int, t: float, seed: int, grad: float = GRADIENT) -> str:
    """Textured state for one cell, or the same state when the block has no ramp."""
    b = _build()
    base, props = _split(state)
    if base in b["ramp"]:
        return pick(base, x, y, z, t, seed, grad) + props
    vk = b["var"].get(base)
    if vk:
        fam, kind = vk
        if fam in b["ramp"]:
            m = pick(fam, x, y, z, t, seed, grad)
            v = variant_id(m, kind)
            if not _lib() or v in _lib():
                return v + props
    return state


def has_ramp(state: str) -> bool:
    b = _build()
    base, _ = _split(state)
    return base in b["ramp"] or (base in b["var"] and b["var"][base][0] in b["ramp"])


# ---------------------------------------------------------------------------------------------------- ghost_set

MAX_SIM = 400_000  # cells simulated for box ownership; bigger calls keep their boxes plain
MAX_OVERLAY = 40_000  # surface blocks added per call


def _box_cells(b: list):
    x1, y1, z1, x2, y2, z2 = (int(v) for v in b[:6])
    mode = b[7] if len(b) > 7 else "fill"
    ax, bx = sorted((x1, x2)); ay, by = sorted((y1, y2)); az, bz = sorted((z1, z2))
    for x in range(ax, bx + 1):
        ex = x == ax or x == bx
        for y in range(ay, by + 1):
            ey = y == ay or y == by
            for z in range(az, bz + 1):
                ez = z == az or z == bz
                e = ex + ey + ez
                if mode == "hollow" and e < 1 or mode == "walls" and not (ex or ez) or mode == "frame" and e < 2:
                    continue
                # surface of this box (outer faces): the only cells anyone sees
                yield (x, y, z), e >= 1


def texture(args: dict) -> tuple[dict, int]:
    """Texture one ghost_set call. Returns (new args, number of changed/added cells)."""
    if os.environ.get("ARCHITECT_TEXTURE", "1") == "0" or not _build()["ramp"]:
        return args, 0
    pal = args.get("palette") if isinstance(args.get("palette"), dict) else {}

    def state_of(key) -> str:
        return pal.get(key, key) if isinstance(key, str) else ""

    boxes = args.get("boxes") or []
    blocks = args.get("blocks") or []
    seed = _seed(str(args.get("id", "")))

    # box ownership: later boxes overwrite earlier ones, like GhostStore
    owner: dict = {}
    vol = 0
    tex_boxes = []
    for i, b in enumerate(boxes):
        if not isinstance(b, (list, tuple)) or len(b) < 7:
            continue
        try:
            dims = [abs(int(b[k + 3]) - int(b[k])) + 1 for k in range(3)]
        except (TypeError, ValueError):
            continue
        vol += dims[0] * dims[1] * dims[2]
        tex_boxes.append(has_ramp(state_of(b[6])))
    if vol > MAX_SIM or not any(tex_boxes) and not blocks:
        owner = None
    else:
        for i, b in enumerate(boxes):
            if not isinstance(b, (list, tuple)) or len(b) < 7:
                continue
            tex = has_ramp(state_of(b[6]))
            for cell, surf in _box_cells(b):
                owner[cell] = (i, surf) if tex else None

    # vertical extent of everything textured in this call -> gradient position
    ys = [c[1] for c, o in (owner or {}).items() if o and o[1]]
    ys += [int(e[1]) for e in blocks if isinstance(e, (list, tuple)) and len(e) > 3 and has_ramp(state_of(e[3]))]
    if not ys:
        return args, 0
    y0, y1 = min(ys), max(ys)
    span = y1 - y0
    grad = GRADIENT if span >= 6 else 0.0

    def tt(y):
        return (y - y0) / span if span else 0.5

    n = 0
    overlay = []
    if owner:
        for (x, y, z), o in owner.items():
            if not o or not o[1]:
                continue
            st = state_of(boxes[o[0]][6])
            ns = retexture(st, x, y, z, tt(y), seed, grad)
            if ns != st:
                overlay.append([x, y, z, ns])
                if len(overlay) >= MAX_OVERLAY:
                    break
        n += len(overlay)
    new_blocks = []
    for e in blocks:
        if isinstance(e, (list, tuple)) and len(e) > 3:
            st = state_of(e[3])
            if st and has_ramp(st):
                ns = retexture(st, int(e[0]), int(e[1]), int(e[2]), tt(int(e[1])), seed, grad)
                if ns != st:
                    e = [e[0], e[1], e[2], ns] + list(e[4:])
                    n += 1
        new_blocks.append(e)
    if not n:
        return args, 0
    out = dict(args)
    out["blocks"] = overlay + new_blocks
    return out, n
