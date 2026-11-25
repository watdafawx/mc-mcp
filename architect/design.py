"""Step 3 of the quality plan: build-as-program.

One Sonnet call turns a prompt (plus the kit's mood board) into a JSON design spec: a concept, a kit with role
overrides, a set of volumes placed relative to each other (attach to a side, stack on top, or absolute) and purposeful
features (spires, chimneys, gears, pipe runs, buttresses, bridges, a platform). A deterministic composer resolves that
spec into ghosts: every volume goes through massing.structure, so the facade depth pass (depth.py) and the palette
pass (palette.py, at ghost_set) apply to all of it.

The composer owns the rules the model is bad at: no overlaps, everything grounded, big interiors for modded play
(machine floors >= 9 high, rooms >= 11 wide inside), attached volumes get a doorway through the shared wall, a volume
something stacks on gets a flat roof, decoration never lands inside another volume.

  spec, cost = design.design(client, "brick factory with a clock tower", kit="steampunk")
  ghosts, report = design.compose(spec)          # ghosts in site-local coords, origin 0,0,0
"""
from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path

import shapes  # noqa: F401  (must load before massing: circular import)
import massing
import campus
import palette

HERE = Path(__file__).resolve().parent
REFS = HERE / "knowledge" / "style_refs"
MODEL = os.environ.get("ARCHITECT_DESIGN_MODEL", "claude-sonnet-5-5")
EFFORT = os.environ.get("ARCHITECT_DESIGN_EFFORT", "medium")
# USD per million tokens (input, output); cache reads ~10%, writes ~125%.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}

KITS = sorted(massing.KITS)
ROOFS = ["flat", "mansard", "dome", "crown"] + sorted(massing.HF_ROOFS)
SHAPES = ["rect", "octagon", "round", "L"]
SIDES = ["n", "s", "e", "w"]
ROLES = ["base", "wall", "wall2", "trim", "pillar", "accent", "glass", "glow", "rail", "roof", "detail", "antenna", "tip"]
PROGRAM = ["machine_hall", "expansion", "workshop", "lab", "storage", "hall", "living"]
FEATURES = ["spire", "chimney", "gear", "pipes", "buttresses", "bridge", "platform"]
# minimum clear floor height per room kind: modded setups are pipe/cable heavy or big multiblocks
MIN_H = {"machine_hall": 9, "expansion": 9, "workshop": 6, "lab": 6, "storage": 5, "hall": 6, "living": 4}
BIG = {"machine_hall", "expansion"}
MAX_VOLUMES, MAX_SIDE, MAX_R, MAX_H = 12, 64, 24, 60
AIR = "minecraft:air"


# ---------------------------------------------------------------- spec schema (structured output)

def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_INT = {"type": "integer"}
_STR = {"type": "string"}
_ROLEPAIRS = {"type": "array", "items": _obj({"role": {"type": "string", "enum": ROLES}, "block": _STR})}

SCHEMA = _obj({
    "concept": _STR,
    "kit": {"type": "string", "enum": KITS},
    "roles": _ROLEPAIRS,
    "volumes": {"type": "array", "items": _obj({
        "id": _STR,
        "purpose": _STR,
        "shape": {"type": "string", "enum": SHAPES},
        "w": _INT, "d": _INT, "r": _INT, "cut_w": _INT, "cut_d": _INT,
        "floor_hs": {"type": "array", "items": _INT},
        "program": {"type": "array", "items": _STR},
        "roof": {"type": "string", "enum": ROOFS},
        "windows": {"type": "string", "enum": ["band", "grid", "slit", "none"]},
        "rhythm": _INT,
        "accent_floor": _INT,
        "open_ground": {"type": "boolean"},
        "entrances": {"type": "array", "items": {"type": "string", "enum": SIDES}},
        "roles": _ROLEPAIRS,
        "place": _obj({
            "mode": {"type": "string", "enum": ["at", "attach", "stack"]},
            "to": _STR,
            "side": {"type": "string", "enum": SIDES},
            "align": {"type": "string", "enum": ["start", "center", "end"]},
            "offset": _INT, "gap": _INT, "x": _INT, "z": _INT,
        }),
    })},
    "features": {"type": "array", "items": _obj({
        "kind": {"type": "string", "enum": FEATURES},
        "on": _STR, "to": _STR,
        "side": {"type": "string", "enum": SIDES + ["top"]},
        "pos": {"type": "number"},
        "size": _INT, "level": _INT,
    })},
})

SYSTEM = """You are the lead architect of a Minecraft build generator for modded survival (All the Mods 10, MC 1.21.1).
You design the COMPOSITION; a deterministic engine turns your spec into blocks (facade piers, recessed window bays,
sills, cornices, base skirts, roof shapes and block shading are added for you). Return only the JSON spec.

Silhouette rules: the landmark is at least 1.8x as tall as the next volume (more floors, a tall roof, a spire feature);
roof lines step down from it. A volume that something stacks on gets a flat roof (the stacked one covers it), so stack
only when that is the look you want; otherwise attach the tower beside the hall.

What separates great builds from samey boxes: one clear theme followed everywhere; a strong silhouette with ONE landmark
(tallest volume, distinct roof or spire); 2-5 supporting volumes of graded size that attach to each other (setbacks,
offsets, an L or octagon where it helps) instead of floating apart; repetition with variation (same window system, a
few roof types, not one per volume); every feature has a reason (chimneys on the furnace hall, gears on the workshop
face, pipe runs on the process hall, buttresses on the tall nave, a bridge only between volumes with a gap).

Modded play rules (hard): interiors must be BIG. Machine halls and expansion floors are 9-13 high and at least 13 wide;
workshops/labs 6-8 high; living 4-5. Prefer wide 1-2 storey halls with lots of floor; height goes into the landmark.
All detail goes outward; never plan anything that eats interior space.

Coordinates: x = east, z = south, y = up. Sizes in blocks. A volume's footprint is w x d (rect/octagon/L) or radius r
(round, footprint 2r+1). floor_hs: clear height per floor, bottom first (program has one room kind per floor; split a
floor with "+", e.g. "workshop+storage"; kinds: machine_hall, expansion, workshop, lab, storage, hall, living).
Placement: the first volume uses mode "at" (x, z = its north-west corner, normally 0, 0). Others use "attach" (touch
volume `to` on `side`; align start|center|end along that side, offset shifts it, gap 0 = shared wall with a doorway,
gap >= 3 leaves a yard a bridge can cross) or "stack" (sits on the roof of `to`, centred, x/z shift it; must be smaller).
Unused numeric fields: 0. roof: flat | mansard | dome | crown | gable(_steep/_low) | hip(_steep/_low) | barrel |
sawtooth (factory north-light) | spire | garden. windows: band | grid | slit | none. rhythm 0-3 = bay rhythm variety.
accent_floor: floor index carrying the accent stripe, -1 none. entrances: sides with a 3-wide door on the ground floor.

Materials: pick the kit closest to the brief, then override roles where the brief needs it (role -> vanilla or listed
block id that really exists; e.g. a brick factory: wall2 minecraft:bricks, pillar minecraft:stone_bricks). Roles:
base = plinth and skirt, wall2 = main wall infill, pillar = piers between bays, trim = ledges, sills, cornice,
wall = bands and parapet, accent = stripe floor, glass, glow = light bands, roof, detail = rooftop units, rail,
antenna, tip. Keep ~3 main materials (60/30/10). Per-volume roles override for one volume (e.g. a copper roof on the tower).

Features: spire (on top of `on`, size = height), chimney (2x2 stack against `on`'s `side` wall at pos 0-1, size =
height above the roof), gear (decorative gear disc on a wall face, size = radius 2-6, level = floor index),
pipes (copper pipe runs along the walls of `on`, side = first wall), buttresses (gothic flying buttresses on `side`),
bridge (enclosed sky-bridge from `on` to `to` at floor `level`; only across a gap), platform (terraced base under the
whole site, size = steps 1-3). Use 3-10 features.

Kits:
""" + "\n".join(f"- {k}: " + ", ".join(f"{r}={massing.KITS[k][r]}" for r in ("base", "wall2", "pillar", "trim", "glass", "roof")
                   if r in massing.KITS[k]) for k in KITS)


# ---------------------------------------------------------------- the designer call

KIT_WORDS = {"steampunk": ("steam", "brass", "factory", "foundry", "industrial", "refinery", "workshop", "victorian"),
             "gothic": ("gothic", "cathedral", "castle", "dark", "church", "abbey"),
             "hextech": ("hextech", "piltover", "arcane", "art deco", "deco"),
             "station_white": ("station", "space", "lab", "white", "sci", "research"),
             "cyber_dark": ("cyber", "neon", "data", "server"),
             "solarpunk": ("solar", "eco", "green", "garden", "greenhouse"),
             "rust_industrial": ("rig", "oil", "rust", "sea", "harbour", "dock"),
             "ae_sky": ("ae2", "sky stone", "applied")}


def guess_kit(text: str) -> str | None:
    t = text.lower()
    best = max(KIT_WORDS, key=lambda k: sum(w in t for w in KIT_WORDS[k]))
    return best if any(w in t for w in KIT_WORDS[best]) else None


def mood_board(kit: str | None, n: int = 3) -> list:
    """Content blocks: the kit's reference notes plus up to n of its pictures."""
    try:
        refs = json.loads((REFS / "index.json").read_text("utf-8"))
    except OSError:
        return []
    mine = [r for r in refs if r["kit"] == kit] if kit else []
    notes = "\n".join(f"- {r['file']} ({r['kit']}): {r['notes']}" for r in (mine or refs))
    out = [{"type": "text", "text": "Mood board (quality bar, follow its theme and composition):\n" + notes}]
    for r in mine[:n]:
        p = REFS / r["file"]
        if p.exists():
            out.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.standard_b64encode(p.read_bytes()).decode()}})
    return out


def cost_of(u, model: str = MODEL) -> float:
    pin, pout = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    cin = (u.input_tokens + (getattr(u, "cache_creation_input_tokens", 0) or 0) * 1.25
           + (getattr(u, "cache_read_input_tokens", 0) or 0) * 0.1)
    return (cin * pin + u.output_tokens * pout) / 1e6


def design(client, request: str, kit: str | None = None, extra: list | None = None) -> tuple[dict, float]:
    """One Sonnet call: prompt -> spec dict. Server-side refusal fallbacks on; JSON schema enforced."""
    kit = kit or guess_kit(request)
    content = mood_board(kit) + list(extra or []) + [{"type": "text", "text": (
        f"Brief: {request}\n" + (f"Use kit {kit} (override roles as needed).\n" if kit else "")
        + "Design it. Put your reasoning about silhouette, hierarchy and materials in `concept` first.")}]
    kw = dict(model=MODEL, max_tokens=16000, system=SYSTEM, messages=[{"role": "user", "content": content}],
              thinking={"type": "adaptive"},
              output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}})
    try:
        with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw) as s:
            resp = s.get_final_message()
    except Exception as e:  # local / proxied endpoints without the beta: plain call
        if "fallback" not in str(e).lower() and "beta" not in str(e).lower():
            raise
        with client.messages.stream(**kw) as s:
            resp = s.get_final_message()
    if resp.stop_reason == "refusal":
        raise RuntimeError("designer refused the brief")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), cost_of(resp.usage, getattr(resp, "model", MODEL) or MODEL)


# ---------------------------------------------------------------- the composer

def _roles(pairs) -> dict:
    """[{role, block}] -> {role: block}, dropping ids the pack doesn't have."""
    lib = palette._lib()
    out = {}
    for p in pairs or []:
        r, b = p.get("role"), str(p.get("block") or "")
        if r in ROLES and ":" in b and (not lib or b.split("[", 1)[0] in lib):
            out[r] = b
    return out


class Vol:
    def __init__(self, spec: dict, fixes: list):
        self.s = s = spec
        self.id = str(s.get("id") or "v")
        self.shape = s.get("shape") if s.get("shape") in SHAPES else "rect"
        prog = [str(p or "hall") for p in (s.get("program") or [])]
        hs = [int(h) for h in (s.get("floor_hs") or [])] or [9]
        hs = hs[:6]
        prog = (prog + [prog[-1] if prog else "hall"] * len(hs))[:len(hs)]
        for i, kinds in enumerate(prog):
            need = max(MIN_H.get(k.strip(), 4) for k in kinds.split("+"))
            if hs[i] < need or hs[i] > 16:
                fixes.append(f"{self.id}: floor {i} height {hs[i]} -> {max(need, min(hs[i], 16))} ({kinds})")
                hs[i] = max(need, min(hs[i], 16))
        while sum(hs) > MAX_H - 6:
            hs.pop()
            prog.pop()
        self.hs, self.prog = hs, prog
        big = any(k.strip() in BIG for p in prog for k in p.split("+"))
        lo = 15 if big else 9  # outer size; 2 rings of facade -> >= 11 clear inside
        self.w = max(lo, min(MAX_SIDE, int(s.get("w") or lo)))
        self.d = max(lo, min(MAX_SIDE, int(s.get("d") or lo)))
        self.r = max(8 if big else 5, min(MAX_R, int(s.get("r") or 0) or self.w // 2))
        for k, v in (("w", self.w), ("d", self.d)):
            if self.shape != "round" and int(s.get(k) or 0) != v:
                fixes.append(f"{self.id}: {k} {s.get(k)} -> {v}")
        self.roof = s.get("roof") if s.get("roof") in ROOFS else "flat"
        self.place = dict(s.get("place") or {})
        self.x0 = self.z0 = self.y0 = 0
        self.fp: set = set()
        self.blocks: list = []
        self.stacked_on_me = False

    def footprint(self) -> set:
        if self.shape == "round":
            fp = massing.footprint("round", r=self.r)
        elif self.shape == "L":
            cw = int(self.s.get("cut_w") or 0) or self.w // 2
            cd = int(self.s.get("cut_d") or 0) or self.d // 2
            fp = massing.footprint("L", self.w, self.d, cut_w=min(cw, self.w - 9), cut_d=min(cd, self.d - 9))
        else:
            fp = massing.footprint(self.shape, self.w, self.d)
        mx, mz = min(p[0] for p in fp), min(p[1] for p in fp)
        return {(x - mx, z - mz) for x, z in fp}

    @property
    def ry(self) -> int:
        return sum(self.hs) + 1

    def bbox(self):
        xs = [p[0] for p in self.fp]
        zs = [p[1] for p in self.fp]
        return min(xs), min(zs), max(xs), max(zs)


def _overlaps(v: Vol, others: list) -> Vol | None:
    for o in others:
        if o is v or not o.fp or v.place.get("mode") == "stack" and o.id == v.place.get("to"):
            continue
        y_ok = v.y0 <= o.y0 + o.ry and o.y0 <= v.y0 + v.ry
        if y_ok and v.fp & o.fp:
            return o
    return None


def _place(v: Vol, by_id: dict, placed: list, fixes: list):
    loc = v.footprint()
    W = max(p[0] for p in loc) + 1
    D = max(p[1] for p in loc) + 1
    pl = v.place
    mode, to = pl.get("mode"), by_id.get(pl.get("to"))
    off = int(pl.get("offset") or 0)
    if mode in ("attach", "stack") and (to is None or not to.fp):
        fixes.append(f"{v.id}: target {pl.get('to')!r} not placed, attached east of the site instead")
        to = placed[-1] if placed else None
        mode, pl["side"] = ("attach", "e") if to else ("at", "e")
    if mode == "stack" and to:
        tx0, tz0, tx1, tz1 = to.bbox()
        if W > tx1 - tx0 - 1 or D > tz1 - tz0 - 1:
            fixes.append(f"{v.id}: too big to stack on {to.id}, attached instead")
            mode, pl["side"] = "attach", pl.get("side") or "e"
        else:
            x0 = tx0 + (tx1 - tx0 + 1 - W) // 2 + int(pl.get("x") or 0)
            z0 = tz0 + (tz1 - tz0 + 1 - D) // 2 + int(pl.get("z") or 0)
            x0 = max(tx0 + 1, min(x0, tx1 - W))
            z0 = max(tz0 + 1, min(z0, tz1 - D))
            v.x0, v.z0, v.y0 = x0, z0, to.y0 + to.ry
            to.stacked_on_me = True
    if mode == "attach" and to:
        tx0, tz0, tx1, tz1 = to.bbox()
        side, gap, al = pl.get("side") or "e", max(0, int(pl.get("gap") or 0)), pl.get("align") or "center"

        def along(lo, hi, n):
            return {"start": lo, "end": hi - n + 1}.get(al, lo + (hi - lo + 1 - n) // 2) + off
        if side == "e":
            v.x0, v.z0 = tx1 + 1 + gap, along(tz0, tz1, D)
        elif side == "w":
            v.x0, v.z0 = tx0 - gap - W, along(tz0, tz1, D)
        elif side == "s":
            v.x0, v.z0 = along(tx0, tx1, W), tz1 + 1 + gap
        else:
            v.x0, v.z0 = along(tx0, tx1, W), tz0 - gap - D
        v.y0 = to.y0
    if mode not in ("attach", "stack"):
        v.x0, v.z0 = int(pl.get("x") or 0), int(pl.get("z") or 0)
    v.fp = {(x + v.x0, z + v.z0) for x, z in loc}
    step = {"e": (1, 0), "w": (-1, 0), "s": (0, 1), "n": (0, -1)}.get(pl.get("side") or "e", (1, 0))
    for _ in range(MAX_SIDE):
        hit = _overlaps(v, placed)
        if not hit:
            break
        v.x0 += step[0]
        v.z0 += step[1]
        v.fp = {(x + step[0], z + step[1]) for x, z in v.fp}
    else:
        fixes.append(f"{v.id}: could not clear an overlap")
    placed.append(v)


def _build_vol(v: Vol, kit: str, roles: dict, seed: int):
    r = {**roles, **_roles(v.s.get("roles"))}
    roof = "flat" if v.stacked_on_me else v.roof
    ents = [e for e in (v.s.get("entrances") or ["s"]) if e in SIDES] or ["s"]
    af = int(v.s.get("accent_floor") if v.s.get("accent_floor") is not None else 0)
    blocks = massing.structure(
        shape=v.shape, w=v.w, d=v.d, r=v.r,
        cut_w=min(int(v.s.get("cut_w") or 0) or v.w // 2, v.w - 9), cut_d=min(int(v.s.get("cut_d") or 0) or v.d // 2, v.d - 9),
        floor_hs=v.hs, program=[p.split("+") if "+" in p else p for p in v.prog], kit=kit, roles=r or None,
        windows=v.s.get("windows") or "band", rhythm=int(v.s.get("rhythm") or 0) % 4, roof=roof,
        accent_floor=af if 0 <= af < len(v.hs) else None, open_ground=bool(v.s.get("open_ground")),
        entrances=ents, seed=seed, antennas=0 if v.stacked_on_me else 1, roof_details=0 if v.stacked_on_me else 2)
    # massing normalises the footprint to start at 0,0 (depth adds -1 outward); shift by the volume's corner
    fp0 = massing.footprint(v.shape, v.w, v.d, v.r, cut_w=min(int(v.s.get("cut_w") or 0) or v.w // 2, v.w - 9),
                            cut_d=min(int(v.s.get("cut_d") or 0) or v.d // 2, v.d - 9))
    mx, mz = min(p[0] for p in fp0), min(p[1] for p in fp0)
    v.blocks = [[x - mx + v.x0, y + v.y0, z - mz + v.z0, b] for x, y, z, b in blocks]


def _interior(v: Vol) -> set:
    return massing._shrink(massing._shrink(v.fp)) if len(v.fp) > 16 else set()


class Site:
    """Merged block dict with ownership: a block outside its volume never lands inside another volume's body."""

    def __init__(self, vols: list):
        self.vols = vols
        self.cells: dict = {}
        self.src: dict = {}
        self.inner = {v.id: _interior(v) for v in vols}

    def owners(self, x, y, z):
        return [v for v in self.vols if (x, z) in v.fp and v.y0 <= y <= v.y0 + v.ry]

    def put_vol(self, v: Vol):
        for x, y, z, b in v.blocks:
            own = self.owners(x, y, z)
            if own and v not in own:
                continue
            if b == AIR and (x, z) not in v.fp:
                continue
            self.cells[(x, y, z)] = b
            self.src[(x, y, z)] = v.id

    def put_feature(self, x, y, z, b, override=False):
        for v in self.owners(x, y, z):
            if (x, z) in self.inner[v.id]:
                return
        if not override and self.cells.get((x, y, z)) not in (None, AIR) and self.owners(x, y, z):
            return
        self.cells[(x, y, z)] = b
        self.src[(x, y, z)] = "features"

    def top(self, x, z, default=0):
        ys = [y for (cx, y, cz), b in self.cells.items() if cx == x and cz == z and b != AIR]
        return max(ys) if ys else default


def _doorway(site: Site, a: Vol, b: Vol, side: str):
    """3-wide doorway through the shared wall of two touching volumes (both have 2 rings of facade)."""
    xs = sorted({p[0] for p in a.fp} & {p[0] for p in b.fp}) if side in "ns" else []
    zs = sorted({p[1] for p in a.fp} & {p[1] for p in b.fp}) if side in "ew" else []
    span = xs or zs
    if len(span) < 5:
        return False
    mid = span[len(span) // 2]
    ax0, az0, ax1, az1 = a.bbox()
    if side == "e":
        cut = [(ax1 + k, t) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
    elif side == "w":
        cut = [(ax0 - k, t) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
    elif side == "s":
        cut = [(t, az1 + k) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
    else:
        cut = [(t, az0 - k) for k in (-1, 0, 1, 2) for t in (mid - 1, mid, mid + 1)]
    hgt = min(4, a.hs[0] - 1, b.hs[0] - 1)
    y0 = max(a.y0, b.y0)
    for (x, z) in cut:
        for y in range(y0 + 1, y0 + 1 + hgt):
            site.cells.pop((x, y, z), None)
    return True


def _side_cells(v: Vol, side: str) -> list:
    """(x, z) just outside v's footprint along a side, ordered west->east / north->south."""
    d = {"e": (1, 0), "w": (-1, 0), "s": (0, 1), "n": (0, -1)}[side]
    out = sorted({(x + d[0], z + d[1]) for x, z in v.fp if (x + d[0], z + d[1]) not in v.fp},
                 key=lambda p: (p[1], p[0]) if side in "ew" else (p[0], p[1]))
    return out


def _feature(site: Site, f: dict, by_id: dict, K: dict, kit: str, roles: dict, report: list, i: int):
    kind, v = f.get("kind"), by_id.get(f.get("on"))
    if kind == "platform":
        return
    if v is None:
        report.append(f"feature {kind}: no volume {f.get('on')!r}, skipped")
        return
    side = f.get("side") if f.get("side") in SIDES + ["top"] else "s"
    pos = min(1.0, max(0.0, float(f.get("pos") if f.get("pos") is not None else 0.5)))
    size = int(f.get("size") or 0)
    x0, z0, x1, z1 = v.bbox()
    H = sum(v.hs)
    put = site.put_feature
    if kind == "spire":
        h = max(8, min(40, size or 16))
        base = 5 if min(x1 - x0, z1 - z0) >= 10 else 3
        cx, cz = (x0 + x1) // 2 - base // 2, (z0 + z1) // 2 - base // 2
        y = max(site.top(cx + a, cz + c) for a in range(base) for c in range(base)) + 1
        for x, yy, z, b in massing.spire(h=h, base=base, kit=kit, roles=roles):
            put(cx + x, y + yy, cz + z, b)
    elif kind == "chimney":
        if side == "top":
            side = "n"
        cells = _side_cells(v, side)
        if len(cells) < 3:
            return
        x, z = cells[min(len(cells) - 2, int(pos * (len(cells) - 2)))]
        if side == "w":
            x -= 1
        if side == "n":
            z -= 1
        h = v.ry + max(3, min(20, size or 6))
        tmp: list = []
        campus._chimney(tmp, x, z, v.y0 + 1, h, K)
        for bx, by, bz, b in tmp:
            put(bx, by, bz, b)
    elif kind == "gear":
        if side == "top":
            side = "s"
        cells = _side_cells(v, side)
        if not cells:
            return
        r = max(2, min(6, size or 3))
        lv = max(0, min(len(v.hs) - 1, int(f.get("level") or 0)))
        cy = v.y0 + 1 + sum(v.hs[:lv]) + v.hs[lv] // 2
        cy = max(cy, v.y0 + r + 2)
        if cy + r + 1 >= v.y0 + v.ry:
            r = max(2, v.y0 + v.ry - cy - 2)
        ax, az = cells[int(pos * (len(cells) - 1))]
        tmp = []
        campus._gear(tmp, 0, cy, 0, r, K)
        for gx, gy, _gz, b in tmp:
            if side in "ns":
                put(ax + gx, gy, az, b, True)
            else:
                put(ax, gy, az + gx, b, True)
    elif kind == "pipes":
        sides = [side if side in SIDES else "s"] + [s for s in SIDES if s != side][:1]
        tmp = []
        campus._pipes(tmp, x0, z0, x1 - x0 + 1, z1 - z0 + 1, H, v.y0, sides, K, i)
        for bx, by, bz, b in tmp:
            put(bx, by, bz, b, True)
    elif kind == "buttresses":
        tmp = []
        campus._buttresses(tmp, x0, z0, x1 - x0 + 1, z1 - z0 + 1, H, v.y0 + 1, K, [side if side in SIDES else "s"])
        for bx, by, bz, b in tmp:
            put(bx, by, bz, b)
    elif kind == "bridge":
        w = by_id.get(f.get("to"))
        if w is None:
            report.append(f"bridge from {v.id}: no target {f.get('to')!r}")
            return
        wx0, wz0, wx1, wz1 = w.bbox()
        lv = max(0, min(len(v.hs) - 1, len(w.hs) - 1, int(f.get("level") or 0)))
        y = max(v.y0 + sum(v.hs[:lv]), w.y0 + sum(w.hs[:lv]))
        if wx0 > x1 + 2 or x0 > wx1 + 2:  # gap along x
            a, b_ = (x1 + 1, wx0 - 1) if wx0 > x1 else (wx1 + 1, x0 - 1)
            zlo, zhi = max(z0, wz0), min(z1, wz1)
            if zhi - zlo < 4:
                report.append(f"bridge {v.id}->{w.id}: faces don't overlap")
                return
            zc = (zlo + zhi) // 2 - 2
            for x, yy, z, b in massing.bridge(length=b_ - a + 1, along="x", width=5, height=4, kit=kit, roles=roles):
                put(a + x, y + yy, zc + z, b)
        elif wz0 > z1 + 2 or z0 > wz1 + 2:
            a, b_ = (z1 + 1, wz0 - 1) if wz0 > z1 else (wz1 + 1, z0 - 1)
            xlo, xhi = max(x0, wx0), min(x1, wx1)
            if xhi - xlo < 4:
                report.append(f"bridge {v.id}->{w.id}: faces don't overlap")
                return
            xc = (xlo + xhi) // 2 - 2
            for x, yy, z, b in massing.bridge(length=b_ - a + 1, along="z", width=5, height=4, kit=kit, roles=roles):
                put(xc + x, y + yy, a + z, b)
        else:
            report.append(f"bridge {v.id}->{w.id}: no gap >= 3 between them, skipped")


def compose(spec: dict, seed: int = 1) -> tuple[list, dict]:
    """Spec -> (ghosts [{id, origin, blocks}], report). Deterministic; never calls a model."""
    spec = copy.deepcopy(spec)
    fixes: list = []
    kit = spec.get("kit") if spec.get("kit") in massing.KITS else "steampunk"
    roles = _roles(spec.get("roles"))
    K = massing._kit(kit, roles)
    raw = list(spec.get("volumes") or [])[:MAX_VOLUMES]
    if not raw:
        raise ValueError("design has no volumes")
    seen = set()
    vols = []
    for s in raw:
        v = Vol(s, fixes)
        while v.id in seen:
            v.id += "_"
        seen.add(v.id)
        vols.append(v)
    by_id = {v.id: v for v in vols}
    vols[0].place["mode"] = "at"
    # place in dependency order (a target first)
    placed: list = []
    todo = list(vols)
    for _ in range(len(vols) + 1):
        rest = []
        for v in todo:
            t = v.place.get("to")
            if v.place.get("mode") in ("attach", "stack") and t in by_id and by_id[t] not in placed and by_id[t] is not v:
                rest.append(v)
            else:
                _place(v, by_id, placed, fixes)
        if not rest or len(rest) == len(todo):
            for v in rest:
                v.place["to"] = None
                _place(v, by_id, placed, fixes)
            break
        todo = rest
    # platform: lift everything
    plat = next((f for f in spec.get("features") or [] if f.get("kind") == "platform"), None)
    lift = max(1, min(3, int(plat.get("size") or 2))) if plat else 0
    for v in vols:
        v.y0 += lift
    # normalise so the site starts at 0,0
    mx = min(p[0] for v in vols for p in v.fp) - (lift * 2 + 2 if plat else 1)
    mz = min(p[1] for v in vols for p in v.fp) - (lift * 2 + 2 if plat else 1)
    for v in vols:
        v.fp = {(x - mx, z - mz) for x, z in v.fp}
        v.x0 -= mx
        v.z0 -= mz
    for i, v in enumerate(vols):
        _build_vol(v, kit, roles, seed + i)
    site = Site(vols)
    for v in vols:
        site.put_vol(v)
    doors = 0
    for v in vols:
        t = by_id.get(v.place.get("to"))
        if v.place.get("mode") == "attach" and t and int(v.place.get("gap") or 0) == 0 and t.y0 == v.y0:
            doors += _doorway(site, t, v, v.place.get("side") or "e")
    report: list = []
    if plat:
        xs = [x for (x, _, _) in site.cells]
        zs = [z for (_, _, z) in site.cells]
        pw, pd = max(xs) + 3, max(zs) + 3
        for x, y, z, b in massing.platform(shape="rect", w=pw, d=pd, steps=lift, kit=kit, roles=roles):
            if (x, y, z) not in site.cells:
                site.cells[(x, y, z)] = b
                site.src[(x, y, z)] = "platform"
    for i, f in enumerate(spec.get("features") or []):
        _feature(site, f, by_id, K, kit, roles, report, i)
    ghosts = {}
    for (x, y, z), b in site.cells.items():
        ghosts.setdefault(site.src[(x, y, z)], []).append([x, y, z, b])
    order = [v.id for v in vols] + ["platform", "features"]
    out = [{"id": g, "origin": [0, 0, 0], "blocks": ghosts[g]} for g in order if ghosts.get(g)]
    rep = {"kit": kit, "concept": spec.get("concept", ""), "fixes": fixes, "notes": report, "doorways": doors,
           "volumes": [{"id": v.id, "shape": v.shape, "corner": [v.x0, v.y0, v.z0], "size": list(map(int, (
               v.bbox()[2] - v.bbox()[0] + 1, v.ry + 1, v.bbox()[3] - v.bbox()[1] + 1))), "floors": v.hs,
               "program": v.prog, "roof": "flat" if v.stacked_on_me else v.roof,
               "clear_inside": [v.bbox()[2] - v.bbox()[0] - 3, v.bbox()[3] - v.bbox()[1] - 3]} for v in vols],
           "blocks": sum(len(g["blocks"]) for g in out)}
    return out, rep
