# Sources

Everything is summarised in my own words. Trust levels: **A** = primary/authoritative (game files, wiki), **B** = reasonable community guide, **C** = low-quality/SEO page seen only as a search snippet, used only to confirm a generic point shared by several sources.

## A. Primary: files read locally (ground truth for ids and multiblock rules)

| What | Where |
|---|---|
| Block id existence, 1.21.1 vanilla (1062 blockstate files) | `G:\Games\Minecraft\Curse\Install\versions\1.21.1\1.21.1.jar` -> `assets/minecraft/blockstates/*.json` |
| Vanilla stairs / trapdoor facing semantics | same jar, `assets/minecraft/blockstates/oak_stairs.json`, `oak_trapdoor.json`, `models/block/stairs.json`, `template_orientable_trapdoor_open.json` |
| Mod block ids (all mods, ~560 jars indexed) | `G:\Games\Minecraft\Curse\Instances\All the Mods 10 - ATM10\mods\*.jar` -> `assets/<modid>/blockstates/*.json` (read-only; extracted index in `C:\Users\MIcha\AppData\Local\Temp\claude\style-kb\work\`) |
| AE2 controller rules | `appliedenergistics2-19.2.18.jar` -> `assets/ae2/ae2guide/items-blocks-machines/controller.md` |
| AE2 crafting CPU rules | same jar -> `.../crafting_cpu_multiblock.md` |
| AE2 quantum bridge, spatial IO | same jar -> `.../quantum_bridge.md`, `ae2-mechanics/spatial-io.md` |
| AdvancedAE quantum computer rules | `AdvancedAE-1.6.12-1.21.1.jar` -> `assets/advanced_ae/ae2guide/aae_intro/quantum_computer.md`, `assets/advanced_ae/ae2guide/structure/quantum_computer_multiblock.snbt` |
| ExtendedAE assembler matrix rules | `ExtendedAE-1.21-2.2.43-neoforge.jar` -> `assets/extendedae/ae2guide/epp_intro/assembler_matrix.md`, `.../structure/assembler_matrix.snbt` |
| Block state property names (Create, Handcrafted, Supplementaries, AE2, EAE) | each jar's `assets/<modid>/blockstates/<name>.json` |

## A. Primary: Minecraft Wiki (fetched and summarised)

- https://minecraft.wiki/w/Tutorial:Adding_beauty_to_constructions - depth (bay windows, arches), weathering with cracked/mossy variants, floor options, ceiling heights (3-4 normal, 5-6 medieval living rooms, 10-12 castle halls), hallway widths, lighting ideas (lamps, sea lanterns, chandeliers).
- https://minecraft.wiki/w/Tutorial:Color_palette - choose main blocks first, check contrast at distance, 3-4 step gradients, substitute blocks for missing colours (pumpkin = orange, melon = green), varying the frame block.
- https://minecraft.wiki/w/Tutorial:Building_a_metropolis/Buildings - per-style hints (skyscrapers, nether/end themes, rare blocks as accents, windowless secure interiors, stone for fortified).
- https://minecraft.wiki/w/Tutorial:Construction - roofs, depth for walls (extra blocks at intervals), overhangs, terrain-fitting houses, lighthouses.
- https://minecraft.wiki/w/Light - light levels of emitting blocks (used in principles.md L2) and 1.21 mob-spawn light rule (block light 0 needed for hostile spawns).
- https://minecraft.wiki/w/Minecraft:_Guide_to_Creative - table of contents only (aesthetics, decor, lighting, outdoor chapters); no body text was available through the fetch, so no content from it is used.
- Search listing consulted only for page discovery: https://minecraft.wiki/w/Tutorial:Best_building_materials , https://minecraft.wiki/w/Tutorial:Pixel_art

## B. Community guides (fetched and summarised)

- https://lamppost.bearblog.dev/building-in-minecraft-a-simple-guide/ - blocking out with wool, small related palettes with a 3-step gradient, shallow (~1 block) relief, patchy weathering noise, shading roofs near dormers.
- https://verbina29.neocities.org/articles/mcBuilding - depth as the top fundamental (overhangs, outer pillars, doors set inside), L/T silhouettes, contrast in value/hue, accents via details, weathering with cracked/mossy/darker variants, remove blocks for divots.
- https://videohighlight.com/v/WD7Uw-ktI9E ("How to be a Better Minecraft Builder" video summary) - light/dark mixing, complementary colours with similar hues, stairs/slabs/walls/trapdoors for layers, subtle depth, mistake list (too-similar tones, ignoring viewing distance, over-detailing, over-variety of blocks).

## C. Search-snippet only (not fetched or blocked; used only for generic points confirmed by several)

- https://www.planetminecraft.com/blog/how-to-become-a-better-builder-basic-depth-and-detail/ (fetch returned 403): push wall blocks back a layer for depth; move a column in/out every few blocks.
- https://minecraft.how/blog/post/minecraft-building-techniques-stunning-builds-2026 , https://minecraft.how/blog/post/minecraft-house-design-tips-1 : 4-5 block ceilings; 3-5 block types; hidden floor lights under carpet.
- https://craftdex.net/es/articles/the-architecture-of-builds : the 60/30/10 heuristic (primary/secondary/accent). It is a rule of thumb from interior design, not a game rule.
- https://www.instructables.com/how-to-build-a-medieval-house-in-minecraft , https://www.planetminecraft.com/blog/how-to-make-a-medieval-house-easy/ : timber-frame spacing (log pillars every 3-4), cobblestone base 1-2 high, 1-block roof overhang.
- https://diamondlobby.com/minecraft/futuristic-minecraft-builds/ , https://sportskeeda.com/minecraft/10-best-minecraft-futuristic-build-ideas : quartz/iron/glass + one vivid accent for sci-fi.
- https://createmod.com/schematics/industrial-estate and the Create-style search results (createmod.com): andesite + iron sheet + shingle roof as a common Create industrial palette; show machinery behind glass.
- https://minecraft.gamepedia.com/Tutorials/Tips_for_your_house (old wiki mirror, seen in search results only).
- Japanese-style roof/eaves points (gentle curve, 1+ block eave, spruce/dark oak, white panes as shoji) came from several low-quality SEO pages (c. "crafting-japanese-roofs-in-minecraft" results); only the points repeated across them are used.

## D. Own knowledge (not from a source)

Roof stair orientation, arch construction, circle row widths, rack/catwalk recipes, the interior-design numbers in the scale table (consistent with the wiki figures above), and the showcase-hall proportions for a 7x7x7 machine are my own design and arithmetic. The controller-shape analysis (wireframe cube = 68 blocks, which fills are invalid) derives from rule 3 of the controller guide text.

## Not verified (see end of this file for the list)

1. Behaviour of placing an empty `ae2:cable_bus` block as a ghost (id exists; behaviour not tested; not used).
2. Maximum Crafting CPU size (not in the guide; AE2 default is 16 from memory).
3. Which faces of a formed Quantum Computer accept cables (the guide only says power goes in via the core's up/down faces for a standalone core).
4. Whether `ae2:quartz_vibrant_glass` and `ae2:quartz_fixture` emit light (names suggest so; not read from data).
5. `handcrafted:*` furniture states: only `facing` is given; other properties (`color`, `shape`, `type`) are left at defaults.
6. `minecraft:light[level=N]` is invisible; the ghost renderer may not show it.
7. The server config of AdvancedAE can change the 7x7x7 limit; ATM10 defaults are not checked.
