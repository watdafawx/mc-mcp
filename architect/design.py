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
import math
import os
from pathlib import Path

import shapes  # noqa: F401  (must load before massing: circular import)
import massing
import campus
import motifs
import palette

HERE = Path(__file__).resolve().parent
REFS = HERE / "knowledge" / "style_refs"
MODEL = os.environ.get("ARCHITECT_DESIGN_MODEL", "claude-sonnet-5-5")
EFFORT = os.environ.get("ARCHITECT_DESIGN_EFFORT", "medium")
# USD per million tokens (input, output); cache reads ~10%, writes ~125%.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}

KITS = sorted(massing.KITS)
ROOFS = ["flat", "mansard", "dome", "crown"] + sorted(massing.HF_ROOFS)
SHAPES = ["rect", "octagon", "round", "L", "ring"]
RING_ROOFS = ("flat", "mansard", "garden", "crown")  # roofs that make sense on an annulus (no centre finial / dome)
MAX_RING_R = 40
SIDES = ["n", "s", "e", "w"]
ROLES = ["base", "wall", "wall2", "trim", "pillar", "accent", "glass", "glow", "rail", "roof", "detail", "antenna", "tip"]
PROGRAM = ["machine_hall", "expansion", "workshop", "lab", "storage", "hall", "living"]
FEATURES = ["spire", "chimney", "buttresses", "bridge", "platform"] + [m for m in motifs.ALL if m not in ("spire",)]
ALIAS = {"pipes": "pipe_rack"}
INDUSTRIAL = ("steampunk", "rust_industrial", "cyber_dark", "station_white", "ae_sky")  # porch default style
# minimum clear floor height per room kind: modded setups are pipe/cable heavy or big multiblocks
MIN_H = {"machine_hall": 9, "expansion": 9, "workshop": 6, "lab": 6, "storage": 5, "hall": 6, "living": 4}
BIG = {"machine_hall", "expansion"}
MAX_VOLUMES, MAX_SIDE, MAX_R, MAX_H = 12, 64, 24, 60
MIN_BAND, MAX_BAND = 9, 24  # ring band thickness (radial blocks); big programs use 13
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
            "mode": {"type": "string", "enum": ["at", "attach", "stack", "around"]},
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
Ring: shape "ring" is a band built AROUND another volume: place.mode "around", place.to = the core's id (list the core first).
w = band thickness in blocks (>= 9, >= 13 for machine_hall/expansion; interiors stay big, detail goes outward), r/d/cut_* 0.
place.gap 0 = the ring's inner wall sits against the core, with doorways at N/E/S/W; gap >= 2 = an open courtyard
(1 is bumped to 2). The engine keeps the ring LOWER than its core, so make the core the tall landmark (a round or
octagon core hugs best). Wall features need a flat stretch the ring does not have (skipped); landing_pad / crane / water_tank
fit on the roof only where the band is wide enough. Example, a ring of labs around a round core tower: volume `core`
{shape round, r 9, floor_hs [8,6,6,6], program [hall,lab,lab,lab], roof dome, place at 0,0} + volume `labs` {shape ring, w 10,
floor_hs [6,6], program [lab,lab], roof flat, windows grid, entrances [s], place {mode around, to core, gap 0}}.

Colour fidelity (hard): the visible facade is mostly pillar (piers, ~40%) + wall2 (infill) + base + trim, so the main
colour the brief names (red brick, red timber, white panels) goes on BOTH pillar and wall2; trim/base are a contrasting
secondary, the kit's dark stones only where the brief allows. Sci-fi briefs: replace gothic-looking piers with smooth
or concrete blocks.
Red materials: red brick = minecraft:bricks; red timber = minecraft:mangrove_planks / stripped_mangrove_log with
dark_oak or spruce posts; NEVER crimson_* or warped_* (they render magenta/teal). Each volume may set its own roles
(e.g. glass labs: wall2 = glass; the core tower: a different trim) so volumes read as distinct parts of one theme.
Materials: pick the kit closest to the brief, then override roles where the brief needs it (role -> vanilla or listed
block id that really exists; e.g. a brick factory: wall2 minecraft:bricks, pillar minecraft:stone_bricks). Roles:
base = plinth and skirt, wall2 = main wall infill, pillar = piers between bays, trim = ledges, sills, cornice,
wall = bands and parapet, accent = stripe floor, glass, glow = light bands, roof, detail = rooftop units, rail,
antenna, tip. Keep ~3 main materials (60/30/10). Per-volume roles override for one volume (e.g. a copper roof on the tower).

Features: spire (on top of `on`, size = height), chimney (2x2 stack against `on`'s `side` wall at pos 0-1, size =
height above the roof), gear (cog on a BLANK stretch of wall only: put it on a windowless end wall or a volume with windows none/slit
and a floor >= 10 high, else it is skipped; size = radius 3-5, level = floor index), clock (clock face on the
landmark's `side`, top floor unless level is set, size = radius 3-6), pipe_rack (thin pipe run with risers and valves
along `on`'s `side` wall), pagoda (stacked flared-eave pagoda roof over `on`, size = tiers 1-4; replaces its roof),
buttresses (gothic flying buttresses on `side`),
porch (entrance canopy over the ground-floor doorway on `on`'s `side`; size 1 = classic columns + pediment, 2 = industrial
steel canopy, 0 = by kit; skipped if that side has no entrance), balcony (slab balcony with rail and stair brackets over
a window of `on`'s `side`, upper floors only; level = floor index, size = half-width 1-3), blade_sign (vertical projecting
glow sign on `on`'s `side` at head height, pos along the wall; shopfront / cyberpunk streets), timber_frame (half-timber
overlay on `on`'s whole `side` wall: posts at the piers, floor beams, diagonal braces in blank panels; replaces wall blocks
only), smokestack (round tapering brick stack standing on the ground beside `on`'s `side` wall, pos along it, size = height
above its roof), water_tank (stilted wooden tank with ladder on the roof of `on`, near a corner; side top; size = height
6-14), landing_pad (round helipad with H, edge lights and windsock on the flat roof of `on`; side top; roof >= 13 wide),
crane (tower crane with cab, jib and counterweight on the roof of `on`; side top; size = mast height 8-30; roof >= 17 x 11;
use another roof than the water tank),
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
    resp = _ask(client, kw)
    if resp.stop_reason == "refusal":
        raise RuntimeError("designer refused the brief")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), cost_of(resp.usage, getattr(resp, "model", MODEL) or MODEL)


def _ask(client, kw: dict):
    """One streamed call with server-side refusal fallbacks; plain stream on endpoints without the beta."""
    try:
        with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw) as s:
            return s.get_final_message()
    except Exception as e:  # local / proxied endpoints without the beta: plain call
        if "fallback" not in str(e).lower() and "beta" not in str(e).lower():
            raise
        with client.messages.stream(**kw) as s:
            return s.get_final_message()


# ---------------------------------------------------------------- the critique call (step 5)

CRITIC_MODEL = os.environ.get("ARCHITECT_CRITIC_MODEL", "claude-sonnet-5-5")
CRITIC_EFFORT = os.environ.get("ARCHITECT_CRITIC_EFFORT", "medium")
CRITIC_SCHEMA = _obj({"flaws": {"type": "array", "items": _obj({"what": _STR, "fix": _STR})}, "spec": SCHEMA})

CRITIC_RUBRIC = """

You are now the CRITIC. You get the brief, the current design spec, the composer's report (what it fixed or skipped) and
screenshots of the build as the engine made it (SE and NW isometric, plus a street-level view). The bar is the user's own:
"they have a theme they follow, every block looks intentional, and they are not just basic shapes".
Judge only what you can see and what the report says. Check, in this order:
1. Theme and colour fidelity: do the visible materials match the brief (the colour it names on the facade, not the kit's default
   stone)? One theme followed everywhere?
2. Silhouette: one clear landmark, clearly taller than the rest, roof lines stepping down from it. A ring (shape ring, mode
   around) is the right answer when the brief says "around a core"; boxes standing next to it are not.
3. Composition: volumes hug each other (attached, stacked, around); nothing scattered in boxes with yards between, nothing
   floating, clipped or poking through another volume.
4. Facade depth and motifs: porches, balconies, clocks, timber frames, signs, pipe runs, a pad or crane where they read in the
   pictures; plain flat walls with nothing on them are a flaw.
5. The report's notes: every feature it SKIPPED ("no blank wall", "no spot", "too narrow", "no flat stretch"...) is a feature the
   designer wanted: move it to a volume / side / size where it fits (a blank end wall, a windowless volume, a wider roof), or
   replace it with one that fits. Every composer fix is a hint of a bad number in the spec.
Hard rules: never shrink floor heights or footprints (w, d, r, ring band) of machine_hall / expansion volumes or of any volume
with big interiors: modded machines and multiblocks need the room; detail goes outward. You may enlarge them. Keep volume ids
stable so placements still resolve.
Return `flaws`: the 0-6 real problems you see (what = the visible problem, fix = the concrete spec change you made for it), and
`spec`: the complete corrected spec (same schema as always, every field). If the build is already good, return flaws = []
and the spec exactly as given: do not change things for the sake of it."""


def _keep_big(old: dict, new: dict) -> list:
    """Undo any shrink of a big-program volume (machine_hall / expansion floors, footprint, ring band). Returns notes."""
    notes = []
    olds = {str(v.get("id")): v for v in old.get("volumes") or []}
    for v in new.get("volumes") or []:
        o = olds.get(str(v.get("id")))
        if o is None:
            continue
        prog = [str(p or "") for p in o.get("program") or []]
        if not any(k.strip() in BIG for p in prog for k in p.split("+")):
            continue
        hs_old = [int(h) for h in o.get("floor_hs") or []]
        hs = [int(h) for h in v.get("floor_hs") or []]
        if len(hs) < len(hs_old):  # dropped floors of a big program: put the old ones back
            notes.append(f"{v.get('id')}: floors restored to {hs_old} (big program)")
            hs, v["program"] = hs_old, list(o.get("program") or [])
        else:
            for i, h in enumerate(hs_old):
                kinds = prog[min(i, len(prog) - 1)]
                if any(k.strip() in BIG for k in kinds.split("+")) and hs[i] < h:
                    notes.append(f"{v.get('id')}: floor {i} height kept at {h} (big program)")
                    hs[i] = h
        v["floor_hs"] = hs
        if o.get("shape") == v.get("shape"):
            for k in ("w", "d", "r"):
                if int(v.get(k) or 0) < int(o.get(k) or 0):
                    notes.append(f"{v.get('id')}: {k} kept at {o.get(k)} (big program)")
                    v[k] = o.get(k)
    return notes


def critique(client, request: str, spec: dict, report: dict, shots: list) -> tuple[dict, list, float]:
    """One critic call: brief + spec + compose report + screenshots -> (new spec, flaws [{what, fix}], cost USD).
    shots: [(label, base64 png)]. No flaws -> the spec comes back exactly as given."""
    rep = {k: report.get(k) for k in ("kit", "fixes", "notes", "doorways", "volumes", "blocks")}
    content = [{"type": "text", "text": f"Brief: {request}\n\nCurrent spec:\n{json.dumps(spec, indent=1)}\n\n"
                                        f"Composer report:\n{json.dumps(rep, indent=1)}\n\nScreenshots follow."}]
    for label, b64 in shots:
        content.append({"type": "text", "text": f"Screenshot: {label}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
    content.append({"type": "text", "text": "Critique the build against the rubric and return flaws + the corrected spec."})
    kw = dict(model=CRITIC_MODEL, max_tokens=16000, system=SYSTEM + CRITIC_RUBRIC,
              messages=[{"role": "user", "content": content}], thinking={"type": "adaptive"},
              output_config={"effort": CRITIC_EFFORT, "format": {"type": "json_schema", "schema": CRITIC_SCHEMA}})
    resp = _ask(client, kw)
    if resp.stop_reason == "refusal":
        raise RuntimeError("critic refused")
    cost = cost_of(resp.usage, getattr(resp, "model", CRITIC_MODEL) or CRITIC_MODEL)
    got = json.loads(next(b.text for b in resp.content if b.type == "text"))
    flaws = [{"what": str(f.get("what", "")), "fix": str(f.get("fix", ""))} for f in got.get("flaws") or []]
    new = got.get("spec")
    if not flaws or not isinstance(new, dict) or not new.get("volumes"):
        return spec, flaws, cost
    new = copy.deepcopy(new)
    for note in _keep_big(spec, new):
        flaws.append({"what": "(guard) " + note, "fix": "restored"})
    return new, flaws, cost


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
        self.r_in = 0
        self.big = big
        if self.shape == "ring":  # w = band thickness; r / r_in are set by _place from the core
            lo = 13 if big else MIN_BAND
            self.band = max(lo, min(MAX_BAND, int(s.get("w") or 0) or lo))
            if int(s.get("w") or 0) != self.band:
                fixes.append(f"{self.id}: ring band {s.get('w')} -> {self.band}")
            self.w = self.d = self.band
        for k, v in (("w", self.w), ("d", self.d)):
            if self.shape not in ("round", "ring") and int(s.get(k) or 0) != v:
                fixes.append(f"{self.id}: {k} {s.get(k)} -> {v}")
        self.roof = s.get("roof") if s.get("roof") in ROOFS else "flat"
        if self.shape == "ring" and self.roof not in RING_ROOFS:
            fixes.append(f"{self.id}: roof {self.roof} -> flat (a ring has no centre for it)")
            self.roof = "flat"
        self.place = dict(s.get("place") or {})
        self.x0 = self.z0 = self.y0 = 0
        self.fp: set = set()
        self.blocks: list = []
        self.stacked_on_me = False

    def footprint(self) -> set:
        if self.shape == "round":
            fp = massing.footprint("round", r=self.r)
        elif self.shape == "ring":
            fp = massing.footprint("ring", r=self.r, r_in=self.r_in)
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

    @property
    def is_ring(self) -> bool:
        return self.shape == "ring"

    @property
    def around(self) -> str | None:
        return self.place.get("to") if self.place.get("mode") == "around" else None

    def centre(self) -> tuple:
        """Integer centre cell of the footprint's bounding box (the round core's own centre cell)."""
        x0, z0, x1, z1 = self.bbox()
        return (x0 + x1) // 2, (z0 + z1) // 2

    def bbox(self):
        xs = [p[0] for p in self.fp]
        zs = [p[1] for p in self.fp]
        return min(xs), min(zs), max(xs), max(zs)


def _overlaps(v: Vol, others: list) -> Vol | None:
    for o in others:
        if o is v or not o.fp or v.place.get("mode") in ("stack", "around") and o.id == v.place.get("to"):
            continue
        y_ok = v.y0 <= o.y0 + o.ry and o.y0 <= v.y0 + v.ry
        if y_ok and v.fp & o.fp:
            return o
    return None


def _cap_ring(v: Vol, core: Vol, fixes: list):
    """The core is the landmark: a ring stays >= 2 blocks lower (>= 1 when the program's minimum floor heights leave
    no room), by dropping top floors, then shrinking the only floor; programs keep their minimum floor height."""
    def fit(tgt):
        hs, prog = list(v.hs), list(v.prog)
        while sum(hs) + 1 > tgt and len(hs) > 1:
            hs.pop()
            prog.pop()
        if sum(hs) + 1 > tgt:
            need = max(MIN_H.get(k.strip(), 4) for k in prog[0].split("+"))
            if tgt - 1 < need:
                return None
            hs[0] = tgt - 1
        return hs, prog
    if v.ry <= core.ry - 3:
        return
    got = fit(core.ry - 3) or (fit(core.ry - 1) if v.ry > core.ry - 1 else (v.hs, v.prog))
    if got is None:
        fixes.append(f"{v.id}: cannot be kept lower than its core {core.id} (minimum floor heights), core is {core.ry}, ring {v.ry}")
        return
    old = list(v.hs)
    v.hs, v.prog = got
    if v.hs != old:
        fixes.append(f"{v.id}: ring height {sum(old) + 1} >= core {core.id} {core.ry}: floors {old} -> {v.hs} so the core stays the landmark")


def _place_ring(v: Vol, core: Vol, placed: list, fixes: list):
    pl = v.place
    gap = max(0, int(pl.get("gap") or 0))
    if gap == 1:
        fixes.append(f"{v.id}: gap 1 is an unusable alley, made 2 (courtyard)")
        gap = 2
    pl["gap"] = gap
    cx, cz = core.centre()
    rc = max(math.hypot(x - cx, z - cz) for x, z in core.fp)
    v.r_in = int(rc + 0.45) + 1 + gap
    band = v.band
    if v.r_in + band > MAX_RING_R:
        band = max(MIN_BAND, MAX_RING_R - v.r_in)
        fixes.append(f"{v.id}: ring too wide for the site, band {v.band} -> {band}")
    v.r = v.r_in + band
    for _ in range(4):  # never touch the core: grow the inner radius until the footprints are apart
        loc = v.footprint()
        v.fp = {(x + cx - v.r, z + cz - v.r) for x, z in loc}
        if not (v.fp & core.fp):
            break
        v.r_in += 1
        v.r += 1
    v.x0, v.z0, v.y0 = cx - v.r, cz - v.r, core.y0
    _cap_ring(v, core, fixes)
    hit = _overlaps(v, placed)
    if hit:
        fixes.append(f"{v.id}: ring overlaps {hit.id} (a ring cannot be moved off its core)")
    placed.append(v)


def _place(v: Vol, by_id: dict, placed: list, fixes: list):
    pl0 = v.place
    if v.is_ring:
        core = by_id.get(pl0.get("to")) if pl0.get("mode") == "around" else None
        if core is not None and core is not v and core in placed and not core.is_ring:
            _place_ring(v, core, placed, fixes)
            return
        fixes.append(f"{v.id}: a ring needs a placed core volume to go around ({pl0.get('to')!r}); built as a round volume")
        v.shape, v.r = "round", max(8 if v.big else 5, min(MAX_R, v.band))
        pl0["mode"] = "at" if not placed else "attach"
        pl0.setdefault("side", "e")
        pl0["to"] = pl0.get("to") if by_id.get(pl0.get("to")) in placed else (placed[-1].id if placed else "")
    elif pl0.get("mode") == "around":
        fixes.append(f"{v.id}: mode around only works for a ring, attached instead")
        pl0["mode"] = "attach"
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
    rin = v.r_in if v.is_ring else None
    blocks = massing.structure(
        shape=v.shape, w=v.w, d=v.d, r=v.r, r_in=rin,
        cut_w=min(int(v.s.get("cut_w") or 0) or v.w // 2, v.w - 9), cut_d=min(int(v.s.get("cut_d") or 0) or v.d // 2, v.d - 9),
        floor_hs=v.hs, program=[p.split("+") if "+" in p else p for p in v.prog], kit=kit, roles=r or None,
        windows=v.s.get("windows") or "band", rhythm=int(v.s.get("rhythm") or 0) % 4, roof=roof,
        accent_floor=af if 0 <= af < len(v.hs) else None, open_ground=bool(v.s.get("open_ground")),
        entrances=ents, seed=seed, antennas=0 if v.stacked_on_me else 1, roof_details=0 if v.stacked_on_me else 2)
    # massing normalises the footprint to start at 0,0 (depth adds -1 outward); shift by the volume's corner
    fp0 = massing.footprint(v.shape, v.w, v.d, v.r, rin, cut_w=min(int(v.s.get("cut_w") or 0) or v.w // 2, v.w - 9),
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
        self.doors: set = set()  # doorway cells: features never cover them

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
        if (x, y, z) in self.doors:
            return
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
            site.doors.add((x, y, z))
    return True


def _ring_doors(site: Site, ring: Vol, core: Vol, notes: list) -> int:
    """3-wide doorways through the ring's inner wall on the 4 cardinal points: gap 0 also through the core's outer wall
    (walls touch), gap >= 2 into the courtyard. Open from y0+1 up to min(4, floor heights - 1)."""
    cx, cz = ring.centre()
    gap0 = int(ring.place.get("gap") or 0) == 0
    hgt = min(4, ring.hs[0] - 1, core.hs[0] - 1 if gap0 else 9)
    n = 0
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        line = [((cx + k * dx, cz + k * dz)) for k in range(1, ring.r + 2)]
        kr = next((k for k, p in enumerate(line, 1) if p in ring.fp), None)
        if kr is None:
            continue
        if gap0:
            kc = max((k for k, p in enumerate(line, 1) if p in core.fp and k < kr), default=None)
            if kc is None or kr != kc + 1:
                notes.append(f"{ring.id}: ring wall does not touch {core.id} on {'e' if dx > 0 else 'w' if dx < 0 else 's' if dz > 0 else 'n'} "
                             f"(non-round core), no doorway there")
                continue
            ks = range(kc - 1, kr + 3)
        else:
            ks = range(kr, kr + 3)
        for k in ks:
            for t in (-1, 0, 1):
                x, z = cx + k * dx + t * dz, cz + k * dz + t * dx
                for y in range(ring.y0 + 1, ring.y0 + 1 + hgt):
                    site.cells.pop((x, y, z), None)
                    site.doors.add((x, y, z))
        n += 1
    return n


def _ring_top(site: Site, v: Vol, kind: str, pos: float, size: int, K: dict, report: list):
    """A roof motif on a ring: slide it round the band until every cell of it stands on the deck (inside the parapet),
    nearest the point `pos` (0..1 = the way round, 0 = east, clockwise) on the band's mid line. Bigger variants first."""
    if kind not in motifs.ON_DECK:
        report.append(f"{kind} on {v.id}: needs a whole roof, not a ring, skipped")
        return
    deck = massing._shrink(v.fp)
    sizes = {"landing_pad": [(21, 21), (19, 19), (17, 17), (15, 15), (13, 13)], "crane": [(26, 13), (22, 12), (17, 11)],
             "water_tank": [(15, 15), (11, 11)]}[kind]
    cx, cz = v.centre()
    ang = 2 * math.pi * pos
    rm = (v.r_in + v.r) / 2
    tx, tz = cx + rm * math.cos(ang), cz + rm * math.sin(ang)
    x0, z0, x1, z1 = v.bbox()
    y = v.y0 + v.ry + 1
    for w, d in sizes:
        cells = motifs.TOP[kind](K, w, d, **({"size": size} if size else {}))
        if not cells:
            continue
        flat = [(a, c) for (a, _, c) in cells]
        anchors = sorted(((ax, az) for ax in range(x0, x1 - w + 2) for az in range(z0, z1 - d + 2)),
                         key=lambda p: math.hypot(p[0] + w / 2 - tx, p[1] + d / 2 - tz))
        for ax, az in anchors:
            if all((ax + a, az + c) in deck for a, c in flat):
                for (a, yy, c), b in cells.items():
                    site.put_feature(ax + a, y + yy, az + c, b, True)
                return
    report.append(f"{kind} on {v.id}: the ring band is too narrow for it, skipped")


def _side_cells(v: Vol, side: str) -> list:
    """(x, z) just outside v's footprint along a side, ordered west->east / north->south."""
    d = {"e": (1, 0), "w": (-1, 0), "s": (0, 1), "n": (0, -1)}[side]
    cells = {(x + d[0], z + d[1]) for x, z in v.fp if (x + d[0], z + d[1]) not in v.fp}
    if v.is_ring:  # only the outer side: not the hole / courtyard
        cx, cz = v.centre()
        cells = {c for c in cells if math.hypot(c[0] - cx, c[1] - cz) > (v.r_in + v.r) / 2}
    return sorted(cells, key=lambda p: (p[1], p[0]) if side in "ew" else (p[0], p[1]))


def _flat_side(v: Vol, side: str) -> list:
    """Edge cells (u=0) of v's flat face on `side`, in +v order (v grows to the right seen from outside)."""
    if side in "ns":
        zz = max(z for _, z in v.fp) if side == "s" else min(z for _, z in v.fp)
        cells = sorted((x, z) for x, z in v.fp if z == zz)
        return cells if side == "s" else cells[::-1]
    xx = max(x for x, _ in v.fp) if side == "e" else min(x for x, _ in v.fp)
    cells = sorted((x, z) for x, z in v.fp if x == xx)
    return cells[::-1] if side == "e" else cells


def _glassy(b) -> bool:
    return bool(b) and ("glass" in b or "pane" in b)


def _wall_spot(site: Site, v: Vol, side: str, hw: int, h: int, ylo: int, yhi: int, pos: float, relaxed=False, ys=None, fits=None):
    """A stretch of v's `side` wall, 2*hw+1 wide and h high, with no window or doorway behind it (relaxed: windows ok,
    doorways never). Returns (edge cell at the centre, base y) nearest to pos / the top of [ylo, yhi], or None.
    ys: explicit base heights to try, in that order (floor lines for a balcony, head height for a sign).
    fits: optional filter fits(edge cell, base y) on a candidate (e.g. free ground and no other feature in front of it)."""
    cells = _flat_side(v, side)
    n = len(cells)
    if n < 2 * hw + 1:
        return None
    o = {"s": (0, 1), "n": (0, -1), "e": (1, 0), "w": (-1, 0)}[side]
    want = pos * (n - 1)
    for c in sorted(range(hw, n - hw), key=lambda c: abs(c - want)):
        for yb in (ys if ys is not None else sorted(range(v.y0 + 2, yhi - h + 1), key=lambda y: (y < ylo, -y))):
            ok = True
            for k in range(c - hw, c + hw + 1):
                ex, ez = cells[k]
                wx, wz = ex - o[0], ez - o[1]
                for y in range(yb, yb + h):
                    wb, eb = site.cells.get((wx, y, wz)), site.cells.get((ex, y, ez))
                    if wb in (None, AIR) and y <= v.y0 + 4 or (not relaxed and (_glassy(wb) or _glassy(eb))):
                        ok = False
                        break
                if not ok:
                    break
            if ok and (not fits or fits(cells[c], yb)):
                return c, yb
    return None


def _door_spot(site: Site, v: Vol, side: str, pos: float = 0.5):
    """The ground-floor doorway on v's `side`: a run of 3-5 wall-plane cells that are empty at y0+1..y0+3 (massing
    cuts entrances as air; windows, the sill course and open-ground colonnades do not qualify). Returns (index of the
    centre cell in _flat_side, ground y) nearest to pos, or None."""
    cells = _flat_side(v, side)
    o = {"s": (0, 1), "n": (0, -1), "e": (1, 0), "w": (-1, 0)}[side]
    if len(cells) < 7:
        return None
    gap = [all(site.cells.get((ex - o[0], y, ez - o[1])) in (None, AIR) for y in range(v.y0 + 1, v.y0 + 4))
           for ex, ez in cells]
    runs, i = [], 0
    while i < len(cells):
        if gap[i]:
            j = i
            while j + 1 < len(cells) and gap[j + 1]:
                j += 1
            if 3 <= j - i + 1 <= 5:
                runs.append((i + j) // 2)
            i = j + 1
        else:
            i += 1
    want = pos * (len(cells) - 1)
    return (min(runs, key=lambda c: abs(c - want)), v.y0) if runs else None


def _clear(site: Site, side: str, ax: int, az: int, u0: int, u1: int, hw: int, ys=()) -> bool:
    """True when the outside strip u0..u1 x v -hw..hw in front of edge cell (ax, az) touches no volume footprint and,
    over the heights `ys`, no feature block already placed there (another motif, a pipe riser, a chimney; the depth
    pass's pier feet and skirt are part of the volume and may be overwritten)."""
    for u in range(u0, u1 + 1):
        for vv in range(-hw, hw + 1):
            x, z = motifs.to_world(side, ax, az, u, vv)
            if any((x, z) in v.fp for v in site.vols) or any(site.src.get((x, y, z)) == "features" and site.cells.get((x, y, z), AIR) != AIR for y in ys):
                return False
    return True


def _place_cells(site: Site, cells: dict, side: str, ax: int, az: int, y0: int, soft: bool):
    """Frame a wall motif and put it; with soft, u=0 cells (the pier / ledge layer) never overwrite volume blocks."""
    edge = {k: b for k, b in cells.items() if soft and k[0] == 0}
    for x, y, z, b in motifs.frame({k: b for k, b in cells.items() if k not in edge}, side, ax, az, y0):
        site.put_feature(x, y, z, b, True)
    for x, y, z, b in motifs.frame(edge, side, ax, az, y0):
        site.put_feature(x, y, z, b, False)


def _motif(site: Site, v: Vol, kind: str, side: str, pos: float, size: int, f: dict, K: dict, report: list):
    if v.is_ring:
        if kind in motifs.TOP:
            _ring_top(site, v, kind, pos, size, K, report)
            return
        if len(_flat_side(v, "s" if side == "top" else side)) < 7:
            report.append(f"{kind} on {v.id} {side}: a ring has no flat stretch on that side, skipped")
            return
    if kind in motifs.TOP:
        x0, z0, x1, z1 = v.bbox()
        cells = motifs.TOP[kind](K, x1 - x0 + 1, z1 - z0 + 1, **({"tiers": size, "size": size} if size else {}))
        if not cells:
            report.append(f"{kind} on {v.id}: roof deck too small, skipped")
            return
        y = v.y0 + v.ry + 1
        for (x, yy, z), b in cells.items():
            if kind in motifs.ON_DECK and (x0 + x, z0 + z) not in v.fp:
                continue  # stands on the deck: nothing hangs over the edge of a round / octagon roof
            if any(o is not v for o in site.owners(x0 + x, y + yy, z0 + z)):
                continue  # never into another volume's shell (something stacked on this roof)
            site.put_feature(x0 + x, y + yy, z0 + z, b, True)
        return
    if side == "top":
        side = "s"
    if kind in motifs.LINE:
        cells = _flat_side(v, side)
        if not cells:
            return
        ax0, az0 = cells[0]

        def existing(u, vv, y):  # what the facade has there now, same frame as the motif (y up from the plinth)
            x, z = motifs.to_world(side, ax0, az0, u, vv)
            return site.cells.get((x, v.y0 + y, z))
        got = motifs.frame(motifs.LINE[kind](K, len(cells), v.hs, existing=existing), side, ax0, az0, v.y0)
        n = 0
        for x, y, z, b in got:
            if kind in motifs.OVERLAY:  # replace-only: never add to empty cells, never touch glass or doorways
                cur = site.cells.get((x, y, z))
                if cur in (None, AIR) or _glassy(cur) or (x, y, z) in site.doors:
                    continue
                site.cells[(x, y, z)] = b
                site.src[(x, y, z)] = "features"
            else:
                site.put_feature(x, y, z, b, True)
            n += 1
        if not n:
            report.append(f"{kind} on {v.id} {side}: nothing to replace, skipped")
        return
    if kind in motifs.DOOR:
        spot = _door_spot(site, v, side, pos)
        if not spot:
            report.append(f"{kind} on {v.id} {side}: no doorway on that side, skipped")
            return
        c, yb = spot
        ax, az = _flat_side(v, side)[c]
        if not _clear(site, side, ax, az, 1, 4, 3, range(yb + 1, yb + 8)):  # (the plinth-level skirt is overwritten)
            report.append(f"{kind} on {v.id} {side}: something else is in front of that doorway, skipped")
            return
        style = {1: "classic", 2: "industrial"}.get(size) or ("industrial" if f.get("_kit") in INDUSTRIAL else "classic")
        _place_cells(site, motifs.WALL[kind](K, style=style), side, ax, az, yb, False)
        return
    if kind in motifs.GROUND:
        cells = _flat_side(v, side)
        want = pos * (len(cells) - 1) if cells else 0
        p = {"h": v.ry + max(4, min(24, size or 6)) + 1}  # highest block = roof level + size
        for c in sorted(range(len(cells)), key=lambda c: abs(c - want)):
            ax, az = cells[c]
            if _clear(site, side, ax, az, 1, 5, 2, range(v.y0 + 1, v.y0 + p["h"])):
                _place_cells(site, motifs.WALL[kind](K, **p), side, ax, az, v.y0, False)
                return
        report.append(f"{kind} on {v.id} {side}: no free ground beside that wall, skipped")
        return
    lv = int(f.get("level") or 0)
    top = len(v.hs) - 1 if kind == "clock" and not lv else max(0, min(len(v.hs) - 1, lv))
    ylo = v.y0 + 1 + sum(v.hs[:top])
    yhi = v.y0 + v.ry
    spot, p, blind = None, {}, False
    if kind in motifs.ON_WINDOW:  # may sit over windows; the windows behind stay as they are
        if kind == "balcony":  # base y = one below a floor surface, upper floors only (level = which floor)
            lines = [v.y0 + sum(v.hs[:k]) for k in range(1, len(v.hs))]
            lines = [y for y in lines if y == v.y0 + sum(v.hs[:lv])] if lv else lines
        else:  # blade sign: bottom edge at head height or above, lowest first
            lines = list(range(v.y0 + 3, v.y0 + 9))
        for p in motifs.candidates(kind, size):
            hw, h = motifs.SIZE[kind](p)
            reach = 3 if kind == "blade_sign" else 2  # how far out it stands: that strip must be free ground / air
            spot = _wall_spot(site, v, side, hw, h, ylo, yhi, pos, relaxed=True, ys=[y for y in lines if y + h <= yhi + 1],
                              fits=lambda e, yb, hw=hw, h=h, reach=reach: _clear(site, side, e[0], e[1], 1, reach, hw,
                                                                                 range(yb, yb + h)))
            if spot:
                break
        if not spot:
            report.append(f"{kind} on {v.id} {side}: no spot, skipped")
            return
        c, yb = spot
        ax, az = _flat_side(v, side)[c]
        _place_cells(site, motifs.WALL[kind](K, **p), side, ax, az, yb, kind in motifs.SOFT_EDGE)
        return
    for blind in ((False,) if kind in motifs.BLANK_ONLY else (False, True)):  # blank wall first; else a blind panel (windows behind become wall), like a clock tower
        for p in motifs.candidates(kind, size):  # shrink the motif until it fits
            hw, h = motifs.SIZE[kind](p)
            spot = _wall_spot(site, v, side, hw, h, ylo, yhi, pos, relaxed=blind)
            if spot:
                break
        if spot:
            break
    if spot and blind:
        cells = _flat_side(v, side)
        o = {"s": (0, 1), "n": (0, -1), "e": (1, 0), "w": (-1, 0)}[side]
        c, yb = spot
        for k in range(max(0, c - hw - 1), min(len(cells), c + hw + 2)):
            ex, ez = cells[k]
            for y in range(yb - 1, yb + h + 1):
                for q in ((ex - o[0], y, ez - o[1]), (ex, y, ez)):
                    if _glassy(site.cells.get(q)):
                        site.cells[q] = K.get("wall2", K["trim"])
    if not spot:
        report.append(f"{kind} on {v.id} {side}: no blank wall, skipped")
        return
    c, yb = spot
    ax, az = _flat_side(v, side)[c]
    _place_cells(site, motifs.WALL[kind](K, **p), side, ax, az, yb, False)


def _feature(site: Site, f: dict, by_id: dict, K: dict, kit: str, roles: dict, report: list, i: int):
    kind, v = ALIAS.get(f.get("kind"), f.get("kind")), by_id.get(f.get("on"))
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
    if kind in motifs.WALL or kind in motifs.LINE or kind in motifs.TOP:
        _motif(site, v, kind, side, pos, size, {**f, "_kit": kit}, K, report)
        return
    if v.is_ring and kind in ("spire", "buttresses", "bridge"):
        report.append(f"{kind} on {v.id}: not for a ring, skipped")
        return
    if kind == "bridge" and by_id.get(f.get("to")) is not None and by_id[f["to"]].is_ring:
        report.append(f"bridge {v.id}->{f.get('to')}: not onto a ring, skipped")
        return
    if kind == "spire":
        h = max(8, min(40, size or 16))
        base = 5 if min(x1 - x0, z1 - z0) >= 10 else 3
        cx, cz = (x0 + x1) // 2 - base // 2, (z0 + z1) // 2 - base // 2
        cols = [(cx + a, cz + c) for a in range(base) for c in range(base)]
        for x, z in cols:  # the roof's own finial/antenna under the spire would hold it up in the air: drop it
            for (fx, fy, fz), b in list(site.cells.items()):
                if (fx, fz) == (x, z) and b in (K["antenna"], K["tip"]):
                    site.cells[(fx, fy, fz)] = AIR
        # sit on the lowest roof cell under the base (a hip/dome peak would otherwise leave it perched on one
        # block); roof blocks inside the base stay, the spire fills the air around them
        y = min(site.top(x, z) for x, z in cols) + 1
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
            if v.place.get("mode") in ("attach", "stack", "around") and t in by_id and by_id[t] not in placed and by_id[t] is not v:
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
    mx = min(p[0] for v in vols for p in v.fp) - (lift + 2 if plat else 3)
    mz = min(p[1] for v in vols for p in v.fp) - (lift + 2 if plat else 3)
    for v in vols:
        v.fp = {(x - mx, z - mz) for x, z in v.fp}
        v.x0 -= mx
        v.z0 -= mz
    for f in spec.get("features") or []:  # top motifs sit on a flat deck
        if f.get("kind") in motifs.TOP and f.get("on") in by_id:
            by_id[f["on"]].stacked_on_me = True
    for i, v in enumerate(vols):
        _build_vol(v, kit, roles, seed + i)
    site = Site(vols)
    for v in vols:
        site.put_vol(v)
    doors = 0
    report: list = []
    for v in vols:
        t = by_id.get(v.place.get("to"))
        if v.is_ring and v.around and t is not None:
            doors += _ring_doors(site, v, t, report)
        elif v.place.get("mode") == "attach" and t and int(v.place.get("gap") or 0) == 0 and t.y0 == v.y0:
            doors += _doorway(site, t, v, v.place.get("side") or "e")
    if plat:
        xs = [x for (x, _, _) in site.cells]
        zs = [z for (_, _, z) in site.cells]
        pw, pd = max(xs) + lift + 3, max(zs) + lift + 3
        for x, y, z, b in massing.platform(shape="rect", w=pw, d=pd, steps=lift, kit=kit, roles=roles):
            if (x, y, z) not in site.cells:
                site.cells[(x, y, z)] = b
                site.src[(x, y, z)] = "platform"
    PRIO = {"porch": 0, "clock": 1}  # doorways and the landmark's clock claim their wall before decoration does
    feats = sorted(enumerate(spec.get("features") or []), key=lambda t: (PRIO.get(t[1].get("kind"), 2), t[0]))
    for i, f in feats:
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
               "clear_inside": [v.bbox()[2] - v.bbox()[0] - 3, v.bbox()[3] - v.bbox()[1] - 3] if not v.is_ring
               else [v.r - v.r_in - 4] * 2, **({"ring": {"around": v.around, "r_in": v.r_in, "r": v.r, "band": v.r - v.r_in,
                                               "gap": int(v.place.get("gap") or 0)}} if v.is_ring else {})} for v in vols],
           "blocks": sum(len(g["blocks"]) for g in out)}
    return out, rep
