"""World-aware site picking for the architect (pure python, no Minecraft or API needed, deterministic).

Input: a *survey* (the JSON of mc-mcp's `world_survey` tool, see README.md for the format): a coarse heightmap grid with
per-cell flags (water / lava / tree / snow / unknown). Output: where to put the campus, what level to build it at, how
much ground must be filled / cut, which trees are in the way, and the extra ghost blocks (foundation walls, support
pillars, access stairs) that keep a build on uneven ground from floating.

    python site.py plan --survey s.json --style hextech [--near x,z]     # best site + layout/size tier, JSON on stdout
    python site.py eval --survey s.json --x 10 --z 20 --w 96 --d 80 [--rot 90]   # score one rectangle (used by /ghost area)
    python site.py demo hill                                             # plan on a fake hill/shore/forest survey

campus.py is NOT imported here; `apply()` only post-processes the ghost list that campus.build() returns.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

YOFF = 128          # survey heights are stored as base-36 of (y + YOFF), two chars per cell
UNKNOWN_Y = None
FLAG_LAND, FLAG_WATER, FLAG_LAVA, FLAG_TREE, FLAG_SNOW, FLAG_UNK = ".", "w", "l", "t", "s", "?"

# Measured campus footprints (blocks, x by z, incl. hub + landmark tower) per layout and number of listed wings
# (the home wing is extra and always included). Used to pick a size tier BEFORE the campus is built; apply() then uses
# the real footprint.
FOOTPRINT = {
    "radial":   {1: (96, 115), 2: (132, 115), 3: (174, 115), 4: (204, 142), 5: (234, 169)},
    "linear":   {1: (111, 103), 2: (111, 103), 3: (146, 103), 4: (166, 103), 5: (185, 103)},
    "cloister": {1: (137, 134), 2: (137, 169), 3: (137, 187), 4: (141, 198), 5: (141, 198)},
    "terraces": {1: (103, 103), 2: (103, 128), 3: (103, 137), 4: (103, 148), 5: (103, 153)},
    "spine":    {1: (88, 85), 2: (125, 85), 3: (125, 85), 4: (140, 90), 5: (155, 91)},
}
DEFAULT_LAYOUT = {"steampunk": "spine", "hextech": "radial", "gothic": "cloister", "solarpunk": "terraces",
                  "station_white": "linear"}
MAX_WINGS = 5

FOUND_EDGE = "minecraft:stone_bricks"      # retaining wall / plinth
FOUND_PILLAR = "minecraft:cobblestone"     # cheap support columns
RAMP_STEP = "minecraft:stone_brick_stairs"
RAMP_FILL = "minecraft:stone_bricks"
_DIRS = ["north", "east", "south", "west"]  # clockwise


# ---------------------------------------------------------------- survey

def _b36(s: str) -> int:
    return int(s, 36)


class Survey:
    """Grid of cells; cell (i, j) is the column at world (x0 + i*step, z0 + j*step) and stands for the step x step
    blocks starting there. ys[j][i] = y of the top solid ground block (None = unknown), flags[j][i] one char."""

    def __init__(self, x0, z0, step, ys, flags, meta=None):
        self.x0, self.z0, self.step = int(x0), int(z0), max(1, int(step))
        self.ys, self.flags = ys, flags
        self.h, self.w = len(ys), (len(ys[0]) if ys else 0)
        self.meta = meta or {}

    # -- io
    @classmethod
    def from_json(cls, d) -> "Survey":
        if isinstance(d, str):
            d = json.loads(d)
        w, h = int(d["w"]), int(d["h"])
        ys, flags = [], []
        for j in range(h):
            row, frow = d["y"][j], d["f"][j]
            ys.append([None if row[2 * i:2 * i + 2] == "??" else _b36(row[2 * i:2 * i + 2]) - YOFF for i in range(w)])
            flags.append([frow[i] for i in range(w)])
        meta = {k: v for k, v in d.items() if k not in ("y", "f")}
        return cls(d["x0"], d["z0"], d["step"], ys, flags, meta)

    @classmethod
    def from_file(cls, path) -> "Survey":
        with open(path, encoding="utf-8") as f:
            return cls.from_json(json.load(f))

    def to_json(self) -> dict:
        def enc(y):
            return "??" if y is None else _to36(y + YOFF).rjust(2, "0")
        out = dict(self.meta)
        out.update({"v": 1, "x0": self.x0, "z0": self.z0, "step": self.step, "w": self.w, "h": self.h,
                    "y": ["".join(enc(y) for y in row) for row in self.ys],
                    "f": ["".join(row) for row in self.flags]})
        return out

    @classmethod
    def from_fn(cls, x0, z0, step, w, h, fn, meta=None) -> "Survey":
        """fn(x, z) -> (y or None, flag char)."""
        ys, fl = [], []
        for j in range(h):
            ry, rf = [], []
            for i in range(w):
                y, f = fn(x0 + i * step, z0 + j * step)
                ry.append(y)
                rf.append(f if y is not None else FLAG_UNK)
            ys.append(ry)
            fl.append(rf)
        return cls(x0, z0, step, ys, fl, meta)

    # -- access
    def cell(self, x, z):
        return (x - self.x0) // self.step, (z - self.z0) // self.step

    def inside(self, i, j):
        return 0 <= i < self.w and 0 <= j < self.h

    def height_at(self, x, z):
        """Ground y at a block column (nearest known cell), or None when outside / unknown."""
        i, j = self.cell(x, z)
        if not self.inside(i, j):
            return None
        return self.ys[j][i]

    def flag_at(self, x, z):
        i, j = self.cell(x, z)
        return self.flags[j][i] if self.inside(i, j) else FLAG_UNK

    @property
    def bounds(self):
        return self.x0, self.z0, self.x0 + self.w * self.step - 1, self.z0 + self.h * self.step - 1


def _to36(n: int) -> str:
    if n < 0:
        raise ValueError("height below survey range")
    s = ""
    while True:
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[n % 36] + s
        n //= 36
        if n == 0:
            return s


# ---------------------------------------------------------------- scoring

class _Prefix:
    """2D prefix sums of the per-cell channels, so any rectangle of cells scores in O(1)."""
    CH = ("n", "water", "lava", "tree", "unk", "snow", "k", "h", "h2", "slope")

    def __init__(self, sv: Survey):
        w, h = sv.w, sv.h
        self.t = {c: [[0.0] * (w + 1) for _ in range(h + 1)] for c in self.CH}
        for j in range(h):
            for i in range(w):
                y, f = sv.ys[j][i], sv.flags[j][i]
                v = dict.fromkeys(self.CH, 0)
                v["n"] = 1
                if y is None:
                    v["unk"] = 1
                else:
                    v["water"] = f == FLAG_WATER
                    v["lava"] = f == FLAG_LAVA
                    v["tree"] = f == FLAG_TREE
                    v["snow"] = f == FLAG_SNOW
                    if f not in (FLAG_WATER, FLAG_LAVA):
                        v["k"], v["h"], v["h2"] = 1, y, y * y
                        v["slope"] = _slope(sv, i, j)
                for c in self.CH:
                    T = self.t[c]
                    T[j + 1][i + 1] = v[c] + T[j][i + 1] + T[j + 1][i] - T[j][i]

    def rect(self, c, i0, j0, wi, wj):
        T = self.t[c]
        return T[j0 + wj][i0 + wi] - T[j0][i0 + wi] - T[j0 + wj][i0] + T[j0][i0]


def _slope(sv: Survey, i, j):
    """Largest height difference to a 4-neighbour, per block."""
    y = sv.ys[j][i]
    best = 0.0
    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if sv.inside(i + a, j + b):
            n = sv.ys[j + b][i + a]
            if n is not None:
                best = max(best, abs(n - y) / sv.step)
    return best


def _score(n, water, lava, tree, unk, k, h, h2, slope, dist_frac):
    """0..100 from channel sums over n cells."""
    wf, tf, uf = water / n, tree / n, unk / n
    std = 0.0
    if k > 0:
        mean = h / k
        std = math.sqrt(max(0.0, h2 / k - mean * mean))
    sl = slope / k if k else 0.0
    pen = min(70, 220 * wf) + min(30, 70 * tf) + min(70, 300 * uf) + min(40, 9 * std) + min(15, 20 * sl)
    pen += min(10, 12 * dist_frac)
    s = max(0.0, 100.0 - pen)
    if lava > 0:
        s = min(s, 5.0)
    return s


def _wquantile(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, max(0, int(q * len(vals))))] if vals else None


def evaluate(sv: Survey, x, z, w, d, rot=0, near=None, ref=None) -> dict:
    """Exact numbers for the block rectangle x..x+w-1, z..z+d-1 (w, d already rotated). Cells outside the survey count
    as unknown. ref = platform level; default: the level that minimises 1.0*fill + 1.5*cut (60% quantile of the ground)."""
    cells = []
    i0, j0 = sv.cell(x, z)
    i1, j1 = sv.cell(x + w - 1, z + d - 1)
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            cells.append((i, j))
    n = len(cells)
    water = lava = tree = unk = snow = 0
    land = []
    for i, j in cells:
        y = sv.ys[j][i] if sv.inside(i, j) else None
        f = sv.flags[j][i] if sv.inside(i, j) else FLAG_UNK
        if y is None:
            unk += 1
            continue
        if f == FLAG_WATER:
            water += 1
        elif f == FLAG_LAVA:
            lava += 1
        else:
            land.append(y)
            tree += f == FLAG_TREE
            snow += f == FLAG_SNOW
    if ref is None:
        ref = _wquantile(land, 0.6)
        if ref is None:
            ref = _wquantile([sv.ys[j][i] for i, j in cells if sv.inside(i, j) and sv.ys[j][i] is not None], 0.6)
        if ref is None:
            ref = 64
    fill = cut = max_fill = max_cut = 0
    trees, tree_cells = [], 0
    cx, cz = x + w // 2, z + d // 2
    dev = []
    for zz in range(z, z + d):
        for xx in range(x, x + w):
            t = sv.height_at(xx, zz)
            if t is None:
                continue
            fl = sv.flag_at(xx, zz)
            f = max(0, ref - 1 - t)
            c = max(0, t - ref)
            fill += f
            cut += c
            max_fill = max(max_fill, f)
            max_cut = max(max_cut, c)
            dev.append(abs(t - ref))
            if fl == FLAG_TREE:
                tree_cells += 1
                if (xx - sv.x0) % sv.step == 0 and (zz - sv.z0) % sv.step == 0:
                    trees.append([xx, t + 1, zz])
    area = max(1, w * d)
    k = len(land)
    std = 0.0
    if k:
        m = sum(land) / k
        std = math.sqrt(sum((v - m) ** 2 for v in land) / k)
    dist = 0.0
    if near is not None:
        half = max(sv.w, sv.h) * sv.step / 2 or 1
        dist = math.hypot(cx - near[0], cz - near[1]) / half
    sl = 0.0
    if k:
        sl = sum(_slope(sv, i, j) for i, j in cells if sv.inside(i, j) and sv.ys[j][i] is not None
                 and sv.flags[j][i] not in (FLAG_WATER, FLAG_LAVA)) / k
    score = _score(n, water, lava, tree, unk, k, sum(land), sum(v * v for v in land), sl * k, dist)
    wf, uf, tf = water / n, unk / n, tree / n
    avg_fill, avg_cut = fill / area, cut / area
    score = max(0.0, score - min(30, 5 * (avg_fill + 1.5 * avg_cut)))  # earthworks cost
    if lava or wf > 0.25 or uf > 0.25 or score < 30 or max_cut > 10 or avg_cut > 3:
        cls = "red"
    elif max_fill > 3 or max_cut > 4 or avg_fill > 1.0 or avg_cut > 1.0 or wf > 0.03:
        cls = "yellow"
    else:
        cls = "lime"
    ymin = min(land) if land else None
    ymax = max(land) if land else None
    return {"x": x, "z": z, "w": w, "d": d, "rot": rot, "ref": ref, "fit": int(round(score)), "class": cls,
            "fill": fill, "cut": cut, "max_fill": max_fill, "max_cut": max_cut,
            "water_pct": round(100 * wf, 1), "tree_pct": round(100 * tf, 1), "unknown_pct": round(100 * uf, 1),
            "lava_cells": lava, "snow_pct": round(100 * snow / n, 1), "y_min": ymin, "y_max": ymax,
            "y_std": round(std, 2), "tree_cells": tree_cells, "trees": trees[:60]}


def _cand_sizes(w, d, allow_rot):
    return [(w, d, 0)] + ([(d, w, 90)] if allow_rot and w != d else [])


def pick(sv: Survey, w, d, near=None, allow_rot=True, top=1) -> list:
    """Best rectangles for a w x d footprint inside the survey, best first (deterministic). Each entry is the
    evaluate() dict plus 'raw' (the fast score used for ranking)."""
    pre = _Prefix(sv)
    cands = []
    for cw, cd, rot in _cand_sizes(w, d, allow_rot):
        wi, wj = -(-cw // sv.step), -(-cd // sv.step)
        if wi > sv.w or wj > sv.h:
            continue
        half = max(sv.w, sv.h) * sv.step / 2 or 1
        for j0 in range(0, sv.h - wj + 1):
            for i0 in range(0, sv.w - wi + 1):
                n = wi * wj
                g = {c: pre.rect(c, i0, j0, wi, wj) for c in _Prefix.CH}
                dist = 0.0
                if near is not None:
                    dist = math.hypot(sv.x0 + (i0 + wi / 2) * sv.step - near[0], sv.z0 + (j0 + wj / 2) * sv.step - near[1]) / half
                s = _score(n, g["water"], g["lava"], g["tree"], g["unk"], g["k"], g["h"], g["h2"], g["slope"], dist)
                cands.append((-s, j0, i0, rot, cw, cd))
    cands.sort()
    out = []
    for ns, j0, i0, rot, cw, cd in cands[:max(1, top)]:
        e = evaluate(sv, sv.x0 + i0 * sv.step, sv.z0 + j0 * sv.step, cw, cd, rot, near)
        e["raw"] = round(-ns, 1)
        out.append(e)
    return out


def configs(style_or_layout: str, slope_hint: float = 0.0, layout: str | None = None, max_wings: int = MAX_WINGS):
    """(layout, wings) options, most ambitious first. A fixed layout (user asked) is the only layout tried."""
    base = layout or DEFAULT_LAYOUT.get(style_or_layout, style_or_layout if style_or_layout in FOOTPRINT else "spine")
    order = [base] if layout else [base] + (["terraces"] if slope_hint > 1.2 else []) + ["spine", "linear", "terraces", "cloister", "radial"]
    seen, out = set(), []
    for lay in order:
        if lay in seen:
            continue
        seen.add(lay)
        for n in range(max_wings, 0, -1):
            out.append((lay, n))
    return out


def plan(sv: Survey, style: str = "hextech", near=None, layout: str | None = None, max_wings: int = MAX_WINGS,
         allow_rot: bool = True) -> dict:
    """Pick layout + wing count + rectangle for the survey. Deterministic."""
    base = DEFAULT_LAYOUT.get(style, "spine")
    pre = _Prefix(sv)
    k = pre.rect("k", 0, 0, sv.w, sv.h)
    sl = pre.rect("slope", 0, 0, sv.w, sv.h) / k if k else 0
    best = None
    for lay, n in configs(style, sl, layout, max_wings):
        fw, fd = FOOTPRINT[lay][min(n, 5)]
        res = pick(sv, fw, fd, near, allow_rot)
        if not res:
            continue
        e = res[0]
        # prefer big campuses, the style's own layout, and a spot that is not red
        util = e["fit"] + 4 * n + (5 if lay == base else 0) - (60 if e["class"] == "red" else 0)
        key = (util, e["fit"], n)
        if best is None or key > best[0]:
            best = (key, lay, n, e)
    if best is None:  # survey smaller than every footprint: best-effort placement of the smallest one
        lay, n = "spine", 1
        fw, fd = FOOTPRINT[lay][1]
        e = evaluate(sv, sv.x0 + (sv.w * sv.step - fw) // 2, sv.z0 + (sv.h * sv.step - fd) // 2, fw, fd, 0, near)
    else:
        _, lay, n, e = best
    e = dict(e)
    e.pop("raw", None)
    e["layout"], e["wings"] = lay, n
    e["size"] = "m" if n >= 4 else "s"
    e["style"] = style
    e["survey"] = survey_summary(sv)
    e["summary"] = describe(e)
    return e


def wings_for(layout: str, w: int, d: int) -> int:
    """Most listed wings of this layout whose measured footprint fits a w x d area (either orientation); at least 1."""
    best = 1
    for n in range(1, MAX_WINGS + 1):
        fw, fd = FOOTPRINT.get(layout, FOOTPRINT["spine"])[n]
        if (fw <= w and fd <= d) or (fd <= w and fw <= d):
            best = n
    return best


def survey_summary(sv: Survey) -> dict:
    m = sv.meta
    return {k: m[k] for k in ("ymin", "ymax", "ymed", "water_pct", "tree_pct", "unknown_pct", "biome", "slope") if k in m}


def describe(e: dict) -> str:
    """One short line for chat and for the LLM prompt (no raw grid)."""
    bits = [f"fit {e['fit']}/100 ({e['class']})", f"{e['w']}x{e['d']} rot{e['rot']} at {e['x']},{e['z']}",
            f"platform y={e['ref']}"]
    if e["fill"] or e["cut"]:
        bits.append(f"fill ~{e['fill']} cut ~{e['cut']} blocks")
    if e["tree_cells"]:
        bits.append(f"{e['tree_cells']} tree blocks to clear")
    if e["water_pct"]:
        bits.append(f"water {e['water_pct']}%")
    if e.get("layout"):
        bits.append(f"layout {e['layout']} {e['wings']} wings")
    return ", ".join(bits)


# ---------------------------------------------------------------- rotation of a built campus

_PROP = re.compile(r"\[(.*)\]$")
_ROT_SHAPE = {"north_south": "east_west", "east_west": "north_south", "ascending_north": "ascending_east",
              "ascending_east": "ascending_south", "ascending_south": "ascending_west", "ascending_west": "ascending_north"}


def rot_dir(d: str) -> str:
    return _DIRS[(_DIRS.index(d) + 1) % 4] if d in _DIRS else d


def rot_state(state: str) -> str:
    """Block state string turned 90 degrees clockwise (seen from above)."""
    m = _PROP.search(state)
    if not m:
        return state
    props = dict(p.split("=", 1) for p in m.group(1).split(",") if "=" in p)
    out = {}
    for k, v in props.items():
        if k == "facing":
            out[k] = rot_dir(v)
        elif k == "axis":
            out[k] = {"x": "z", "z": "x"}.get(v, v)
        elif k in _DIRS:  # fence / wall / pane / vine sides
            out[_DIRS[(_DIRS.index(k) + 1) % 4]] = v
        elif k == "rotation":
            out[k] = str((int(v) + 4) % 16)
        elif k == "shape" and v in _ROT_SHAPE:
            out[k] = _ROT_SHAPE[v]
        else:
            out[k] = v
    return state[:m.start()] + "[" + ",".join(f"{k}={v}" for k, v in out.items()) + "]"


def _bounds(ghosts):
    xs, zs, ys = [], [], []
    for g in ghosts:
        o = g["origin"]
        for b in g["blocks"]:
            xs.append(o[0] + b[0])
            zs.append(o[2] + b[2])
            ys.append(o[1] + b[1])
    return min(xs), max(xs), min(zs), max(zs), min(ys), max(ys)


def rotate_ghosts(ghosts, quarter_turns: int):
    """Rotate a whole campus about the vertical axis; keeps min corner at 0,0. Door sides in meta turn too."""
    for _ in range(quarter_turns % 4):
        x0, x1, z0, z1, _y0, _y1 = _bounds(ghosts)
        D = z1 - z0 + 1
        out = []
        for g in ghosts:
            o = g["origin"]
            gz = o[2] - z0
            gx = o[0] - x0
            ng = dict(g)
            ng["origin"] = [(D - 1) - gz, o[1], gx]
            ng["blocks"] = [[-b[2], b[1], b[0], rot_state(b[3]) if isinstance(b[3], str) else b[3]] for b in g["blocks"]]
            meta = dict(g.get("meta") or {})
            if meta.get("door"):
                meta["door"] = {"n": "e", "e": "s", "s": "w", "w": "n"}.get(meta["door"], meta["door"])
            ng["meta"] = meta
            out.append(ng)
        ghosts = out
    return ghosts


# ---------------------------------------------------------------- campus integration

def apply(ghosts: list, sv: Survey, near=None, force: dict | None = None, allow_rot: bool = True):
    """Fit a built campus (campus.build() output: list of {id, origin, blocks[[x,y,z,state]], meta}) onto the surveyed
    ground. Returns (ghosts + foundation ghost, report). report['origin'] is the world [x, y, z] the ghosts' origins are
    relative to (use it instead of the caller's origin). Nothing in the world is ever removed: ground above the platform
    is reported as 'cut', trees as 'trees_to_clear'. Without a survey call nothing here: the flat behaviour is unchanged.

    force: {"x": minx, "z": minz, "rot": 0|90|180|270, "ref": platform_y?} pins the placement (an accepted /ghost area)."""
    x0, x1, z0, z1, _, _ = _bounds(ghosts)
    # normalise: min corner of the campus at local 0,0
    ghosts = [dict(g, origin=[g["origin"][0] - x0, g["origin"][1], g["origin"][2] - z0]) for g in ghosts]
    W, D = x1 - x0 + 1, z1 - z0 + 1
    if force:
        rot = int(force.get("rot", 0)) % 360
        turns = rot // 90
        if turns:
            ghosts = rotate_ghosts(ghosts, turns)
        ev = {"w": W, "d": D} if turns % 2 == 0 else {"w": D, "d": W}
        # centre the real footprint in the previewed area when the area is the larger one
        ax, az = int(force["x"]), int(force["z"])
        aw, ad = int(force.get("w", ev["w"])), int(force.get("d", ev["d"]))
        px, pz = ax + max(0, (aw - ev["w"]) // 2), az + max(0, (ad - ev["d"]) // 2)
        e = evaluate(sv, px, pz, ev["w"], ev["d"], rot, near, force.get("ref"))
    else:
        res = pick(sv, W, D, near, allow_rot)
        if res:
            e = res[0]
        else:  # survey smaller than the campus: centre it on the survey
            e = evaluate(sv, sv.x0 + (sv.w * sv.step - W) // 2, sv.z0 + (sv.h * sv.step - D) // 2, W, D, 0, near)
            e["class"] = "red"
        rot = e["rot"]
        if rot:
            ghosts = rotate_ghosts(ghosts, rot // 90)
    px, pz, ref = e["x"], e["z"], e["ref"]

    plat = [g for g in ghosts if g["id"] in ("platform", "tiers")]
    base_g = [g for g in ghosts if g["id"] == "platform"] or ghosts
    base_y = min(g["origin"][1] + b[1] for g in base_g for b in g["blocks"])
    oy = ref - base_y
    # site-local -> world: x = px + lx, z = pz + lz, y = oy + ly
    cols: dict = {}
    src = plat or ghosts
    for g in src:
        for b in g["blocks"]:
            if not plat and g["origin"][1] + b[1] != base_y:
                continue
            k = (g["origin"][0] + b[0], g["origin"][2] + b[2])
            y = g["origin"][1] + b[1]
            if k not in cols or y < cols[k]:
                cols[k] = y
    found, fill_total, cut_total, max_fill = [], 0, 0, 0
    keys = set(cols)
    for (lx, lz), by in sorted(cols.items()):
        t = sv.height_at(px + lx, pz + lz)
        if t is None:
            t = oy + by - 1  # unknown ground: assume it touches
        top = oy + by - 1  # highest foundation block world y
        if top <= t:
            cut_total += max(0, t - (oy + by))
            continue
        depth = top - t
        fill_total += depth
        max_fill = max(max_fill, depth)
        edge = any((lx + a, lz + b2) not in keys for a, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        pillar = lx % 4 == 0 and lz % 4 == 0
        if edge or pillar:
            blk = FOUND_EDGE if edge else FOUND_PILLAR
            for wy in range(t + 1, top + 1):
                found.append([lx, wy - oy, lz, FOUND_EDGE if (edge or wy == top) else blk])
    # stairs down from the middle of each platform side where the platform stands well above the ground
    ramps = _ramps(sv, cols, keys, px, pz, oy, found)
    ghosts = list(ghosts)
    if found:
        ghosts.append({"id": "foundation", "origin": [0, 0, 0], "blocks": found, "meta": {"kind": "foundation"}})
    trees = e.get("trees") or []
    summary = {
        "origin": [px, oy, pz], "rot": rot, "platform_y": ref, "fit": e["fit"], "class": e["class"],
        "fill_blocks": fill_total, "cut_blocks": e["cut"], "max_fill_depth": max_fill, "foundation_ghost_blocks": len(found),
        "ramps": ramps, "water_pct": e["water_pct"], "tree_count": e["tree_cells"], "trees_to_clear": trees[:30],
        "site_min": [px, pz], "site_max": [px + (W if rot % 180 == 0 else D) - 1, pz + (D if rot % 180 == 0 else W) - 1],
        "footprint": [W, D],
    }
    summary["summary"] = (f"site {summary['class']} (fit {e['fit']}): platform y={ref}, fill ~{fill_total} (max {max_fill} deep), "
                          f"cut ~{e['cut']}, {e['tree_cells']} tree blocks to clear, {len(found)} foundation blocks, {ramps} stairs")
    return ghosts, summary


def _ramps(sv, cols, keys, px, pz, oy, found) -> int:
    """3-wide stone-brick stairs descending outward from the middle of each platform side that stands > 2 above ground."""
    if not keys:
        return 0
    xs = [k[0] for k in keys]
    zs = [k[1] for k in keys]
    mx, mz = (min(xs) + max(xs)) // 2, (min(zs) + max(zs)) // 2
    sides = [((max(xs), mz), (1, 0), "west"), ((min(xs), mz), (-1, 0), "east"),
             ((mx, max(zs)), (0, 1), "north"), ((mx, min(zs)), (0, -1), "south")]
    have = {(f[0], f[1], f[2]) for f in found}
    n = 0
    for (ex, ez), (dx, dz), face in sides:
        if (ex, ez) not in cols:
            continue
        edge_top = oy + cols[(ex, ez)] - 1
        t0 = sv.height_at(px + ex, pz + ez)
        if t0 is None or edge_top - t0 < 3:
            continue
        for lane in (-1, 0, 1):
            for k in range(1, 16):
                lx, lz = ex + dx * k + (lane if dx == 0 else 0), ez + dz * k + (lane if dz == 0 else 0)
                step_y = edge_top - k + 1  # first step one below the platform
                t = sv.height_at(px + lx, pz + lz)
                if t is None or step_y <= t or step_y < t + 1:
                    break
                for wy in range(t + 1, step_y):
                    if (lx, wy - oy, lz) not in have:
                        found.append([lx, wy - oy, lz, RAMP_FILL])
                        have.add((lx, wy - oy, lz))
                found.append([lx, step_y - oy, lz, f"{RAMP_STEP}[facing={face},half=bottom]"])
                have.add((lx, step_y - oy, lz))
                n += 1
    return n


def prompt_note(plan_: dict) -> str:
    """The only survey text the LLM sees (cheap): level, foundations, obstacles; never the raw grid."""
    p = plan_
    s = (f"Terrain survey: site {p['class']} (fit {p['fit']}/100), flat platform y={p['ref']}. "
         f"{'Foundations will be added automatically (fill ~%d blocks, max %d deep). ' % (p['fill'], p['max_fill']) if p['fill'] else 'Ground is already flat. '}"
         f"{'%d tree blocks inside the site will be listed to clear. ' % p['tree_cells'] if p['tree_cells'] else ''}"
         f"{'%.0f%% water inside the site. ' % p['water_pct'] if p['water_pct'] else ''}"
         f"Use layout={p['layout']} with at most {p['wings']} wings (size {p['size']}), nothing outside the site. "
         "Mention in your summary the foundations and the trees to clear that the campus result reports.")
    return s


# ---------------------------------------------------------------- fake surveys (tests, demo)

def fake(kind: str, w=49, h=49, step=3, x0=0, z0=0) -> Survey:
    """Deterministic fake surveys: flat | hill | slope | shoreline | forest | unknown | cliff."""
    def fn(x, z):
        cx, cz = x0 + w * step // 2, z0 + h * step // 2
        if kind == "flat":
            return 64, FLAG_LAND
        if kind == "hill":  # one big mound at the centre, 24 high
            r = math.hypot(x - cx, z - cz)
            return 64 + int(max(0, 24 - r * 0.6)), FLAG_LAND
        if kind == "slope":  # gentle ramp, 0.1 per block (about 9 over a campus)
            return 64 + int((x - x0) * 0.1), FLAG_LAND
        if kind == "shoreline":  # sea for z > cz+30 (seabed 58), shore slope, flat land elsewhere
            if z > cz + 30:
                return 58, FLAG_WATER
            return 64 + max(0, int((cz + 30 - z) * 0.0)), FLAG_LAND
        if kind == "forest":
            tree = (x * 7 + z * 13) % 5 == 0 or (x // step + z // step) % 3 == 0 and (x // step) % 2 == 0
            return 66, FLAG_TREE if tree else FLAG_LAND
        if kind == "unknown":  # only the western 55% is loaded
            return (None, FLAG_UNK) if x > x0 + w * step * 55 // 100 else (64, FLAG_LAND)
        if kind == "cliff":  # plateau at 80 east of cx, lowland at 64 west
            return (80 if x > cx else 64), FLAG_LAND
        raise ValueError(kind)
    return Survey.from_fn(x0, z0, step, w, h, fn, {"biome": "minecraft:plains"})


# ---------------------------------------------------------------- cli

def _near(s):
    return tuple(int(v) for v in s.split(",")) if s else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--survey", required=True)
    p.add_argument("--style", default="hextech")
    p.add_argument("--near")
    p.add_argument("--layout")
    p.add_argument("--max-wings", type=int, default=MAX_WINGS)
    e = sub.add_parser("eval")
    e.add_argument("--survey", required=True)
    e.add_argument("--x", type=int, required=True)
    e.add_argument("--z", type=int, required=True)
    e.add_argument("--w", type=int, required=True)
    e.add_argument("--d", type=int, required=True)
    e.add_argument("--rot", type=int, default=0)
    e.add_argument("--ref", type=int)
    e.add_argument("--near")
    d = sub.add_parser("demo")
    d.add_argument("kind")
    d.add_argument("--style", default="hextech")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        out = plan(Survey.from_file(a.survey), a.style, _near(a.near), a.layout, a.max_wings)
    elif a.cmd == "eval":
        out = evaluate(Survey.from_file(a.survey), a.x, a.z, a.w, a.d, a.rot, _near(a.near), a.ref)
        out["summary"] = describe(out)
    else:
        out = plan(fake(a.kind), a.style)
    out.pop("trees", None) if "--keep-trees" not in sys.argv else None
    print(json.dumps(out))


if __name__ == "__main__":
    main()
