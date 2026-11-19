"""Haiku architect: designs themed rooms and areas as ghost builds in a running Minecraft client (via mc-mcp),
looks at them through screenshots, iterates, and exports schematics on request.

  python architect.py -s base "a quantum lab around the trinity core, sci-fi, purple and black"
  python architect.py -s base                 # interactive: keep giving feedback
  python architect.py -s base --chat          # in game: type "@claude <request>" in chat

Sessions live in sessions/<name>/ (conversation + plan), so iterations keep their context.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import anthropic

import blocklib
import campus
import floaters
import mods
import multiblocks
import refs as refs_mod
import shapes

HERE = Path(__file__).resolve().parent

import importlib.util as _ilu  # site.py shares its name with the stdlib `site` (already loaded): import it by path

_sp = _ilu.spec_from_file_location("arch_site", HERE / "site.py")
site = _ilu.module_from_spec(_sp)
sys.modules["arch_site"] = site
_sp.loader.exec_module(site)
FEATURE_MODS: list[str] = []  # --feature-mod: registered mod rooms the brief asks for
SITE: dict | None = None  # set from --survey: {survey, plan, near, force}; None = the old flat behaviour


def _load_dotenv(path: Path) -> None:
    """Reads KEY=VALUE lines from architect/.env into os.environ (never overrides, never prints a value)."""
    try:
        for line in path.read_text("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


_load_dotenv(HERE / ".env")
MODEL = os.environ.get("ARCHITECT_MODEL", "claude-haiku-5-5")
EFFORT = os.environ.get("ARCHITECT_EFFORT", "medium")
MCP_URL = os.environ.get("MCMCP_URL", "http://127.0.0.1:47861/mcp")
MODS_DIR = Path(os.environ.get("ARCHITECT_MODS", r"G:\Games\Minecraft\Curse\Instances\All the Mods 10 - ATM10\mods"))
KNOWLEDGE = HERE / "knowledge"
IMG3D_PY = Path(os.environ.get("ARCHITECT_IMG3D_PY", HERE / "img3d" / ".venv" / "Scripts" / "python.exe"))
# Screenshot paths come back as the game's paths. When the game runs on rig and this runs on FOX, rig's G: is Q:.
PATH_MAP = os.environ.get("ARCHITECT_PATH_MAP", "G:\\=Q:\\" if os.path.exists("Q:\\") else "")
MAX_STEPS = int(os.environ.get("ARCHITECT_MAX_STEPS", "60"))
MAX_COST = float(os.environ.get("ARCHITECT_MAX_COST", "0") or 0)  # USD per run, 0 = no cap (--max-cost)
# Local model mode: any server that speaks the Anthropic Messages API (Ollama 0.40+ on rig: http://192.168.50.3:11434).
# No web search, no effort/caching params, no cost.
BASE_URL = os.environ.get("ARCHITECT_BASE_URL", "")
LOCAL = bool(BASE_URL)
# Haiku 5.5 list prices per million tokens (cache reads ~10%, writes ~125%).
PRICE_IN, PRICE_OUT = 0.10, 0.50


def usage_cost(u) -> float:
    """Estimated USD for one response's `usage` (cache reads ~10%, writes ~125%). Also used by suggest.py."""
    cin = (u.input_tokens + (getattr(u, "cache_creation_input_tokens", 0) or 0) * 1.25
           + (getattr(u, "cache_read_input_tokens", 0) or 0) * 0.1)
    return (cin * PRICE_IN + u.output_tokens * PRICE_OUT) / 1e6

FORWARD = ["status", "registry_blocks", "block_describe", "ghost_set", "ghost_list", "ghost_info", "ghost_move",
           "ghost_show", "ghost_clear", "ghost_export"]

SYSTEM = """You are an architect for a modded Minecraft pack (All the Mods 10, MC 1.21.1). You design builds as GHOSTS:
see-through block layouts drawn only on the player's screen. Nothing is ever placed in the world. The player
looks at them, gives feedback, and you change them until they like it; ghost_export saves a schematic only when asked.

## Coordinates
- y is up. North = -z, south = +z, east = +x, west = -x.
- Each ghost has a world origin; its boxes/blocks use local coordinates from 0,0,0. Negative local coordinates
  are fine, and ghosts can go below the ground (foundations, cliffs, cellars): the terrain doesn't limit them.
- Room ghosts inside a campus (storage room, autocraft room, ...): use the campus result's wing room_origins[].origin as the ghost
  origin and LOCAL coordinates from 0,0,0 (never world coords together with an origin); anything off the campus is moved or rejected.
- Name ghosts "<area>/<room>", e.g. "core/hall", "core/server_room". One ghost per room or feature, so each can
  be moved, redrawn or hidden alone. Rooms of one area share an origin system: keep their world origins in the plan.
- Stairs: facing=<dir> is the side of the tall back. half=top flips them upside down (good for eaves and trims).
- Logs/pillars: axis=x|y|z. Slabs: type=bottom|top|double. Use full block-state strings in the palette.

## Workflow
1. Read the request. Call plan(action=get). For a new area, write a plan first with plan(action=set): areas,
   rooms (name, theme, purpose, world origin, size), how rooms connect (doors, corridors), and the overall style.
   Use knowledge(topic) for design principles, themes and room archetypes before planning anything big.
   Before any exterior: read knowledge(craft), pick ONE kit that fits the requested style, and call
   style_refs(kit) to see what the player expects.
2. Blocks must be CHEAP and survival-obtainable: the player builds this for real. Find blocks with
   blocks(shape, colour, max_cost, kw): it searches ~32k pack blocks (chipped, rechiseled, chisel, xtonesreworked,
   luminax glow cubes, create, mcw roofs/windows/fences/furniture/lights, connectedglass...) and shows their
   textures. Bulk blocks <= 3 cobble units, accents <= 6. Never use gold/diamond/emerald/netherite blocks, sea
   lanterns, prismarine, froglights, beacons or other expensive blocks in bulk. The kits are already cheap; use
   blocks() for variety (a textured panel block, a roof stair, window, lamp, furniture). block_describe for state
   properties. Never guess a mod block id. ghost_set reports bad_palette / unknown_keys: fix them at once.
   Before export, run bill(prefix/) and swap any expensive bulk block.
3. THE PLAYER'S TASTE: big and spread out, HORIZONTAL usable floor, not stacks of empty floors. Big areas for
   machines and other mods' setups, a ROOM PER MOD, or a WING per group of similar mods. Only the landmark is tall.
   For a base, retain the kit's default campus archetype unless the PLAYER explicitly asks for another layout.
   Do not switch to spine during palette/cost fixes; keep the existing layout and room coordinates.
   Preserve generated grass, gardens, covered halls, tiers and stairs. Never replace the platform with a full paving slab.
   The campus result lists every ghost's WORLD bounds (world_min/world_max), roof_deck_y and door_side: build extra
   details (chimneys, pipes, spires, signs, props) with coordinates taken from those numbers, touching a wall face,
   a roof deck (y = roof_deck_y+1) or the ground (y = site_min.y+1) so they attach on the first try. Floating parts
   are dropped; the drop report gives nearest_building_block and move_by_approx.
   Defaults: steampunk spine, hextech radial, gothic cloister, station_white linear, solarpunk terraces.
   For a base, start with ONE campus call: list the player's mods as wings (AE2 wing, Create/tech wing,
   processing wing, magic wing, farming...), each with a mod_room per mod plus one expansion room. Then make it
   theirs: per-wing roofs, roles overrides and blocks() picks for variety, rooftop clutter, the style's
   signature features (gears and pipes for steampunk, buttresses and pointed windows for gothic, green roofs
   and trees for solarpunk...), and the AE2 controller / quantum computer as the hub's showpiece. For a single
   building use the shapes tool's styled volumes (structure, platform, bridge, slope, spire), all in ONE kit,
   per knowledge(craft): a base, wings 1-2 floors with tall machine floors (floor_h 8-9), one landmark, a curve
   or angle, designed links. Write the layout in one sentence in the plan first. Never draw an exterior wall
   as a plain ghost_set box.
   Then interiors and details with ghost_set, multiblock and the classic shapes.
   Build room by room with ghost_set. Prefer boxes (fill | hollow | walls | frame) over single blocks; use blocks
   for details. Keep one ghost_set under ~3000 entries; split big rooms into several ghosts or calls with mode=merge.
   Use the shapes tool for anything boxes draw badly: round towers, cone/gable/hip roofs, domes, arches, window
   rows, battlements, pillar rows. Real roofs are made of stairs, never stepped full blocks. Block out the mass
   with boxes first, then add shapes on top (they merge into the ghost; air in a shape carves openings).
4. Working mod multiblocks (AE2 controller, crafting CPUs of every family, AdvancedAE quantum computer, ExtendedAE
   assembler matrix) must be
   made with the multiblock tool: it follows each mod's rules exactly. Never hand-place their parts. Design the
   room around them: pedestal, frame, lighting, sight lines. Don't put other blocks inside or touching their faces
   unless they are AE network blocks meant to connect.
5. After building, call view (iso first, then front/top). Every view comes back with one of the player's
   reference images: compare the two side by side, name the 3 biggest gaps, fix the worst, view again. Also judge
   it against the craft checklist like a picky builder: one clear silhouette? height hierarchy? a base? a curve or angle? bands and one accent stripe? lit?
   rooftop detail? Then look INSIDE with view(angle=cut, cut_y=<floor y + 3>): a cutaway from above that hides
   every ghost block higher than cut_y, to check rooms, machines and aisles. Fix and view again. 2-4 rounds.
6. For feedback ("taller", "less purple", "move the door"), change only what was asked, with mode=merge or a
   redraw of that one ghost. Update the plan when rooms move or change.
7. Use mod_guide for questions about a mod block or machine (what it is, rules, sizes). Use web_search for
   building ideas or anything not in the pack's guides.
8. End each turn with a short summary for the player: what you built or changed, ghost ids, and 1-2 ideas for
   what to do next. No long essays.

## Style rules (short version; knowledge(craft) and knowledge(principles) have the full lists)
- The bar is the player's mood board: designed silhouettes on a base, layered facades with bands, one accent
  colour, glow, rooftop clutter. "A few boxes joined by tubes" is a failed build.
- No flat walls: inset windows 1 deep, pillars and beams that stick out, trims of stairs/slabs/walls.
- Palette: 3-5 blocks per room, about 60% main, 30% secondary, 10% accent. Mix textures, not just colours.
- No plain boxes: shape the roof, add overhangs, vary heights, use odd widths so things have a centre.
- Interiors are for players: every building needs space to LIVE (beds, kitchen, storage), WORK (workshop,
  machine floor with clear aisles) and EXPAND (at least one empty expansion bay or floor). Use structure
  program=[...] for this; check with view(angle=cut) that every room is reachable from the entrance and core.
- Interiors: 4-6 blocks of headroom for normal rooms, more for halls; 3-wide walkways in big rooms.
- Light everything (no dark corners), hide light sources where you can.
- Floors get a border or pattern; big floors get inlays that lead to the main feature.
"""


# --------------------------------------------------------------------------------------------- mc-mcp

class Mcp:
    def __init__(self, url: str):
        self.url = url
        self.n = 0
        self.nogold = False  # hextech: swap gold/yellow blocks in every ghost_set for quartz/purple/cyan
        self.swapped = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "architect", "version": "1"}})

    def _rpc(self, method: str, params: dict) -> dict:
        self.n += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if os.environ.get("MCMCP_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["MCMCP_TOKEN"]
        req = urllib.request.Request(self.url, body, headers)
        with urllib.request.urlopen(req, timeout=600) as r:
            msg = json.loads(r.read())
        if "error" in msg:
            raise RuntimeError(msg["error"].get("message", str(msg["error"])))
        return msg["result"]

    def tools(self) -> list[dict]:
        return self._rpc("tools/list", {})["tools"]

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        if name == "ghost_set":  # v26: explicit fluid_pipe connection states (the default all-true state draws nothing)
            args, n = floaters.fix_pipes(args)
            if n:
                print(f"  [pipes] set explicit connections on {n} fluid_pipe entries in ghost_set {args.get('id')}", flush=True)
        if name == "ghost_set" and self.nogold:
            args, n = floaters.swap_gold(args)
            if n:
                self.swapped += n
                print(f"  [no-gold] swapped {n} gold/yellow entries in ghost_set {args.get('id')}", flush=True)
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return text, bool(res.get("isError"))

    def json(self, name: str, args: dict) -> dict:
        text, err = self.call(name, args)
        if err:
            raise RuntimeError(f"{name}: {text}")
        return json.loads(text)


# ----------------------------------------------------------------------------------------- mod guides

class Guides:
    """Searchable index of in-game guide pages from the pack's jars: AE2-style ae2guide pages (AE2, ExtendedAE,
    AdvancedAE, MEGA, ...) and Patchouli books (English)."""

    def __init__(self, mods: Path, cache: Path):
        self.pages: list[dict] = []
        if cache.exists() and mods.exists() and cache.stat().st_mtime > mods.stat().st_mtime:
            self.pages = json.loads(cache.read_text("utf-8"))
            return
        if not mods.exists():
            return
        for jar in sorted(mods.glob("*.jar")):
            try:
                with zipfile.ZipFile(jar) as z:
                    for n in z.namelist():
                        guide = "/ae2guide/" in n and n.endswith(".md") and not re.search(r"/_[a-z]{2}_[a-z]{2}/", n)
                        book = "/patchouli_books/" in n and "/en_us/entries/" in n and n.endswith(".json")
                        if not (guide or book):
                            continue
                        raw = z.read(n).decode("utf-8", "replace")
                        if book:
                            try:
                                d = json.loads(raw)
                                title = d.get("name", n)
                                text = "\n".join(p.get("text", "") for p in d.get("pages", []) if isinstance(p, dict))
                            except ValueError:
                                continue
                        else:
                            m = re.search(r"^\s*title:\s*(.+)$", raw, re.M)
                            title = m.group(1).strip() if m else n.rsplit("/", 1)[-1]
                            text = raw
                        self.pages.append({"mod": n.split("/")[1], "jar": jar.name, "path": n,
                                           "title": title, "text": text[:20000]})
            except (zipfile.BadZipFile, OSError):
                continue
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(self.pages), "utf-8")

    def search(self, query: str, mod: str | None = None, n: int = 3) -> list[dict]:
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 1]
        scored = []
        for p in self.pages:
            if mod and mod.lower() not in (p["mod"].lower(), p["jar"].lower()) and mod.lower() not in p["jar"].lower():
                continue
            title, text = p["title"].lower(), p["text"].lower()
            s = sum(title.count(t) * 8 + min(text.count(t), 20) for t in terms)
            if s:
                scored.append((s, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:n]]


# ------------------------------------------------------------------------------------------- the agent

LOCAL_TOOLS = [
    {"name": "plan", "description": "Read or replace the session's build plan (areas, rooms, themes, world origins, "
     "sizes, connections). action=get returns it; action=set stores `plan` (any JSON object) as the new plan.",
     "input_schema": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["get", "set"]},
         "plan": {"type": "object", "description": "full plan for action=set"}}, "required": ["action"]}},
    {"name": "knowledge", "description": "Design knowledge for this pack: principles (build techniques), themes "
     "(palettes and signature features), rooms (archetypes and sizes), multiblocks (showing off mod machines). "
     "topic=list shows what exists. item: one theme or room id (e.g. crafting_core) or one principles section "
     "letter/heading (e.g. D, palettes); without item, themes and rooms return just their ids.",
     "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}, "item": {"type": "string"}},
                      "required": ["topic"]}},
    {"name": "multiblock", "description": "Build a working mod multiblock as a ghost, valid by construction. kinds: "
     "controller_frame {size 2..7} (AE2 controller cube frame), controller_column {height 1..7}, quantum_computer "
     "{size 3..7, accelerator_share 0..1, entangler, multi_threader, storage} (AdvancedAE), assembler_matrix {sx,sy,sz "
     "3..7, speed<=5, pattern_share, faces glass|wall|window|checker} (ExtendedAE), trinity_core {matrix_faces} "
     "(matrix | controller cage around a 5^3 quantum computer | matrix, 21x7x7 along +x), crafting_cpu {family "
     "ae2|expandedae|megacells, sx,sy,sz 1..16, storage (a crafting storage id of that family), accelerators "
     "(list of co-processor ids, e.g. ExpandedAE exp_crafting_accelerator_16/_64/_256), accelerator_share, "
     "monitor}: use it for EVERY crafting CPU, never hand-place CPU blocks. origin = world position "
     "of the multiblock's min corner.",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": sorted(multiblocks.KINDS)},
         "ghost_id": {"type": "string"},
         "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3},
         "options": {"type": "object"}}, "required": ["kind", "ghost_id", "origin"]}},
    {"name": "campus", "description": "Build a walkable horizontal base, room per mod and wing per group. "
     "Default layouts: steampunk spine (gallery and glass dome), hextech radial (crown hub), gothic cloister "
     "(arcade ring round a garth), station_white linear (curved habitat ring + glass halls), solarpunk terraces "
     "(stepped tiers, retaining walls, stairs). Override with layout. Every wing joins the hub by a covered hall "
     "(pier + glass roof). Wings get varied roofs (gable, hip, barrel, sawtooth, planted garden...) and the tower a "
     "kit profile. Recessed glass bays with varied spacing, wing colours, "
     "large yards/gardens, and optional landmark tower with elevator. Returns for every ghost its world_min/world_max, floor_y, roof_deck_y and door_side, plus site_min/site_max: use them to attach extra details. "
     "Wing: {name, rooms:[kinds], size:s|m|l, floors:1|2, floor_h, upper:[kinds], roof:flat|mansard|dome|crown|gable|gable_steep|hip|hip_steep|spire|barrel|sawtooth|garden, roles:{material overrides}}. "
     "Rooms: mod_room:ae2|create|power|processing|magic|farming|mekanism|powah|bigreactors|industrialforegoing (or arbitrary theme; mekanism/powah/bigreactors/create/industrialforegoing are registered mods with real machines on every pad), expansion, storage, workshop, living, lab, hall. "
     "home=true adds a home wing. Personalise with attached details and multiblocks using returned world origins; keep aisles clear.",
     "input_schema": {"type": "object", "properties": {
         "layout": {"type": "string", "enum": ["spine", "radial", "cloister", "linear", "terraces"]},
         "area": {"type": "string"}, "kit": {"type": "string"},
         "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3,
                    "description": "world position of the site's min corner (platform bottom)"},
         "wings": {"type": "array", "items": {"type": "object"}},
         "home": {"type": "boolean"}, "landmark": {"type": "string", "enum": ["tower", "spire", "none"]},
         "roles": {"type": "object"}}, "required": ["area", "kit", "origin", "wings"]}},
    {"name": "shapes", "description": "Add generated shapes to a ghost (merged; mode=replace starts it fresh). "
     "Each part: {kind, at:[x,y,z] local to the ghost origin = the part's min corner and bottom, ...options}. "
     "Materials default to stone bricks / deepslate tiles; stairs and slabs are derived from `block` "
     "(stone_bricks -> stone_brick_stairs) unless you pass stair=; if ghost_set reports a bad derived id, retry "
     "with stair= set. Kinds:\n"
     "STYLED VOLUMES (use these for every exterior). They take kit= one of station_white | cyber_dark | ae_sky | "
     "hextech | steampunk | gothic | solarpunk | rust_industrial, and roles={wall:..., accent:...} to override one role:\n"
     "- structure {shape rect|octagon|round|ring|L, w, d (rect/octagon/L), r (round/ring), r_in, a0, a1 (ring "
     "sector in degrees, 0=east 90=south), c (octagon chamfer), cut_w, cut_d (L), floors=2, floor_h=4, kit, "
     "windows band|grid|slit|none, bay=4, accent_floor (index or null), glow_floors [..], plinth, ledges, pillars, "
     "parapet rail|wall|none, roof flat|mansard|dome|crown (default: mansard for hextech/gothic/steampunk, else flat), roof_details=3, antennas=1, interior_floors=true, "
     "open_ground (pilotis), seed}: a "
     "finished building: plinth, floor ledges, recessed windows with mullions, corner pillars, accent stripe, glow "
     "band, parapet with rail, rooftop vents and antennas, real floors inside. Height = 1 + floors*floor_h + roof. "
     "INSIDE: floor_hs=[7,5,5] sets each floor's height (machine floors 6-8, living 4-5); program=[...] fits "
     "out each floor, one entry per floor, a kind or a list of kinds split along the long axis: living (beds, "
     "kitchen run, dining table, storage), workshop (crafting/smelting stations, chests, work island), storage "
     "(barrel walls and shelf rows), machine_hall (3x3 machine pads, clear aisles, cable tray, floor glow), "
     "expansion (empty bay with a hazard border for future machines), lab (desks, bookshelves, brewing), hall "
     "(open showcase floor for a multiblock). A 3-wide spine stays clear on every floor; core=auto|stairs|elevator "
     "connects the floors; entrances=[s,n,e,w] cuts framed 3-wide doorways. Every building gets a program.\n"
     "- platform {shape round|rect|octagon, r or w,d, steps=2, rail, pattern grid|plain, kit}: the base/island "
     "the buildings stand on (top at local y=steps-1). Make it first, under everything.\n"
     "- bridge {length, along x|z, width=5, height=4, glass_roof, kit}: glass sky-bridge/corridor between volumes.\n"
     "- slope {w, run, rise, axis, kit}: framed sloped glass wall/roof (greenhouse, lab ramp).\n"
     "- spire {h, base=5, kit}: tapering landmark mast with glow ring and lit tip. Make the landmark at least "
     "1.5x the next tallest volume (h 25-40, base 7-9 for an 80-block base).\n"
     "ROOFS: vary them. flat for service wings, mansard for halls (hextech/gothic/steampunk), dome for the "
     "showcase rotunda, crown for the landmark tower. Keep wings to 1-2 floors; only the landmark is tall.\n"
     "CLASSIC PARTS:\n"
     "- round_tower {r 1..20, h, block, hollow=true, floor, floors_every, windows=4, window_every=5, window, "
     "crenel=true, crenel_block, corbel=true}: footprint 2r+1; corbel ring + merlons above h.\n"
     "- cone_roof {r (the tower's r), h (default 2.2x), block, overhang=1, tip=lightning_rod}: put at "
     "[tower_x-overhang, tower_top, tower_z-overhang]; with a corbelled tower use overhang=2.\n"
     "- gable_roof {w, d (wall footprint), axis x|z (ridge direction), block, stair, gable (end-wall fill), "
     "overhang=1, stepped=false (crow-stepped gables), ridge}: at = wall corner, y = wall top + 1.\n"
     "- pyramid_roof {w, d, block, stair, overhang=1, tip}: hip roof, same placement.\n"
     "- dome {r, block, hollow, tip}: half sphere, footprint 2r+1, at y = wall top.\n"
     "- battlements {w, d, block, corbel=false, every=2}: merlons on a wall top, at y = wall top + 1.\n"
     "- window_row {length, along x|z, outward north|south|east|west, count, spacing=3, w=1, h=2, glass, sill "
     "(stairs id), lintel (stairs id), frame}: cuts windows into an existing wall plane starting at `at`.\n"
     "- arch {w=3, h=4, along x|z, depth (wall thickness), block, stair, frame=true}: arched doorway carved "
     "through a wall; at = opening's bottom-left.\n"
     "- pillar_row {count, spacing, h, along, block, base, cap, size 1|2}.\n"
     "Returns each part's block count and world-local bounds.",
     "input_schema": {"type": "object", "properties": {
         "ghost_id": {"type": "string"},
         "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3,
                    "description": "only needed for a new ghost; existing ghosts keep theirs"},
         "mode": {"type": "string", "enum": ["merge", "replace"]},
         "parts": {"type": "array", "items": {"type": "object"}}}, "required": ["ghost_id", "parts"]}},
    {"name": "image_to_3d", "description": "Turn one image of a single object (statue, creature, ship, vehicle, "
     "tree, small building) into a voxel ghost: a 3D model is generated on rig's GPU from the picture, then "
     "voxelized and coloured with real blocks. Best for organic shapes boxes can't draw; for buildings, model "
     "them yourself with boxes and shapes. image: a file path, an URL, or 'ref' (the latest reference image in "
     "this session). size = longest side in blocks (48+ for creatures with thin legs). palette: default | cwt "
     "(concrete/terracotta/wool) | concrete | wool | terracotta | natural | stone | comma list of block ids. "
     "The model assumes the picture shows the object's front facing +z (south); fix with ghost_move rotate. "
     "First call after idle takes ~40 s (model load), then ~6 s. Returns block counts and a preview image.",
     "input_schema": {"type": "object", "properties": {
         "image": {"type": "string"}, "ghost_id": {"type": "string"},
         "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3},
         "size": {"type": "integer"}, "palette": {"type": "string"}, "hollow": {"type": "boolean"}},
         "required": ["image", "ghost_id", "origin"]}},
    {"name": "view", "description": "Look at ghosts and get a screenshot back. target: a ghost id, an area prefix "
     "ending in '/', or '*'. angle: iso (default, from the south-west above), iso_ne, front (from the south), back, "
     "side (from the east), top, inside (from the middle of the target at eye height), cut (cutaway from above "
     "with every ghost block higher than cut_y hidden, to inspect interiors). Moves the player in spectator mode.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string"},
         "angle": {"type": "string", "enum": ["iso", "iso_ne", "front", "back", "side", "top", "inside", "cut"]},
         "cut_y": {"type": "integer", "description": "angle=cut: world y of the cut (default target bottom + 4)"},
         "zoom": {"type": "number", "description": "1 = fit (default), <1 closer, >1 further"}},
         "required": ["target"]}},
    {"name": "style_refs", "description": "The player's mood board: reference screenshots of builds they like, "
     "with notes on what makes each work. kit: station_white | cyber_dark | ae_sky | hextech | steampunk | gothic | solarpunk "
     "| rust_industrial; returns up to `n` (default 2) images for that kit plus all notes. Look at them before "
     "planning an exterior and aim for that level of detail.",
     "input_schema": {"type": "object", "properties": {
         "kit": {"type": "string"}, "n": {"type": "integer"}}, "required": ["kit"]}},
    {"name": "blocks", "description": "Search the pack's ~32k survival-obtainable building blocks (chipped, rechiseled, "
     "chisel, xtonesreworked, luminax glow cubes, create, mcw roofs/windows/fences/furniture/lights, connectedglass, "
     "handcrafted, supplementaries, vanilla...) by shape, colour and price, and SEE their textures: returns a contact "
     "sheet image (index, id, cost) plus the list. Cost = raw material per block in cobble units (cobble 1, iron ingot "
     "3, gold 4, diamond 40); keep bulk blocks <= 3 and accents <= 6. shape: block | stairs | slab | wall | pillar | "
     "light | glass | window | roof | door | trapdoor | furniture | path | fence | pane | carpet. colour: hex or name "
     "(cream, gold, teal, navy, copper, brass, dark grey...). full=true for full cubes only. kw: words that must be in "
     "the id (e.g. 'brick', 'oak table', 'tile'). ns: limit to mods (e.g. 'chipped,rechiseled'). "
     "mod: a registered mod room theme (mekanism, powah, bigreactors, create, industrialforegoing): lists that mod's "
     "whitelisted machine/casing blocks with NO cost filter (they have no recipe cost). Active automatically for the "
     "mod rooms of your campus; everything else stays cheap survival blocks.",
     "input_schema": {"type": "object", "properties": {
         "shape": {"type": "string"}, "colour": {"type": "string"}, "max_cost": {"type": "number"},
         "kw": {"type": "string"}, "ns": {"type": "string"}, "full": {"type": "boolean"}, "mod": {"type": "string"},
         "n": {"type": "integer", "description": "default 24, max 40"}}}},
    {"name": "bill", "description": "Material bill of ghosts: total cost in cobble units, the most expensive blocks, "
     "and blocks with no survival recipe. target: ghost id, prefix ending in '/', or '*'. Run before export and swap "
     "any expensive bulk block for a cheap look-alike from blocks().",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "mod_guide", "description": "Search the pack's in-game guide pages (AE2 guide pages of AE2 and its "
     "addons, Patchouli books) for a block, machine or mechanic. Returns the best pages' text.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "mod": {"type": "string", "description": "optional mod id or jar name filter"}},
         "required": ["query"]}},
]


class Architect:
    def __init__(self, session: str):
        self.dir = HERE / "sessions" / session
        self.dir.mkdir(parents=True, exist_ok=True)
        self.msgs_file = self.dir / "messages.json"
        self.plan_file = self.dir / "plan.json"
        self.messages: list[dict] = json.loads(self.msgs_file.read_text("utf-8")) if self.msgs_file.exists() else []
        self.client = (anthropic.Anthropic(base_url=BASE_URL, api_key="local", timeout=900) if LOCAL
                       else anthropic.Anthropic())
        self.mcp = Mcp(MCP_URL)
        mcp_tools = {t["name"]: t for t in self.mcp.tools()}
        missing = [n for n in FORWARD if n not in mcp_tools]
        if missing:
            sys.exit(f"mc-mcp is missing tools {missing}: is this the mc-mcp build with ghosts?")
        # Fixed order keeps the tool list byte-identical between calls, so the prompt cache hits.
        self.tools = [{"name": n, "description": mcp_tools[n]["description"], "input_schema": mcp_tools[n]["inputSchema"]}
                      for n in FORWARD] + LOCAL_TOOLS
        if not LOCAL:
            self.tools.append({"type": "web_search_20250305", "name": "web_search", "max_uses": 5})
        self._guides: Guides | None = None
        self.guard = floaters.Guard()
        self.spectator = False
        self.cost = 0.0
        self.active_mods: list[str] = list(FEATURE_MODS)  # registered mod room themes whose whitelist the blocks tool adds

    # ---- local tools

    def guides(self) -> Guides:
        if self._guides is None:
            print("  (indexing guide pages in the pack's jars, once)", flush=True)
            self._guides = Guides(MODS_DIR, HERE / "sessions" / "_guide_index.json")
        return self._guides

    def ghost_set_guarded(self, a: dict):
        """ghost_set without parts floating in the air: those are dropped and reported back."""
        args, floating = self.guard.check(a["id"], a)
        snapped = [p for p in floating if "snapped_down" in p]
        rej = [p for p in floating if "rejected" in p]
        if rej:
            return json.dumps({"error": "nothing placed: " + rej[0]["rejected"]}), True
        floating = [p for p in floating if "snapped_down" not in p]
        if floating and not args.get("boxes") and not args.get("blocks"):
            return json.dumps({"error": "nothing placed: every part floats (touches no building block and is above "
                                        "the ground). Attach it to a wall or roof, or stand it on the ground.",
                               "floating": floating}), True
        out, is_err = self.mcp.call("ghost_set", args)
        if not is_err:
            self.guard.record(a["id"], args, args.get("mode", "replace") == "replace")
        if floating:
            out = (out if isinstance(out, str) else json.dumps(out)) + "\nDROPPED floating parts (touch nothing): " + \
                json.dumps(floating) + " -- attach them to a building or remove them."
        return out, is_err

    def run_local(self, name: str, a: dict):
        if name == "plan":
            if a.get("action") == "set":
                # Top-level keys merge into the saved plan, so a reference brief doesn't wipe the area list.
                old = json.loads(self.plan_file.read_text("utf-8")) if self.plan_file.exists() else {}
                new = a.get("plan", {})
                merged = {**old, **new} if isinstance(old, dict) and isinstance(new, dict) else new
                self.plan_file.write_text(json.dumps(merged, indent=1), "utf-8")
                return "plan saved (top-level keys merged)"
            return self.plan_file.read_text("utf-8") if self.plan_file.exists() else "no plan yet"
        if name == "knowledge":
            files = sorted(p for p in KNOWLEDGE.glob("*") if p.suffix in (".md", ".json")) if KNOWLEDGE.exists() else []
            topic = a.get("topic", "list").lower()
            if topic == "list":
                return "topics: " + ", ".join(p.stem for p in files) if files else "no knowledge files yet"
            item = (a.get("item") or "").strip().lower()
            for p in files:
                if p.stem.lower() == topic or topic in p.stem.lower():
                    text = p.read_text("utf-8")
                    if p.suffix == ".json":
                        data = json.loads(text)
                        lst = next((v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
                        if lst is not None:
                            if not item:
                                return (f"{p.stem}: " + ", ".join(e.get("id", "?") for e in lst)
                                        + "\n(call again with item=<id> for one entry)")
                            hit = [e for e in lst if item in (e.get("id", "").lower(), e.get("name", "").lower())]
                            hit = hit or [e for e in lst if item in json.dumps(e).lower()][:2]
                            return json.dumps(hit, indent=1) if hit else f"no {item} in {p.stem}"
                    elif item:
                        parts = re.split(r"(?m)^(?=## )", text)
                        hit = [s for s in parts if s.startswith("## ") and (s[3:].lower().startswith(item + ".")
                                                                           or item in s.splitlines()[0].lower())]
                        if hit:
                            return "\n".join(hit)
                    return text if len(text) < 40000 else text[:40000] + "\n...(truncated)"
            return f"no topic {topic}; topics: " + ", ".join(p.stem for p in files)
        if name == "multiblock":
            spec = multiblocks.build(a["kind"], **(a.get("options") or {}))
            info = spec.pop("info", None)
            res = self.mcp.json("ghost_set", {"id": a["ghost_id"], "origin": a["origin"], "mode": "replace",
                                              "tags": {"multiblock": a["kind"]}, **spec})
            self.guard.record(a["ghost_id"], {"origin": a["origin"], **spec}, True)
            if info:
                res["info"] = info
            return json.dumps(res)
        if name == "campus":
            if str(a["kit"]).lower() == "hextech":
                self.mcp.nogold = True
            ghosts = campus.build(a["kit"], a.get("wings") or [], bool(a.get("home", True)),
                                  a.get("landmark") or "tower", a.get("roles"), layout=a.get("layout"))
            site_rep = None
            if SITE:  # surveyed terrain: re-place the campus, add foundations, report fill/cut/trees
                ghosts, site_rep = site.apply(ghosts, SITE["survey"], near=SITE.get("near"), force=SITE.get("force"))
                a = dict(a, origin=site_rep["origin"])
            ox, oy, oz = a["origin"]
            rep = []
            for g in ghosts:
                o = [ox + g["origin"][0], oy + g["origin"][1], oz + g["origin"][2]]
                res = self.mcp.json("ghost_set", {"id": f"{a['area']}/{g['id']}", "origin": o, "mode": "replace",
                                                  "blocks": g["blocks"]})
                self.guard.record(f"{a['area']}/{g['id']}", {"origin": o, "blocks": g["blocks"]}, True)
                self.guard.campus_ids.add(f"{a['area']}/{g['id']}")
                xs = [b[0] for b in g["blocks"]]; ys = [b[1] for b in g["blocks"]]; zs = [b[2] for b in g["blocks"]]
                item = {"id": f"{a['area']}/{g['id']}", "origin": o,
                        "size": [max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1],
                        "world_min": [o[0] + min(xs), o[1] + min(ys), o[2] + min(zs)],
                        "world_max": [o[0] + max(xs), o[1] + max(ys), o[2] + max(zs)]}
                m = g.get("meta") or {}
                if not m and (g["id"].startswith("wing_") or g["id"] == "hub"):  # legacy (steam) path: no meta
                    wn = g["id"][5:]
                    wr = next((w.get("rooms") for w in (a.get("wings") or []) if str(w.get("name")) == wn), None)
                    m = {"kind": "hub" if g["id"] == "hub" else "wing", "floor_y": campus.STEPS + 1, "rooms": wr}
                if m.get("kind") in ("wing", "hub") and "floor_y" in m:
                    self.guard.add_wing(item["id"], item["world_min"], item["world_max"], oy + m["floor_y"],
                                        m.get("rooms") if m.get("kind") == "wing" else None, m["kind"])
                    if m.get("kind") == "wing":
                        item["room_origins"] = [{k: v for k, v in sl.items() if k != "wing"}
                                                for sl in self.guard.room_slots(self.guard.wings[item["id"]])]
                if m.get("kind") in ("wing", "hub", "tower"):  # world y of the floor and of the roof deck
                    item["floor_y"] = oy + m["floor_y"] if "floor_y" in m else None
                    if "deck_y" in m:
                        item["roof_deck_y"] = oy + m["deck_y"]
                    if m.get("door"):
                        item["door_side"] = m["door"]
                    if m.get("roof"):
                        item["roof"] = m["roof"]
                bad = res.get("bad_palette") or res.get("unknown_keys")
                if bad:
                    item["bad"] = bad
                rep.append(item)
            themes = mods.themes_in(a.get("wings"))
            for t in themes:
                if t not in self.active_mods:
                    self.active_mods.append(t)
            allmin = [min(r["world_min"][i] for r in rep) for i in range(3)]
            allmax = [max(r["world_max"][i] for r in rep) for i in range(3)]
            return json.dumps({"ghosts": rep, "floor_y": oy + campus.STEPS + 1, "site_min": allmin, "site_max": allmax,
                               **({"site": {k: v for k, v in site_rep.items() if k != "origin"},
                                   "site_note": "Placed on surveyed terrain at origin " + str(site_rep["origin"]) + ". " + site_rep["summary"]
                                                + ". Mention the foundations (fill/cut) and the trees to clear in your summary; ghosts never remove blocks."}
                                  if site_rep else {}),
                               **({"mod_rooms": [mods.prompt_note(t) for t in themes]} if themes else {}),
                               "note": "All coordinates are WORLD coordinates. world_min/world_max = each ghost's bounding "
                                       "box; roof_deck_y = y of a wing's flat deck (a part at that y+1 sits on it); wall "
                                       "planes are the box faces (a part touching x=world_min.x-1 or world_max.x+1 or the "
                                       "z faces touches the wall). Ground = site_min.y+1. Covered halls ('halls'), tiers and "
                                       "stairs are ghosts too. ROOM GHOSTS (ae2_storage, ae2_autocraft, ...): use each wing's room_origins[].origin as the ghost origin with LOCAL coords from 0,0,0 inside max_size; never write world coords with a non-zero origin. Attach extra details to these faces on the FIRST try: any part "
                                       "that touches no ghost block and is above ground is dropped."})
        if name == "shapes":
            blocks, summary = shapes.build(a.get("parts") or [])
            args = {"id": a["ghost_id"], "mode": a.get("mode", "merge"), "blocks": blocks}
            if a.get("origin"):
                args["origin"] = a["origin"]
            args, floating = self.guard.check(args["id"], args)
            floating = [p for p in floating if "snapped_down" not in p]
            if floating and not args.get("blocks"):
                return json.dumps({"error": "every part floats: nothing touches a building or the ground",
                                   "floating": floating})
            blocks = args["blocks"]
            res = self.mcp.json("ghost_set", args)
            self.guard.record(args["id"], args, args["mode"] == "replace")
            if floating:
                res["dropped_floating"] = floating
            bad = list((res.get("bad_palette") or {}).keys())
            if bad:  # a derived stairs/slab id that doesn't exist: swap in a stone-brick one and redo the call
                swap = {}
                for k in bad:
                    base = k.split("[")[0]
                    for kind in ("stairs", "slab"):
                        if base.endswith("_" + kind):
                            swap[base] = shapes.FALLBACK[kind]
                if swap:
                    args["blocks"] = [[x, y, z, swap.get(s.split("[")[0], s.split("[")[0]) +
                                       (s[s.index("["):] if "[" in s else "")] for (x, y, z, s) in blocks]
                    res = self.mcp.json("ghost_set", args)
                    res["substituted"] = swap
            res["parts"] = summary
            return json.dumps(res)
        if name == "image_to_3d":
            return self.image_to_3d(a)
        if name == "view":
            return self.view(a.get("target", "*"), a.get("angle", "iso"), float(a.get("zoom", 1) or 1),
                             a.get("cut_y"))
        if name == "style_refs":
            return self.style_refs(a.get("kit", ""), int(a.get("n") or 2))
        if name == "blocks":
            n = max(1, min(40, int(a.get("n") or 24)))
            ns_l = [x.strip() for x in a["ns"].split(",")] if a.get("ns") else None
            want_mods = [m for m in re.split(r"[ ,]+", a.get("mod") or "") if m in mods.REGISTRY]
            want_mods += [t for t in self.active_mods if t not in want_mods and ns_l and
                          set(ns_l) & set(mods.REGISTRY[t].namespaces)]
            hits = []
            if want_mods:  # registered mod room: its whitelist, no cost filter
                hits = blocklib.find_listed(mods.whitelist(want_mods), a.get("shape"), a.get("colour"), a.get("kw"), n,
                                            full=bool(a.get("full")))
            if not a.get("mod") or not hits:
                rest = blocklib.find(a.get("shape"), a.get("colour"), float(a.get("max_cost") or 3), ns_l,
                                     a.get("kw"), n, full=bool(a.get("full")))
                if want_mods:
                    rest = [h for h in rest if h["id"] not in {x["id"] for x in hits}]
                hits = (hits + rest)[:n]
            if not hits:
                return "no blocks match; loosen shape/colour/kw or raise max_cost"
            path = blocklib.sheet([h["id"] for h in hits], str(self.dir / "blocks_sheet.jpg"), cols=6, px=48)
            text = "\n".join(f"{i} {h['id']} cost {h['cost']} {h['colour'] or ''}" for i, h in enumerate(hits))
            return [{"type": "text", "text": text},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.standard_b64encode(Path(path).read_bytes()).decode()}}]
        if name == "bill":
            t = a.get("target", "*")
            ghosts = self.mcp.json("ghost_list", {}).get("ghosts", [])
            ids = [g["id"] for g in ghosts if t == "*" or g["id"] == t or (t.endswith("/") and g["id"].startswith(t))]
            counts: dict[str, int] = {}
            for gid in ids:
                for st, c in (self.mcp.json("ghost_info", {"id": gid}).get("palette") or {}).items():
                    counts[st] = counts.get(st, 0) + c
            res = blocklib.bill(counts)
            res["ghosts"] = len(ids)
            res["blocks"] = sum(counts.values())
            return json.dumps(res)
        if name == "mod_guide":
            pages = self.guides().search(a["query"], a.get("mod"))
            if not pages:
                return "nothing found in the pack's guides; try other words or web_search"
            return "\n\n".join(f"# {p['title']} ({p['jar']}: {p['path']})\n{p['text'][:3000]}" for p in pages)
        raise ValueError(f"unknown tool {name}")

    def image_to_3d(self, a: dict):
        """Runs img3d (its own venv: trimesh etc.) as a subprocess, then sends the spec inline: the game on rig
        can't read FOX paths."""
        src = a["image"]
        work = self.dir / "img3d"
        work.mkdir(parents=True, exist_ok=True)
        if src == "ref":
            refs_dir = self.dir / "refs"
            imgs = sorted(refs_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime) if refs_dir.exists() else []
            if not imgs:
                raise ValueError("no reference image in this session yet")
            path = imgs[-1]
        else:
            got = refs_mod.fetch(src, self.dir / "refs")
            path = got[0]
        size = int(a.get("size") or 32)
        out = work / f"{path.stem}_{size}.json"
        cmd = [str(IMG3D_PY), str(HERE / "img3d" / "img3d.py"), "build", str(path), "--size", str(size),
               "--palette", a.get("palette") or "default", "-o", str(out), "--workdir", str(work)]
        if a.get("hollow"):
            cmd.append("--hollow")
        print(f"  (img3d: generating on rig, {path.name}, size {size})", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError("img3d failed: " + (r.stderr or r.stdout)[-1500:])
        spec = json.loads(out.read_text("utf-8"))
        res = self.mcp.json("ghost_set", {"id": a["ghost_id"], "origin": a["origin"], "mode": "replace",
                                          "palette": spec["palette"], "boxes": spec.get("boxes", []),
                                          "blocks": spec["blocks"],
                                          "tags": {"source": "img3d", "image": path.name}})
        meta = spec.get("meta", {})
        res["img3d"] = {k: meta[k] for k in ("dims", "counts", "silhouette_iou", "mesh") if k in meta}
        if isinstance(res["img3d"].get("counts"), dict):  # keep the reply short: top 12 blocks
            res["img3d"]["counts"] = dict(sorted(res["img3d"]["counts"].items(), key=lambda kv: -kv[1])[:12])
        content = [{"type": "text", "text": json.dumps(res)}]
        prev = work / f"{out.stem}_preview.png"
        if prev.exists():
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                        "data": base64.standard_b64encode(prev.read_bytes()).decode()}})
        return content

    def style_refs(self, kit: str, n: int):
        d = KNOWLEDGE / "style_refs"
        refs = json.loads((d / "index.json").read_text("utf-8"))
        kit = kit.lower().strip()
        mine = [r for r in refs if r["kit"] == kit] or refs
        shown = self.__dict__.setdefault("_refs_shown", set())
        pick = ([r for r in mine if r["file"] not in shown] or mine)[:max(1, min(n, 3))]
        shown.update(r["file"] for r in pick)
        self.kit = kit if any(r["kit"] == kit for r in refs) else getattr(self, "kit", None)
        self.mcp.nogold = self.mcp.nogold or self.kit == "hextech"
        notes = "\n".join(f"- {r['file']} ({r['kit']}): {r['notes']}" for r in mine)
        content = [{"type": "text", "text": f"mood board for {kit} (showing {[r['file'] for r in pick]}):\n{notes}"}]
        for r in pick:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": base64.standard_b64encode((d / r["file"]).read_bytes()).decode()}})
        return content

    def view(self, target: str, angle: str, zoom: float, cut_y=None):
        ghosts = self.mcp.json("ghost_list", {})["ghosts"]
        sel = [g for g in ghosts if "world_min" in g and (target == "*" or g["id"] == target
                                                         or (target.endswith("/") and g["id"].startswith(target)))]
        if not sel:
            raise ValueError(f"no ghost matches {target}")
        lo = [min(g["world_min"][i] for g in sel) for i in range(3)]
        hi = [max(g["world_max"][i] for g in sel) + 1 for i in range(3)]
        if cut_y is not None and int(cut_y) < lo[1]:  # a local height (e.g. 4) instead of a world y
            cut_y = lo[1] + int(cut_y)
        c = [(lo[i] + hi[i]) / 2 for i in range(3)]
        size = max(hi[i] - lo[i] for i in range(3))
        d = (size * 0.95 + 6) * zoom
        offsets = {"iso": (-0.7, 0.55, 0.7), "iso_ne": (0.7, 0.55, -0.7), "front": (0, 0.25, 1), "back": (0, 0.25, -1),
                   "side": (1, 0.25, 0), "top": (0.01, 1, 0.01), "inside": (0, 0, 0), "cut": (-0.35, 1, 0.45)}
        ox, oy, oz = offsets.get(angle, offsets["iso"])
        if angle == "inside":
            eye = (c[0], lo[1] + 1.6, c[2])
            look = (c[0], lo[1] + 1.6, lo[2] - 100)
        else:
            norm = math.sqrt(ox * ox + oy * oy + oz * oz)
            if angle == "cut":
                c[1] = int(cut_y) if cut_y is not None else lo[1] + 4
            eye = (c[0] + ox / norm * d, c[1] + oy / norm * d, c[2] + oz / norm * d)
            look = tuple(c)
        if not self.spectator:
            # Daylight, no HUD, ghosts drawn over terrain and opaque: the screenshot shows the design, not the woods.
            for cmd in ("gamemode spectator", "time set noon", "gamerule doDaylightCycle false",
                        "weather clear"):
                self.mcp.call("run_command", {"command": cmd})
            self.spectator = True
        # Every view: terrain can't hide the ghosts, they draw opaque, no HUD.
        show = {"id": "*", "xray": True, "solid": True, "hud": False}
        if angle == "cut":
            show["clip_y"] = int(cut_y) if cut_y is not None else lo[1] + 4
        else:
            show["clip_off"] = True
        self.mcp.call("ghost_show", show)
        self.mcp.call("run_command", {"command": f"tp @s {eye[0]:.1f} {eye[1]:.1f} {eye[2]:.1f}"})
        self.mcp.call("look_at", {"x": look[0], "y": look[1], "z": look[2]})
        time.sleep(1.5)  # let chunks and the ghost mesh draw
        shot = self.mcp.json("screenshot", {})
        path = shot["path"].replace("\\.\\", "\\")
        if PATH_MAP:
            src, dst = PATH_MAP.split("=", 1)
            if path.upper().startswith(src.upper()):
                path = dst + path[len(src):]
        data = base64.standard_b64encode(Path(path).read_bytes()).decode()
        out = [{"type": "text", "text": f"view {angle} of {target}: bounds {lo}..{hi}, camera at "
                                        f"{[round(v) for v in eye]}"},
               {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}]
        ref = self.ref_thumb() if angle != "cut" else None
        if ref:
            name, b64 = ref
            out += [{"type": "text", "text": f"REFERENCE ({name}, the player's mood board). Before your next build "
                     "step, compare the view above with this reference and write the 3 biggest gaps (silhouette, "
                     "roofline, facade depth, palette, detail, light), then fix the worst one."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}]
        return out

    def ref_thumb(self):
        """One small reference image of the session's kit, a different one each view (round robin)."""
        kit = getattr(self, "kit", None)
        if not kit:
            return None
        d = KNOWLEDGE / "style_refs"
        refs = [r for r in json.loads((d / "index.json").read_text("utf-8")) if r["kit"] == kit]
        if not refs:
            return None
        self.ref_i = getattr(self, "ref_i", -1) + 1
        r = refs[self.ref_i % len(refs)]
        from PIL import Image
        import io
        im = Image.open(d / r["file"]).convert("RGB")
        im.thumbnail((640, 640))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        return r["file"], base64.standard_b64encode(buf.getvalue()).decode()

    # ---- loop

    def save(self):
        self.msgs_file.write_text(json.dumps(self.messages), "utf-8")

    def repair(self):
        """Give every tool_use a tool_result in the next user message (older sessions could miss them), and merge
        back-to-back user messages so the history is valid again."""
        fixed: list[dict] = []
        for i, m in enumerate(self.messages):
            if fixed and fixed[-1]["role"] == m["role"] == "user":
                a = fixed[-1]["content"]; b = m["content"]
                a = a if isinstance(a, list) else [{"type": "text", "text": a}]
                b = b if isinstance(b, list) else [{"type": "text", "text": b}]
                fixed[-1] = {"role": "user", "content": a + b}
                continue
            fixed.append(m)
        msgs, self.messages = fixed, []
        for i, m in enumerate(msgs):
            self.messages.append(m)
            if m["role"] != "assistant" or not isinstance(m["content"], list):
                continue
            ids = [b["id"] for b in m["content"] if b.get("type") == "tool_use"]
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            have = {b.get("tool_use_id") for b in (nxt["content"] if nxt and isinstance(nxt["content"], list) else [])
                    if isinstance(b, dict)}
            miss = [{"type": "tool_result", "tool_use_id": t, "is_error": True, "content": "not run"}
                    for t in ids if t not in have]
            if not miss:
                continue
            if nxt is None or nxt["role"] != "user":
                self.messages.append({"role": "user", "content": miss})
            else:
                c = nxt["content"] if isinstance(nxt["content"], list) else [{"type": "text", "text": nxt["content"]}]
                nxt["content"] = miss + c
        # merge again: a patched result message may now sit right before the next user message
        out: list[dict] = []
        for m in self.messages:
            if out and out[-1]["role"] == m["role"] == "user":
                a = out[-1]["content"]; b = m["content"]
                a = a if isinstance(a, list) else [{"type": "text", "text": a}]
                b = b if isinstance(b, list) else [{"type": "text", "text": b}]
                out[-1] = {"role": "user", "content": a + b}
            else:
                out.append(m)
        self.messages = out

    def turn(self, user_text: str, refs: list[str] | None = None) -> str:
        text, found = refs_mod.find(user_text)
        refs = list(refs or []) + found
        if refs:
            frames, from_video = [], False
            for r in refs:
                got = refs_mod.fetch(r, self.dir / "refs")
                from_video |= len(got) > 1
                frames += got
                print(f"  (reference {r}: {len(got)} image(s))", flush=True)
            frames = frames[:12]
            content = [{"type": "text", "text": refs_mod.instructions(len(frames), from_video)}]
            content += refs_mod.blocks(frames)
            content.append({"type": "text", "text": "Request: " + (text or "Build what the reference shows.")})
            self.messages.append({"role": "user", "content": content})
        else:
            self.messages.append({"role": "user", "content": user_text})
        self.repair()
        local = {t["name"] for t in LOCAL_TOOLS}
        final = ""
        for step in range(MAX_STEPS):
            t0 = time.time()
            if LOCAL:
                resp = self.client.messages.create(model=MODEL, max_tokens=8000, system=SYSTEM,
                                                   tools=self.tools, messages=self.messages)
            else:
                resp = self.client.messages.create(
                    model=MODEL, max_tokens=16000,
                    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    tools=self.tools, messages=self.messages,
                    output_config={"effort": EFFORT},
                    cache_control={"type": "ephemeral"},
                )
            u = resp.usage
            self.tokens_in = getattr(self, "tokens_in", 0) + u.input_tokens
            self.tokens_out = getattr(self, "tokens_out", 0) + u.output_tokens
            self.secs = getattr(self, "secs", 0.0) + time.time() - t0
            if not LOCAL:
                self.cost += usage_cost(u)
            self.messages.append({"role": "assistant",
                                  "content": [b.model_dump(mode="json", exclude_none=True) for b in resp.content]})
            self.save()
            if MAX_COST and self.cost >= MAX_COST:
                return final + f"\n(stopped: cost cap ${MAX_COST:.2f} reached)"
            for b in resp.content:
                if b.type == "text" and b.text.strip():
                    final = b.text
            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason == "refusal":
                return final or "(the model declined this request)"
            if resp.stop_reason == "max_tokens":
                # A cut-off reply can end in a half-written tool call; every tool_use needs a tool_result.
                cut = [{"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                        "content": "not run: your reply was cut off at max_tokens"}
                       for b in resp.content if b.type == "tool_use"]
                self.messages.append({"role": "user", "content": cut + [{"type": "text", "text":
                                      "Your last reply was cut off at max_tokens. Continue with smaller steps "
                                      "(fewer blocks per ghost_set, one shapes part per call)."}]})
                continue
            calls = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not calls:
                return final
            results = []
            for c in calls:
                print(f"  -> {c.name} {json.dumps(c.input)[:140]}", flush=True)
                try:
                    if c.name in local:
                        out = self.run_local(c.name, c.input)
                        is_err = False
                    elif c.name == "ghost_set" and c.input.get("id"):
                        out, is_err = self.ghost_set_guarded(c.input)
                    else:
                        out, is_err = self.mcp.call(c.name, c.input)
                        if c.name == "ghost_clear" and not is_err:
                            gid = str(c.input.get("id", ""))
                            for k in [k for k in self.guard.cells if k == gid or (gid.endswith("/") and k.startswith(gid))]:
                                del self.guard.cells[k]
                except Exception as e:  # tool failures go back to the model, not up the stack
                    out, is_err = f"error: {e}", True
                if isinstance(out, str) and len(out) > 30000:
                    out = out[:30000] + "\n...(truncated)"
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": is_err})
            self.messages.append({"role": "user", "content": results})
            self.save()
        return final + f"\n(stopped after {MAX_STEPS} steps; say 'continue' to go on)"


PAUSE_MARK = HERE / "sessions" / ".pause_on_lost_focus"


def hold_focus(mcp) -> str | None:
    """While a turn runs, the game must not open the pause menu when its window is in the background (it would cover
    every view). Turns pauseOnLostFocus off without saving options.txt and returns the value to restore. The original
    value is also kept in a marker file, so a killed run is repaired by the next one."""
    try:
        old = mcp.json("video_get", {"filter": "pauseOnLostFocus"}).get("pauseOnLostFocus")
        if old is None:  # mc-mcp older than 0.2.1: no plain-field options
            return None
        if PAUSE_MARK.exists():
            old = PAUSE_MARK.read_text().strip() or old
        PAUSE_MARK.parent.mkdir(parents=True, exist_ok=True)
        PAUSE_MARK.write_text(old)
        mcp.json("video_set", {"option": "pauseOnLostFocus", "value": "false", "save": False})
        scr = mcp.json("screen", {})
        if scr.get("open") and scr.get("class", "").endswith("PauseScreen"):
            mcp.call("close_screen", {})
        return old
    except Exception:
        return None


def release_focus(mcp, old: str | None):
    if old is None:
        return
    try:
        mcp.json("video_set", {"option": "pauseOnLostFocus", "value": old, "save": False})
        PAUSE_MARK.unlink(missing_ok=True)
    except Exception:
        pass


GEN_BRIEF = """Build my main base as ONE big, spread-out, walkable complex, site min corner at {x} {y} {z} (about 150-180 x 110-130 blocks). Ghost ids under "{id}/". I like lots of horizontal usable floor, big spaced-out machine areas, a room per mod and wings grouping similar mods; only the landmark should be tall, no stacks of empty floors.
Start with ONE campus call (kit {kit}, home=true, landmark=tower{layout}) with wings built from the mods installed (registry_blocks namespaces): a storage/AE2 wing, a tech wing, a processing wing, a magic wing, a farming wing.
Make it look like the {style} style refs (call style_refs({kit})): extra signature details, rooftop clutter. EVERY detail must overlap or touch the building (on wall faces, on the roof deck, trees on the ground only). Everything cheap in survival. No gold or yellow emblems on facades.
Check with view (iso, front, top) and fix the worst gaps. Summarise what you built."""


def generate_request(style: str, x: int, y: int, z: int, kit: str, layout: str, ident: str) -> str:
    brief = GEN_BRIEF.format(style=style, x=x, y=y, z=z, kit=kit or style,
                             layout=f", layout={layout}" if layout else "", id=ident)
    for t in FEATURE_MODS:
        r = mods.get(t)
        brief += (f"\nFEATURE WING: the {r.name} mod. Give it its OWN large wing (size l, floors 1, floor_h 9, name \"{t}\", "
                  f"rooms [\"mod_room:{t}\", \"mod_room:{t}\", \"expansion\"]) and make it the showpiece of the campus: the "
                  f"room fit-out already puts real {r.name} machines on every pad; add more of them with ghost_set using "
                  f"the whitelist, and look inside with view(angle=cut). Kit {r.style} fits it best. Keep the other wings few and plain: at most an AE2 wing and one more, size s or m, no extra mod rooms, so the budget goes into the {r.name} wing: its facade, its interior and the mod blocks you add with ghost_set (use the whitelist ids, place them as visible set pieces with aisles clear).\n" + mods.prompt_note(t))
    if SITE:  # survey summary only (never the raw grid): keeps the prompt cheap
        p = SITE["plan"]
        brief = brief.replace("(about 150-180 x 110-130 blocks)", f"(about {p['w']} x {p['d']} blocks, hard limit)")
        brief += "\n" + site.prompt_note(p)
    return brief


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--session", default="default")
    ap.add_argument("--chat", action="store_true", help="take requests from in-game chat (@claude ...)")
    ap.add_argument("--ref", action="append", default=[],
                    help="reference image/video: file, URL, YouTube link, or 'clipboard:' (repeatable). "
                         "Paths, URLs and /paste inside a request work too.")
    ap.add_argument("--max-cost", type=float, default=None, help="stop the run once the API cost reaches this many USD")
    ap.add_argument("--generate", metavar="STYLE", help="build a base in this style (steampunk, hextech, gothic, "
                                                         "station_white, solarpunk) at --x --y --z; ghosts go under <session>/")
    ap.add_argument("--x", type=int, default=0)
    ap.add_argument("--y", type=int, default=66)
    ap.add_argument("--z", type=int, default=0)
    ap.add_argument("--kit")
    ap.add_argument("--layout")
    ap.add_argument("--feature-mod", action="append", default=[], choices=sorted(mods.REGISTRY),
                    help="registered mod room to feature as the showpiece wing of --generate (repeatable)")
    ap.add_argument("--survey", help="world_survey JSON (written by the mod): fit the campus to the terrain")
    ap.add_argument("--near", help="x,z the player aimed at (site picker prefers spots close to it)")
    ap.add_argument("--site-rect", help="x,z,w,d,rot of a previewed /ghost area: build exactly there")
    ap.add_argument("request", nargs="*")
    args = ap.parse_args()
    global MAX_COST, SITE
    FEATURE_MODS[:] = args.feature_mod
    if args.max_cost is not None:
        MAX_COST = args.max_cost
    if args.survey:
        sv = site.Survey.from_file(args.survey)
        near = tuple(int(v) for v in args.near.split(",")) if args.near else None
        style = args.generate or args.kit or "hextech"
        if args.site_rect:
            fx, fz, fw, fd, frot = (int(v) for v in args.site_rect.split(","))
            lay = args.layout or site.DEFAULT_LAYOUT.get(style, "spine")
            plan = site.evaluate(sv, fx, fz, fw, fd, frot, near)
            plan.update(layout=lay, wings=site.wings_for(lay, fw, fd), style=style)
            plan["size"] = "m" if plan["wings"] >= 4 else "s"
            force = {"x": fx, "z": fz, "w": fw, "d": fd, "rot": frot}
        else:
            plan = site.plan(sv, style, near, args.layout)
            force = None
        SITE = {"survey": sv, "plan": plan, "near": near, "force": force}
        args.x, args.z, args.y = plan["x"], plan["z"], plan["ref"] - 1
        args.layout = args.layout or plan["layout"]
        print("SITE " + site.describe(plan), flush=True)
    if args.generate:
        args.request = [generate_request(args.generate, args.x, args.y, args.z, args.kit, args.layout, args.session)]
    arch = Architect(args.session)
    first_refs = list(args.ref)

    def run(text: str) -> str:
        nonlocal first_refs
        held = hold_focus(arch.mcp)
        try:
            out = arch.turn(text, first_refs)
        except Exception as e:  # a bad reference shouldn't kill the REPL or chat loop
            out = f"error: {e}"
        finally:
            release_focus(arch.mcp, held)
        first_refs = []
        print(f"\n{out}\n  [{MODEL}, cost ~${arch.cost:.4f}, {getattr(arch, 'tokens_in', 0)} in / "
              f"{getattr(arch, 'tokens_out', 0)} out tokens, {getattr(arch, 'secs', 0):.0f}s model time]\n", flush=True)
        return out

    if args.request or first_refs:
        run(" ".join(args.request))
        return
    if args.chat:
        arch.mcp.call("chat_send", {"text": "Architect ready. Type @claude <what to build or change>."})
        while True:
            got = arch.mcp.json("chat_wait", {"timeout_s": 600})
            for m in got.get("messages", []):
                text = m.get("text") or m.get("message") or ""
                if not text:
                    continue
                arch.mcp.call("chat_send", {"text": "On it..."})
                out = run(text)
                arch.mcp.call("chat_send", {"text": out[:600]})
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text:
            run(text)


if __name__ == "__main__":
    main()
