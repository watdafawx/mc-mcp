"""Block catalogue for the pack: every placeable block with what it costs to make, where it comes from, its average
colour and its shape, built offline from the instance's jars (no game needed).

    python blocklib.py build            -> knowledge/blocklib.json
    python blocklib.py find wall --colour "#e8dcc0" --max-cost 2 [--ns chipped,rechiseled] [--kw brick] [-n 20]

Cost is in "cobble units" of raw material per block: cobble/sand/dirt/log ~1, iron ingot 3, gold 4, diamond 40.
It is the cheapest recipe chain found in crafting (shaped/shapeless), stonecutting and smelting, plus the free
chisel workbenches (chipped, rechiseled, chisel): every block in a chisel group costs the same as the group's
cheapest member. Blocks with no recipe chain get source "gather" (mined/found) or "none" (not obtainable by
normal crafting); those are only cheap if the raw price table below lists them.
"""
from __future__ import annotations

import io
import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "knowledge" / "blocklib.json"
TEXIDX = HERE / "knowledge" / "_tex.json"  # texture id -> [jar, member], for contact sheets
INSTANCE = Path(r"G:\Games\Minecraft\Curse\Instances\All the Mods 10 - ATM10")
VANILLA = Path(r"G:\Games\Minecraft\Curse\Install\versions\1.21.1\1.21.1.jar")

# Raw material prices (cobble units). Everything else is derived from recipes.
RAW = {
    # stone & earth
    "minecraft:cobblestone": 1, "minecraft:cobbled_deepslate": 1, "minecraft:stone": 1.2, "minecraft:deepslate": 1.2,
    "minecraft:andesite": 1, "minecraft:diorite": 1, "minecraft:granite": 1, "minecraft:tuff": 1, "minecraft:calcite": 6,
    "minecraft:dirt": 0.5, "minecraft:grass_block": 1, "minecraft:sand": 0.7, "minecraft:red_sand": 0.8,
    "minecraft:gravel": 0.7, "minecraft:clay_ball": 0.4, "minecraft:clay": 1.6, "minecraft:netherrack": 0.5,
    "minecraft:blackstone": 1, "minecraft:basalt": 1, "minecraft:end_stone": 2, "minecraft:obsidian": 4,
    "minecraft:soul_sand": 1, "minecraft:soul_soil": 1, "minecraft:mud": 1, "minecraft:moss_block": 1.5,
    "minecraft:snowball": 0.2, "minecraft:ice": 1, "minecraft:packed_ice": 9, "minecraft:dripstone_block": 2,
    "minecraft:amethyst_shard": 1.5, "minecraft:magma_block": 3, "minecraft:terracotta": 1.6,
    # wood & plants
    **{f"minecraft:{w}_log": 1 for w in ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry")},
    "minecraft:crimson_stem": 1, "minecraft:warped_stem": 1, "minecraft:bamboo": 0.2, "minecraft:stick": 0.12,
    "minecraft:vine": 0.3, "minecraft:sugar_cane": 0.3, "minecraft:wheat": 0.3, "minecraft:kelp": 0.2,
    "minecraft:dried_kelp": 0.3, "minecraft:cactus": 0.5, "minecraft:pumpkin": 1, "minecraft:melon_slice": 0.2,
    "minecraft:hay_block": 2.7, "minecraft:nether_wart": 0.5, "minecraft:honeycomb": 2, "minecraft:honey_bottle": 2,
    # mob drops
    "minecraft:string": 0.6, "minecraft:leather": 1.5, "minecraft:bone_meal": 0.3, "minecraft:bone": 0.9,
    "minecraft:feather": 0.5, "minecraft:slime_ball": 2, "minecraft:gunpowder": 1, "minecraft:ink_sac": 1,
    "minecraft:glow_ink_sac": 2, "minecraft:ender_pearl": 6, "minecraft:blaze_rod": 6, "minecraft:ghast_tear": 12,
    "minecraft:phantom_membrane": 6, "minecraft:prismarine_shard": 2.5, "minecraft:prismarine_crystals": 3.5,
    "minecraft:shulker_shell": 40, "minecraft:rabbit_hide": 1, "minecraft:white_wool": 2.4, "minecraft:egg": 0.5,
    # ores
    "minecraft:coal": 1, "minecraft:charcoal": 1, "minecraft:iron_ingot": 3, "minecraft:copper_ingot": 1.2,
    "minecraft:gold_ingot": 4, "minecraft:gold_nugget": 0.45, "minecraft:iron_nugget": 0.34,
    "minecraft:redstone": 1, "minecraft:lapis_lazuli": 1.2, "minecraft:quartz": 1.5, "minecraft:diamond": 40,
    "minecraft:emerald": 25, "minecraft:netherite_scrap": 120, "minecraft:glowstone_dust": 1.2,
    "minecraft:echo_shard": 60, "minecraft:nether_star": 2000, "minecraft:dragon_breath": 50,
    "minecraft:raw_iron": 3, "minecraft:raw_copper": 1.2, "minecraft:raw_gold": 4, "minecraft:flint": 0.7,
    # light sources found in the world
    "minecraft:shroomlight": 2, "minecraft:ochre_froglight": 6, "minecraft:verdant_froglight": 6,
    "minecraft:pearlescent_froglight": 6, "minecraft:sea_pickle": 1,
    **{f"create:{s}": 1 for s in ("asurine", "crimsite", "limestone", "ochrum", "scorchia", "scoria", "veridium")},
    "ae2:sky_stone_block": 1.5, "ae2:certus_quartz_crystal": 2, "ae2:charged_certus_quartz_crystal": 2.5,
    "ae2:fluix_crystal": 4, "ae2:quartz_block": 8, "ae2:fluix_block": 16, "ae2:quartz_glass": 3,
    "minecraft:chorus_fruit": 0.5, "minecraft:cocoa_beans": 0.3, "minecraft:sweet_berries": 0.2,
    "minecraft:brown_mushroom": 0.3, "minecraft:red_mushroom": 0.3, "minecraft:crimson_fungus": 0.3,
    "minecraft:warped_fungus": 0.3, "minecraft:lily_pad": 0.3, "minecraft:glow_lichen": 0.3,
    "minecraft:glow_berries": 0.3, "minecraft:moss_carpet": 0.7, "minecraft:spore_blossom": 2,
    **{f"minecraft:{f}": 0.3 for f in ("dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "red_tulip",
       "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "sunflower",
       "lilac", "rose_bush", "peony", "pink_petals", "torchflower", "pitcher_plant", "wither_rose", "beetroot")},
}
# Natural blocks from any mod (logs, stems, leaves, flowers...) are gathered, not crafted: priced like vanilla.
GATHER = [(r"_(log|stem|hyphae)$", 1.0), (r"_wood$", 1.33), (r"(_leaves|_sapling|_mushroom|_flower|_fungus|_roots)$", 0.3),
          (r"(^|:)(raw_|)(\w+_)?(sand|gravel|dirt|clay|mud|moss_block)$", 1.0), (r"_wool$", 2.4)]
CHISEL_MODS = ("chipped", "rechiseled", "chisel")
SKIP_NS = {"allthecompressed"}
# Mods whose blocks look out of place in a base or come from other dimensions; find() skips them unless asked.
EXOTIC = {"eternal_starlight", "forbidden_arcanus", "kaleidoscope_doll", "kaleidoscope_dim_wine", "cobblemon",
          "securitycraft", "ad_astra", "twilightforest", "aether", "deep_aether", "undergarden", "bibliocraft",
          "dyenamicsandfriends", "silentgems", "allthemodium", "draconicevolution", "mysticalagriculture",
          "botania", "occultism", "evilcraft", "theurgy", "ars_nouveau", "chromacarvings", "merrymaking",
          "mcwholidays", "butchercraft", "productivetrees", "chipped_holiday", "structurize", "domum_ornamentum"}
BAD = r"(concrete_powder|_valve|_tank|_ore$|deepslate_.*_ore|tnt|spawner|infested|suspicious|command_block|structure|jigsaw|barrier|_sand$|gravel|bedrock|portal|_egg$|budding|reinforced)"
PLANT = r"(leaves|sapling|_flower|mushroom|fungus|_roots|pumpkin|melon|_crop|vine|_bush|grass$|fern$|petals|moss_carpet|_cake|cactus|hay)"
SHAPES = [("stairs", r"_stairs$"), ("slab", r"_slab$"), ("wall", r"_wall$"), ("fence", r"_fence$|fence_gate$"),
          ("pane", r"_pane$|_bars$"), ("door", r"_door$"), ("trapdoor", r"_trapdoor$"),
          ("pillar", r"pillar|_log$|_column|_stem$"), ("roof", r"^mcwroofs:|_roof"),
          ("glass", r"glass"), ("window", r"^mcwwindows:|window"),
          ("light", r"lamp|lantern|(?<![a-z])light(?!_(blue|gray|grey))|torch|candle|froglight|glowstone|end_rod|luminax|shroomlight"), ("path", r"^mcwpaths:"), ("furniture", r"^(handcrafted|mcwfurnitures|refurbished_furniture|bibliocraft|cluttered):"),
          ("carpet", r"carpet|rug"), ("button", r"_button$|_pressure_plate$")]


def jars():
    yield VANILLA
    nf = sorted(VANILLA.parents[2].glob("libraries/net/neoforged/neoforge/21.1.*/neoforge-*-universal.jar"),
                key=lambda q: [int(x) for x in q.parent.name.split(".")])
    if nf:
        yield nf[-1]  # the c: common tags live here
    yield from sorted((INSTANCE / "mods").glob("*.jar"))


def _ings(x):
    """Ingredient -> list of alternatives, each ('item', id) or ('tag', name)."""
    if x is None:
        return []
    if isinstance(x, str):
        return [("tag", x[1:])] if x.startswith("#") else [("item", x)]
    if isinstance(x, list):
        out = []
        for e in x:
            out += _ings(e)
        return out
    if isinstance(x, dict):
        if "item" in x:
            return [("item", x["item"])]
        if "tag" in x:
            return [("tag", x["tag"])]
        if "items" in x:
            return _ings(x["items"])
        if "ingredient" in x:
            return _ings(x["ingredient"])
        if "children" in x:  # neoforge:compound
            return _ings(x["children"])
        if "base" in x:  # neoforge:difference / intersection: the base is a fair upper bound
            return _ings(x["base"])
    return [("bad", "")]


CREATE_OK = ("create:item_application", "create:deploying", "create:pressing", "create:cutting", "create:mixing",
             "create:compacting", "create:filling", "create:sandpaper_polishing")


def _result(r):
    res = r.get("result")
    if res is None and isinstance(r.get("results"), list) and r["results"]:
        res = r["results"][0]
        if isinstance(res, dict) and res.get("chance", 1) < 1:
            return None, 0
    if isinstance(res, str):
        return res, 1
    if isinstance(res, dict):
        return res.get("id") or res.get("item"), int(res.get("count", 1))
    return None, 0


def build():
    recipes = []  # (out, count, [alt-lists])
    wgroups = []  # rechiseled: [(block, worth)] -- any member converts to any other at its worth
    tags = defaultdict(set)  # item tags
    blocks = {}  # id -> texture ref candidates
    models = {}  # "ns:path" -> model json
    textures = {}  # "ns:block/x" -> (zip path, member)
    for jp in jars():
        try:
            z = zipfile.ZipFile(jp)
        except (zipfile.BadZipFile, OSError):
            continue
        for n in z.namelist():
            if not n.endswith((".json", ".png")):
                continue
            p = n.split("/")
            if len(p) < 4:
                continue
            if p[0] == "data" and n.endswith(".json"):
                ns = p[1]
                if p[2] == "chiseling_recipes":
                    try:
                        ents = json.loads(z.read(n)).get("entries", [])
                    except ValueError:
                        continue
                    wgroup = []
                    for e in ents:
                        e = {"block": e} if isinstance(e, str) else e
                        for k, v in e.items():
                            if isinstance(v, str):
                                w = e.get(k + "_worth", 0.75 if "stairs" in k else 1.0)
                                wgroup.append((v, float(w)))
                    if wgroup:
                        wgroups.append(wgroup)
                    continue
                if p[2] in ("recipe", "recipes"):
                    try:
                        r = json.loads(z.read(n))
                    except ValueError:
                        continue
                    t = r.get("type", "")
                    out, cnt = _result(r)
                    if not out or ns in SKIP_NS:
                        continue
                    if t.endswith("crafting_shaped"):
                        keys = r.get("key", {})
                        counts = defaultdict(int)
                        for row in r.get("pattern", []):
                            for ch in row:
                                if ch != " ":
                                    counts[ch] += 1
                        ins = []
                        for ch, k in counts.items():
                            ins += [_ings(keys.get(ch))] * k
                        recipes.append((out, cnt, ins))
                    elif t.endswith("crafting_shapeless"):
                        recipes.append((out, cnt, [_ings(i) for i in r.get("ingredients", [])]))
                    elif t == "refurbished_furniture:workbench_constructing":
                        ins = []
                        for m in r.get("materials", []):
                            ins += [_ings(m.get("ingredient"))] * int(m.get("count", 1))
                        recipes.append((out, cnt, ins))
                    elif t in CREATE_OK and not r.get("heat_requirement"):
                        ins = [_ings(i) for i in r.get("ingredients", []) if not (isinstance(i, dict) and ("fluid" in i or "type" in i and "fluid" in str(i.get("type"))))]
                        if ins:
                            recipes.append((out, cnt, ins + [[("item", "minecraft:stick")]]))  # small machine overhead
                    elif t.endswith("stonecutting"):
                        recipes.append((out, cnt, [_ings(r.get("ingredient"))]))
                    elif t.endswith(("smelting", "blasting")):
                        recipes.append((out, cnt, [_ings(r.get("ingredient")), [("item", "minecraft:coal")]]))
                elif p[2] == "tags" and p[3] in ("item", "items", "block", "blocks"):
                    tag = ns + ":" + "/".join(p[4:])[:-5]
                    if p[3].startswith("block"):
                        if ns not in CHISEL_MODS:
                            continue
                        tag = "block#" + tag
                    try:
                        vals = json.loads(z.read(n)).get("values", [])
                    except (ValueError, AttributeError):
                        continue
                    for v in vals:
                        v = v.get("id") if isinstance(v, dict) else v
                        if isinstance(v, str):
                            if not v.startswith("#") and ":" not in v:
                                v = "minecraft:" + v
                            tags[tag].add(v)
            elif p[0] == "assets":
                ns = p[1]
                if p[2] == "blockstates" and n.endswith(".json") and ns not in SKIP_NS:
                    try:
                        bs = json.loads(z.read(n))
                    except ValueError:
                        continue
                    m = None
                    if "variants" in bs and bs["variants"]:
                        v = next(iter(bs["variants"].values()))
                        v = v[0] if isinstance(v, list) else v
                        m = v.get("model") if isinstance(v, dict) else None
                    elif "multipart" in bs and bs["multipart"]:
                        a = bs["multipart"][0].get("apply")
                        a = a[0] if isinstance(a, list) else a
                        m = a.get("model") if isinstance(a, dict) else None
                    blocks[f"{ns}:{'/'.join(p[3:])[:-5]}"] = m
                elif p[2] == "models" and n.endswith(".json"):
                    try:
                        models[f"{ns}:{'/'.join(p[3:])[:-5]}"] = json.loads(z.read(n))
                    except ValueError:
                        pass
                elif p[2] == "textures" and p[3] == "block" and n.endswith(".png"):
                    textures[f"{ns}:{'/'.join(p[3:])[:-4]}"] = (jp, n)
    print(f"{len(recipes)} recipes, {len(tags)} item tags, {len(blocks)} blocks, {len(models)} models", flush=True)

    def expand(tag, seen=None):
        seen = seen or set()
        if tag in seen:
            return set()
        seen.add(tag)
        out = set()
        for v in tags.get(tag, ()):
            out |= expand(v[1:], seen) if v.startswith("#") else {v}
        return out

    tagm = {t: expand(t) for t in tags}
    tagm = {t: m for t, m in tagm.items()}
    cost = dict(RAW)  # replaced below
    source = {k: "raw" for k in RAW}
    why = {}

    def alt_cost(alts):
        best = math.inf
        for kind, v in alts:
            if kind == "item":
                best = min(best, cost.get(v, math.inf))
            elif kind == "tag":
                for m in tagm.get(v) or tagm.get("block#" + v, ()):
                    best = min(best, cost.get(m, math.inf))
        return best

    # chisel groups: every tag of the chisel mods is a group of interchangeable blocks
    groups = []
    for t, mem in tagm.items():
        ns_ = t.split(":")[0].replace("block#", "")
        if ns_ in CHISEL_MODS:
            base = "minecraft:" + t.split(":", 1)[1]
            g = set(mem) | ({base} if base in cost or base in blocks else set())
            if len(g) > 1:
                groups.append(g)
    # Knuth/Dijkstra: finalise the cheapest item, then fire the recipes and chisel groups it completes. Each item's
    # price is fixed once, from already-final inputs, so recipe loops (block<->slab, uncrafting) can't spiral to 0.
    import heapq
    partial = re.compile(r"_(slab|stairs|wall|fence|fence_gate|pane|button|pressure_plate|carpet|door|trapdoor)(_connecting)?$")
    wg = [g for g in wgroups]
    for g in groups:
        wg.append([(b, 1.0) for b in g if not partial.search(b)])
    uses = defaultdict(list)  # item -> [(recipe, slot)]
    for ri, (out, cnt, ins) in enumerate(recipes):
        for si, alts in enumerate(ins):
            mem = set()
            for kind, v in alts:
                if kind == "item":
                    mem.add(v)
                elif kind == "tag":
                    mem |= tagm.get(v) or tagm.get("block#" + v, set())
            for m in mem:
                uses[m].append((ri, si))
    slot = [[None] * len(r[2]) for r in recipes]
    left = [len(r[2]) for r in recipes]
    ingroup = defaultdict(list)
    for gi, g in enumerate(wg):
        for b, w in g:
            ingroup[b].append((gi, w))
    final = {}
    cost = {}
    heap = [(c, k, "raw", None) for k, c in RAW.items()]
    craftable = {r[0] for r in recipes}
    for b in blocks:
        if b in RAW or b in craftable:
            continue
        for rx, c in GATHER:
            if re.search(rx, b):
                heap.append((c, b, "gather", None))
                break
    # copper oxidises by itself: exposed/weathered/oxidized cost the same as fresh copper
    for b in blocks:
        for st in ("exposed_", "weathered_", "oxidized_"):
            if st in b:
                fresh = b.replace(st, "")
                if fresh == "minecraft:copper":
                    fresh = "minecraft:copper_block"
                recipes.append((b, 1, [[("item", fresh)]]))
                slot.append([None]); left.append(1); uses[fresh].append((len(recipes) - 1, 0))
                break
    # concrete hardens from powder in water
    for b in blocks:
        if b.endswith("_concrete") and b + "_powder" in blocks:
            recipes.append((b, 1, [[("item", b + "_powder")]]))
            slot.append([None]); left.append(1); uses[b + "_powder"].append((len(recipes) - 1, 0))
    heapq.heapify(heap)
    while heap:
        c, item, src, info = heapq.heappop(heap)
        if item in final:
            continue
        final[item] = c
        source[item] = src
        if info:
            why[item] = info
        for ri, si in uses.get(item, ()):
            if slot[ri][si] is None:
                slot[ri][si] = c
                left[ri] -= 1
                if left[ri] == 0:
                    out, cnt, ins = recipes[ri]
                    if out not in final:
                        heapq.heappush(heap, (sum(slot[ri]) / max(1, cnt), out, "craft", (cnt, ins)))
        for gi, w in ingroup.get(item, ()):
            for b, wb in wg[gi]:
                if b not in final:
                    heapq.heappush(heap, (c / w * wb, b, "chisel", (0, [[["from", item, gi]]])))
    cost = final
    # report the uncosted ingredients that block the most recipes (candidates for the RAW table)
    blockers = defaultdict(int)
    for ri, (out, cnt, ins) in enumerate(recipes):
        if out in final:
            continue
        for si, alts in enumerate(ins):
            if slot[ri][si] is None:
                blockers[" | ".join(sorted(v for _, v in alts))[:80]] += 1
    (HERE / "knowledge" / "_blockers.txt").write_text(
        "\n".join(f"{n:5} {k}" for k, n in sorted(blockers.items(), key=lambda kv: -kv[1])[:300]), "utf-8")
    # chisel mod (no data tags): chisel:<pattern>/<material> costs the vanilla material
    for b in blocks:
        if b.startswith("chisel:") and "/" in b and cost.get(b, math.inf) == math.inf:
            mat = b.split("/")[-1]
            for cand in (f"minecraft:{mat}_block", f"minecraft:{mat}s", f"minecraft:{mat}"):
                if cand in cost:
                    cost[b] = cost[cand]
                    source[b] = "chisel"
                    break

    # colours
    def tex_of(model, depth=0):
        m = models.get(model if ":" in model else "minecraft:" + model)
        if not m or depth > 6:
            return None
        tx = dict(m.get("textures", {}))
        if m.get("parent"):
            par = m["parent"] if ":" in m["parent"] else "minecraft:" + m["parent"]
            ptx = tex_of_textures(par, depth + 1)
            tx = {**ptx, **tx}
        for k in ("all", "side", "texture", "end", "top", "particle", "wall", "pane", "cross", "front", "0", "1"):
            v = tx.get(k)
            for _ in range(4):
                if isinstance(v, str) and v.startswith("#"):
                    v = tx.get(v[1:])
            if isinstance(v, str):
                return v if ":" in v else "minecraft:" + v
        return None

    def tex_of_textures(model, depth):
        m = models.get(model)
        if not m or depth > 6:
            return {}
        tx = dict(m.get("textures", {}))
        if m.get("parent"):
            par = m["parent"] if ":" in m["parent"] else "minecraft:" + m["parent"]
            tx = {**tex_of_textures(par, depth + 1), **tx}
        return tx

    def is_full(model, depth=0):
        m = models.get(model if ":" in model else "minecraft:" + model)
        if not m or depth > 8:
            return False
        par = m.get("parent", "")
        if re.search(r"(^|:)block/(cube|cube_all|cube_column|cube_bottom_top|cube_column_horizontal|orientable|leaves)$", par):
            return True
        return bool(par) and is_full(par, depth + 1)

    from PIL import Image
    zcache = {}

    def colour(tex):
        ref = textures.get(tex)
        if not ref:
            return None
        jp, member = ref
        z = zcache.get(jp) or zcache.setdefault(jp, zipfile.ZipFile(jp))
        try:
            im = Image.open(io.BytesIO(z.read(member))).convert("RGBA")
        except Exception:
            return None
        im = im.crop((0, 0, im.width, min(im.height, im.width)))  # first animation frame
        px = list(im.resize((8, 8)).get_flattened_data())
        px = [p for p in px if p[3] > 128] or [p for p in px if p[3] > 10]
        if not px:
            return None
        r, g, b = (sum(p[i] for p in px) // len(px) for i in range(3))
        return f"#{r:02x}{g:02x}{b:02x}"

    lib = {}
    for b, model in blocks.items():
        c = cost.get(b, math.inf)
        src = source.get(b, "none")
        shape = next((s for s, rx in SHAPES if re.search(rx, b)), "block")
        if src == "gather" or re.search(PLANT, b.split(":")[1]):
            shape = "plant"
        tex = tex_of(model) if model else None
        lib[b] = {"cost": None if c == math.inf else round(c, 2), "src": src, "shape": shape,
                  "colour": colour(tex) if tex else None}
        if tex and tex in textures:
            lib[b]["tex"] = tex
        if shape in ("block", "light", "glass") and model and is_full(model):
            lib[b]["full"] = 1
    json.dump({k: [v[0], [a[:3] for a in v[1]]] for k, v in why.items()}, open(HERE / "knowledge" / "_why.json", "w"))
    OUT.write_text(json.dumps(lib, separators=(",", ":")), "utf-8")
    used = {v["tex"] for v in lib.values() if v.get("tex")}
    TEXIDX.write_text(json.dumps({t: [str(textures[t][0]), textures[t][1]] for t in used}), "utf-8")
    ok = sum(1 for v in lib.values() if v["cost"] is not None)
    print(f"wrote {OUT} ({len(lib)} blocks, {ok} with a cost)")


# ----------------------------------------------------------------------------------------------- query

COLOURS = {"white": "#e8e8e8", "cream": "#e6d9b8", "beige": "#d6c49a", "sand": "#d8c890", "yellow": "#e0c040",
           "gold": "#e8b830", "orange": "#d87830", "red": "#a83030", "brown": "#6b4a30", "dark brown": "#3c2a1c",
           "green": "#507a3a", "teal": "#2f7068", "cyan": "#3aa0b0", "light blue": "#80b8e0", "blue": "#3050a0",
           "navy": "#202c50", "purple": "#704090", "pink": "#d890a8", "grey": "#808080", "light grey": "#b0b0b0",
           "dark grey": "#404040", "black": "#1c1c20", "copper": "#c06a48", "brass": "#c8a050"}


def _rgb(h):
    h = COLOURS.get(h.lower(), h).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _dist(a, b):  # perceptual-ish (redmean)
    r = (a[0] + b[0]) / 2
    d = [a[i] - b[i] for i in range(3)]
    return math.sqrt((2 + r / 256) * d[0] ** 2 + 4 * d[1] ** 2 + (2 + (255 - r) / 256) * d[2] ** 2)


_LIB = None


def lib():
    global _LIB
    if _LIB is None:
        _LIB = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {}
    return _LIB


def find(shape: str | None = None, colour: str | None = None, max_cost: float = 3.0, ns: list | None = None,
         kw: str | None = None, n: int = 20, exclude_ns: list | None = None, full: bool = False) -> list[dict]:
    """Cheap blocks matching a shape (block|stairs|slab|wall|pillar|light|glass|window|roof|door|trapdoor|furniture|
    path|fence|pane|carpet|plant), full=True for full cubes only, near a colour (hex or name), at most max_cost, optional namespaces / keyword."""
    want = _rgb(colour) if colour else None
    kws = [k for k in re.split(r"[ ,]+", kw.lower()) if k] if kw else []
    out = []
    for b, v in lib().items():
        if v["cost"] is None or v["cost"] > max_cost:
            continue
        if shape and v["shape"] != shape:
            continue
        bns = b.split(":")[0]
        if ns and bns not in ns:
            continue
        if exclude_ns and bns in exclude_ns:
            continue
        if not ns and bns in EXOTIC:
            continue
        if re.search(BAD, b):
            continue
        if full and not v.get("full"):
            continue
        if kws and not all(k in b for k in kws):
            continue
        if want and not v["colour"]:
            continue
        d = _dist(want, _rgb(v["colour"])) if want else 0
        out.append({"id": b, "cost": v["cost"], "src": v["src"], "colour": v["colour"], "d": round(d)})
    out.sort(key=lambda e: (e["d"], e["cost"]) if want else (e["cost"], e["id"]))
    # spread over mods: at most n//4 from one namespace so chipped's thousands don't drown the rest
    per, res = defaultdict(int), []
    for e in out:
        k = e["id"].split(":")[0]
        if per[k] < max(3, n // 4):
            per[k] += 1
            res.append(e)
        if len(res) >= n:
            break
    return res


def find_listed(ids: list[str], shape: str | None = None, colour: str | None = None, kw: str | None = None,
                n: int = 24, full: bool = False) -> list[dict]:
    """Explicitly whitelisted ids (mods/ registry), same filters as find() but NO cost filter: mod machines have no
    recipe cost. Only ids in the library are returned; find() and its default cost cap are unchanged."""
    L = lib()
    want = _rgb(colour) if colour else None
    kws = [k for k in re.split(r"[ ,]+", kw.lower()) if k] if kw else []
    out = []
    for b in ids:
        v = L.get(b)
        if not v or (shape and v["shape"] != shape) or (full and not v.get("full")):
            continue
        if kws and not all(k in b for k in kws):
            continue
        if want and not v["colour"]:
            continue
        out.append({"id": b, "cost": v["cost"], "src": v["src"], "colour": v["colour"],
                    "d": round(_dist(want, _rgb(v["colour"]))) if want else 0})
    if want:
        out.sort(key=lambda e: e["d"])
    return out[:n]


def bill(counts: dict[str, int]) -> dict:
    """Material bill of a build: total cost and the most expensive blocks."""
    L = lib()
    tot, unknown, rows = 0.0, {}, []
    for b, c in counts.items():
        base = b.split("[")[0]
        v = L.get(base)
        if not v or v["cost"] is None:
            unknown[base] = unknown.get(base, 0) + c
            continue
        tot += v["cost"] * c
        rows.append((v["cost"] * c, base, c, v["cost"]))
    rows.sort(reverse=True)
    return {"total_cobble_units": round(tot), "top": [{"id": b, "count": c, "each": e, "total": round(t)}
                                                       for t, b, c, e in rows[:8]],
            "no_recipe": dict(sorted(unknown.items(), key=lambda kv: -kv[1])[:10])}


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["find"]:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd"); ap.add_argument("shape", nargs="?")
        ap.add_argument("--colour"); ap.add_argument("--max-cost", type=float, default=3)
        ap.add_argument("--ns"); ap.add_argument("--kw"); ap.add_argument("-n", type=int, default=20)
        a = ap.parse_args()
        for e in find(a.shape, a.colour, a.max_cost, a.ns.split(",") if a.ns else None, a.kw, a.n):
            print(e)


def sheet(ids: list[str], path: str, cols: int = 8, px: int = 72) -> str:
    """Contact sheet of block textures (one tile each, labelled with index + short id + cost) -> JPEG path."""
    from PIL import Image, ImageDraw
    idx = json.loads(TEXIDX.read_text("utf-8"))
    L = lib()
    rows = (len(ids) + cols - 1) // cols
    W, H = cols * (px * 3), rows * (px + 30)
    im = Image.new("RGB", (W, H), (32, 32, 36))
    d = ImageDraw.Draw(im)
    zc = {}
    for i, b in enumerate(ids):
        x, y = (i % cols) * px * 3, (i // cols) * (px + 30)
        v = L.get(b.split("[")[0], {})
        t = v.get("tex")
        if t and t in idx:
            jp, mem = idx[t]
            z = zc.get(jp) or zc.setdefault(jp, zipfile.ZipFile(jp))
            try:
                tile = Image.open(io.BytesIO(z.read(mem))).convert("RGBA")
                tile = tile.crop((0, 0, tile.width, min(tile.height, tile.width))).resize((px, px), Image.NEAREST)
                for k in range(3):  # 3 tiles side by side to show the pattern repeat
                    im.paste(tile, (x + k * px, y), tile)
            except Exception:
                pass
        d.text((x + 2, y + px + 2), f"{i} {b.split(':')[-1][:34]}", fill=(230, 230, 230))
        d.text((x + 2, y + px + 15), f"{b.split(':')[0][:20]} c{v.get('cost')}", fill=(150, 200, 150))
    im.save(path, quality=85)
    return path
