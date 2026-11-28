"""Suggest improvements for an area the player built: one Haiku call over a compact survey of the real blocks.

  python suggest.py -s job1 --survey region.json --out result.json [--max-cost 0.10] [--no-overlay]

Started by the mod (`/ghost suggest`, MCP tool `ghost_suggest`). `region.json` is `world_survey`-format JSON plus a
`region` block (palette counts, built bounding box, features, per-building footprints, roof flatness, lights per side)
written by WorldSurvey.region(). The model answers with 3-6 short suggestions as JSON; for a few of them it may pick a
deterministic `fix` (gable_roof, lanterns, corner_posts) which this file turns into cheap survival blocks (the optional
ghost overlay, absolute world coordinates). Result JSON written to --out:

  {"suggestions": [{"text", "fix", "building", "material"}], "blocks": [[x, y, z, "minecraft:block[state]"]], "cost": usd}

No Minecraft connection is needed (the survey is the only input). The API key comes from architect/.env, read by
architect.py when it is imported (api key is never read, printed or logged here). Terrain code lives in terrain.py (was
site.py, which shadowed the stdlib `site`). Offline test: python test_suggest.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

import terrain

FIXES = ("gable_roof", "lanterns", "corner_posts")
MAX_SUGGESTIONS = 6
MAX_TEXT = 140
MAX_BLOCKS = 3000
# material -> (stairs, slab, post block). All plain survival blocks.
MATERIALS = {
    "oak": ("oak_stairs", "oak_slab", "oak_log"),
    "spruce": ("spruce_stairs", "spruce_slab", "spruce_log"),
    "dark_oak": ("dark_oak_stairs", "dark_oak_slab", "dark_oak_log"),
    "birch": ("birch_stairs", "birch_slab", "birch_log"),
    "stone_brick": ("stone_brick_stairs", "stone_brick_slab", "stone_bricks"),
    "cobblestone": ("cobblestone_stairs", "cobblestone_slab", "cobblestone"),
    "brick": ("brick_stairs", "brick_slab", "bricks"),
}
CONTRAST = ("spruce", "dark_oak", "oak", "stone_brick", "cobblestone")

SYSTEM = (
    "You review Minecraft builds. You get a compact JSON survey of a region the player built (block palette counts, "
    "buildings with bounding box, roof flatness, lights per side, glass, doors, terrain features). Reply with ONLY a JSON "
    "object, no prose, no code fence:\n"
    '{"suggestions": [{"text": "...", "fix": null, "building": 0, "material": null}]}\n'
    "Rules: 3 to 6 suggestions, most useful first. text = one short imperative sentence (max 110 chars) that names the "
    "building id or side and cites a number from the survey (e.g. 'Building 0 roof is 92% flat: add a gable'; 'No light "
    "on the east wall: add lanterns'; 'Only 1 block type: mix in accents'). Only suggest what the survey supports. Use "
    "cheap survival blocks only. fix is optional and may be one of: gable_roof (flat roofs only), lanterns (walls with 0 "
    "lights), corner_posts (plain walls, few block types), or null for advice without an overlay. building = the "
    "building id the fix applies to (required with a fix). material = oak, spruce, dark_oak, birch, stone_brick, "
    "cobblestone or brick (a contrasting accent for the fix) or null. At most one fix of each kind per building."
)


# ------------------------------------------------------------------ survey


def load_region(path) -> tuple[dict, "terrain.Survey"]:
    raw = json.loads(Path(path).read_text("utf-8"))
    if "region" not in raw:
        raise ValueError("survey has no 'region' block (use the mod's ghost_suggest survey)")
    return raw, terrain.Survey.from_json(raw)


def summarize(raw: dict) -> dict:
    """What the model sees: no grids (y/f/bmap), only the numbers."""
    reg = raw["region"]
    keep = {k: v for k, v in reg.items() if k not in ("bmap", "bmap_format")}
    out = {"center": raw.get("center"), "radius": raw.get("radius"), "biome": raw.get("biome"), "dim": raw.get("dim")}
    for k in ("ymin", "ymax", "ymed", "water_pct", "lava_pct", "tree_pct", "slope", "dominant_ground"):
        if k in raw:
            out[k] = raw[k]
    out.update(keep)
    return out


def build_prompt(summary: dict, overlay: bool) -> tuple[str, str]:
    n = len(summary.get("buildings") or [])
    user = "Survey:\n" + json.dumps(summary, separators=(",", ":"))
    if not summary.get("built_blocks"):
        user += "\nNo built blocks were found: say so in one suggestion (aim at a structure) and add nothing else."
    elif not n:
        user += "\nNo building footprints found (only small or low structures): give general advice, fix = null."
    if not overlay:
        user += "\nThe player does not want an overlay: use fix = null everywhere."
    return SYSTEM, user


# ------------------------------------------------------------------ parsing


def parse_reply(text: str, n_buildings: int) -> list[dict]:
    """Tolerant: strips code fences / prose around the JSON, drops bad items, caps at 6. Raises ValueError if nothing usable."""
    if not isinstance(text, str):
        raise ValueError("no text")
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in the reply")
    try:
        data = json.loads(t[a:b + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"bad JSON: {e}") from e
    items = data.get("suggestions") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("no 'suggestions' list")
    out, seen = [], set()
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        if not isinstance(it, dict):
            continue
        txt = " ".join(str(it.get("text") or "").split())
        if not txt:
            continue
        if len(txt) > MAX_TEXT:
            txt = txt[:MAX_TEXT - 3].rstrip() + "..."
        fix = it.get("fix") if it.get("fix") in FIXES else None
        bld = it.get("building")
        bld = bld if isinstance(bld, int) and not isinstance(bld, bool) and 0 <= bld < n_buildings else None
        if fix and bld is None:
            fix = None
        mat = it.get("material") if it.get("material") in MATERIALS else None
        if fix:
            if (fix, bld) in seen:
                fix = None
            else:
                seen.add((fix, bld))
        out.append({"text": txt, "fix": fix, "building": bld, "material": mat})
        if len(out) == MAX_SUGGESTIONS:
            break
    if not out:
        raise ValueError("no usable suggestions")
    return out


# ------------------------------------------------------------------ overlay (deterministic, cheap survival blocks)


def _default_material(b: dict) -> str:
    """First contrasting material that the building does not already use."""
    used = " ".join(p[0] for p in b.get("palette", []))
    for m in CONTRAST:
        key = {"stone_brick": "stone_bricks"}.get(m, m)
        if f"{key}" not in used and f"{m}_planks" not in used:
            return m
    return "spruce"


def lanterns(b: dict, sv) -> dict:
    """Posts with a lantern, 1 block outside every wall that has no light (all walls when none has), every 5 blocks."""
    x0, _, z0, x1, _, z1 = b["bbox"]
    lights = b.get("lights", {})
    sides = [s for s in "nsew" if not lights.get(s)] or ["n", "s", "e", "w"]
    gy = b.get("ground_y")
    out: dict = {}
    for s in sides:
        if s in "ns":
            z = z0 - 1 if s == "n" else z1 + 1
            pts = [(x, z) for x in range(x0 + 1, x1, 5)] or [((x0 + x1) // 2, z)]
        else:
            x = x1 + 1 if s == "e" else x0 - 1
            pts = [(x, z) for z in range(z0 + 1, z1, 5)] or [(x, (z0 + z1) // 2)]
        for x, z in pts[:6]:
            h = sv.height_at(x, z)
            if h is None or sv.flag_at(x, z) in "wl?" or (gy is not None and abs(h - gy) > 3):
                continue
            out[(x, h + 1, z)] = "minecraft:cobblestone_wall"
            out[(x, h + 2, z)] = "minecraft:lantern[hanging=false]"
    return out


def gable_roof(b: dict, sv, material: str) -> dict:
    """A stepped gable above a flat roof: stair rows on both long edges rising to a slab ridge."""
    roof = b.get("roof", {})
    if roof.get("stair_slab_pct", 0) >= 40 or roof.get("distinct_top_heights", 1) >= 6:
        return {}
    x0, _, z0, x1, _, z1 = b["bbox"]
    top = roof.get("top_y", b["bbox"][4])
    w, d = x1 - x0 + 1, z1 - z0 + 1
    along_x = w >= d  # ridge runs along the long axis
    lo, hi, s = (z0, z1, d) if along_x else (x0, x1, w)
    if s < 3 or s > 21:
        return {}
    stairs, slab, _ = MATERIALS[material]
    out: dict = {}
    longr = range(x0, x1 + 1) if along_x else range(z0, z1 + 1)
    k = 0
    while lo + k <= hi - k:
        y = top + 1 + k
        a, c = lo + k, hi - k
        for t in longr:
            if a == c:
                out[(t, y, a) if along_x else (a, y, t)] = f"minecraft:{slab}[type=bottom]"
                continue
            fa, fc = ("south", "north") if along_x else ("east", "west")
            out[(t, y, a) if along_x else (a, y, t)] = f"minecraft:{stairs}[facing={fa},half=bottom]"
            out[(t, y, c) if along_x else (c, y, t)] = f"minecraft:{stairs}[facing={fc},half=bottom]"
        k += 1
    return out


def corner_posts(b: dict, sv, material: str) -> dict:
    """Vertical accent posts on the four corners (they replace the wall blocks there: build them over the wall)."""
    x0, y0, z0, x1, _, z1 = b["bbox"]
    top = b.get("roof", {}).get("top_y", b["bbox"][4])
    post = MATERIALS[material][2]
    state = f"minecraft:{post}" + ("[axis=y]" if post.endswith("_log") else "")
    out: dict = {}
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        for y in range(y0, top + 1):
            out[(x, y, z)] = state
    return out


def overlay_blocks(suggestions: list[dict], buildings: list[dict], sv) -> list[list]:
    blocks: dict = {}
    for s in suggestions:
        fix, bi = s["fix"], s["building"]
        if not fix or bi is None or bi >= len(buildings):
            continue
        b = buildings[bi]
        mat = s["material"] or _default_material(b)
        if fix == "lanterns":
            got = lanterns(b, sv)
        elif fix == "gable_roof":
            got = gable_roof(b, sv, mat)
        else:
            got = corner_posts(b, sv, mat)
        s["blocks"] = len(got)
        blocks.update(got)
        if len(blocks) > MAX_BLOCKS:
            break
    return [[x, y, z, st] for (x, y, z), st in list(blocks.items())[:MAX_BLOCKS]]


# ------------------------------------------------------------------ model call + run


def _arch():
    """architect.py (loads architect/.env itself on import). Imported late so tests and parsing never need it."""
    sys.path.insert(0, str(HERE))
    import architect  # noqa: PLC0415

    return architect


def run(survey_path, out_path, max_cost: float = 0.10, overlay: bool = True, client=None, cost_fn=None,
        model: str | None = None, log=print) -> dict:
    """One model call (a second only if the first reply is unusable and the cap allows). Returns the result dict
    (also written to out_path). Raises RuntimeError on failure or when the cost cap stops it."""
    raw, sv = load_region(survey_path)
    summary = summarize(raw)
    buildings = summary.get("buildings") or []
    system, user = build_prompt(summary, overlay)
    if client is None:
        arch = _arch()
        import anthropic  # noqa: PLC0415

        client = (anthropic.Anthropic(base_url=arch.BASE_URL, api_key="local", timeout=120) if arch.LOCAL
                  else anthropic.Anthropic(timeout=120))
        cost_fn = cost_fn or (lambda u: 0.0 if arch.LOCAL else arch.usage_cost(u))
        model = model or arch.MODEL
    cost = 0.0
    est = (len(system) + len(user)) / 3.5 * 0.10 / 1e6  # input estimate at Haiku list price
    if max_cost and est >= max_cost:
        raise RuntimeError(f"survey too big for the cost cap (est ${est:.3f} >= ${max_cost:.2f})")
    err = "no reply"
    suggestions = None
    msgs = [{"role": "user", "content": user}]
    for attempt in range(2):
        resp = client.messages.create(model=model, max_tokens=1200, system=system, messages=msgs,
                                      output_config={"effort": "low"})
        cost += cost_fn(resp.usage)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        try:
            suggestions = parse_reply(text, len(buildings))
            break
        except ValueError as e:
            err = str(e)
            log(f"reply not usable ({err}); cost ~${cost:.4f}")
            if max_cost and cost >= max_cost:
                break
            msgs = [{"role": "user", "content": user},
                    {"role": "assistant", "content": text or "{}"},
                    {"role": "user", "content": "That was not valid. Reply with ONLY the JSON object described."}]
    if suggestions is None:
        raise RuntimeError(f"model gave no usable suggestions: {err} (cost ~${cost:.4f}"
                           + (", cap reached)" if max_cost and cost >= max_cost else ")"))
    blocks = overlay_blocks(suggestions, buildings, sv) if overlay else []
    result = {"suggestions": suggestions, "blocks": blocks, "cost": round(cost, 5), "model": model}
    Path(out_path).write_text(json.dumps(result), "utf-8")
    for i, s in enumerate(suggestions, 1):
        log(f"SUGGEST {i}: {s['text']}" + (f" [{s['fix']} b{s['building']}]" if s["fix"] else ""))
    log(f"[{model}, cost ~${cost:.4f}, {len(blocks)} overlay blocks]")
    if max_cost and cost >= max_cost:
        log(f"(cost cap ${max_cost:.2f} reached)")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--session", default="suggest")
    ap.add_argument("--survey", required=True, help="region survey JSON written by the mod")
    ap.add_argument("--out", required=True, help="result JSON path")
    ap.add_argument("--max-cost", type=float, default=0.10)
    ap.add_argument("--no-overlay", action="store_true")
    a = ap.parse_args()
    try:
        run(a.survey, a.out, a.max_cost, not a.no_overlay)
    except Exception as e:  # noqa: BLE001 - one clean line for the mod's log
        print(f"error: {e}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
