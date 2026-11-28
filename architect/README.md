# Architect

LLM architect: designs themed bases, single structures, and architectural components as ghost builds in a running Minecraft client through mc-mcp. See `architect.py`
(docstring) for the CLI. In game:
- **Ghost Builder screen** (`/ghost gui`, or `G` keybind): two modes:
  - **Prompt / Image**: free-text prompt + optional image path/URL, **Clip: on** (clipboard image), **3D: on** (force Hunyuan3D photo→voxel), Position, Kit, **Generate** (new session), **Iterate** (continue latest session), **Stop**.
  - **Base Style**: full themed base (style, position, kit, layout, fit, Generate/Stop).
  - **Utility bar** (both modes): **Export** (saves `.litematic` to `schematics/`), **Clear**, **Ghosts**, **X-ray**, **FreeCam** (detached client camera for `view()` without `/tp` or cheats).
- **Commands**: `/ghost prompt <text>`, `/ghost ref <clip|url|path> [text]`, `/ghost ref3d <clip|url|path> [text]`, `/ghost iterate <change>`, `/ghost export [name] [litematic|schem|nbt]`, `/ghost freecam [on|off]`, `/ghost generate <style> [look|here|x z] [kit] [layout]`, `/ghost stop`.
- **MCP tools**: `ghost_prompt`, `ghost_camera`, `ghost_generate`, `ghost_generate_status`. `/ghost stop` cancels a running job (kills the process).

## Setup on the machine that runs the client (rig)

The mod starts `architect.py` as a child process **on the machine hosting the game client**, so these must exist there,
next to the mod project (`<project>/architect/`):

1. `architect/.env` with one line `ANTHROPIC_API_KEY=...` (git-ignored; `architect.py` loads it itself; the mod never
   reads, logs or forwards it). `run-on-rig.ps1` mirrors the project, so copy `.env` to rig once and check it survives the mirror.
2. A python venv: `python -m venv architect/.venv` then `architect/.venv/Scripts/pip install anthropic pillow` (plus whatever
   `architect.py` imports). The mod looks for `.venv/Scripts/python.exe`, then `venv/...`,
   then `python` on PATH. Override with `ghostGenerate.python` / `ghostGenerate.architectDir` in `config/mcmcp-common.toml`.
3. mc-mcp's client server reachable at `127.0.0.1:<port>` (the mod passes `MCMCP_URL` and, if set, `MCMCP_TOKEN`).

If anything is missing, `/ghost generate` and `ghost_generate` fail at once with a message naming the missing file.

## Cost cap

`architect.py --max-cost <usd>` (or env `ARCHITECT_MAX_COST`) stops the run when the estimated API cost reaches the cap.
The mod passes `ghostGenerate.costCapUsd` (default 0.15). Estimate is from token usage, so the real bill can be slightly over.

## Direct use

    python architect.py -s mysession --generate steampunk --x 100 --y 66 --z 200 [--kit hextech] [--layout radial] [--max-cost 0.10]

## Suggest mode (suggest.py)

`/ghost suggest` / `ghost_suggest` start `python suggest.py -s <job> --survey <region.json> --out <result.json> [--max-cost 0.10] [--no-overlay]`
in this folder. No Minecraft connection: the input is a survey file from `WorldSurvey.region()` (the normal survey format,
step 1, with `y` = true ground under buildings, plus a `region` block: `built_blocks`, `bbox`, `palette` [[id, n]],
`features`, `buildings` [bbox, size, palette, `roof` {top_y, distinct_top_heights, flat_pct, stair_slab_pct}, `lights`
{n,s,e,w}, glass, doors], `bmap` grid). `summarize()` drops the grids, so the model sees about 1 KB of numbers.

- Prompt and parsing live in `suggest.py`; the reply is JSON `{"suggestions": [{text, fix, building, material}]}`, parsed
  tolerantly (code fences and prose are stripped, bad fixes dropped, max 6, one retry if the cap allows).
- Fixes are deterministic: `gable_roof`, `lanterns`, `corner_posts` (survival materials only). Blocks are absolute world
  coordinates, at most 3000, written to `--out` with the suggestions and the cost. The mod draws them as ghost `suggest`.
- Cost: `architect.usage_cost()` (extracted from the agent loop, same prices) per response; stops at `--max-cost`. The key
  comes from `architect/.env`, read by `architect.py` when `suggest.py` imports it for the model call; `suggest.py` itself
  never touches the key. It imports `terrain.py` normally (renamed from `site.py`, which shadowed the stdlib `site`).
- Offline test (fake client, canned survey, no API): `python test_suggest.py`.

## World-aware sites (terrain.py)

`ghost_generate` / `/ghost generate` survey the client world first (`world_survey`), write the JSON to a temp file and run
`architect.py --survey <file> --near x,z` (plus `--site-rect x,z,w,d,rot` for a previewed `/ghost area`). No survey = the
old flat behaviour, unchanged (so batch scripts keep working). The LLM only sees a one-line summary (platform height,
foundations, trees, layout and wing limit), never the grid, so a build stays around $0.03-0.07.

`terrain.py` is pure python and deterministic (no Minecraft, no API); import it normally or run it as a script:

    python terrain.py plan --survey s.json --style hextech --near x,z     # best layout/wings/rectangle (JSON)
    python terrain.py eval --survey s.json --x 10 --z 20 --w 96 --d 80 [--rot 90]   # score one rectangle (/ghost area move|rotate)
    python terrain.py demo hill|slope|cliff|forest|shoreline|unknown|flat   # fake surveys
    python test_terrain.py                                                # offline tests

**Picker.** Every candidate rectangle of the campus footprint (measured per layout and wing count, 88x85 .. 235x170),
also turned 90 degrees, is scored in O(1) from prefix sums: water, lava, trees, unknown cells, height spread, slope,
earthwork (fill + 1.5 x cut) and a small distance penalty to the aimed spot. Layout/wing configs are tried from the most
ambitious (style layout, 5 wings) to the smallest (spine, 1 wing); utility = fit + 4 per wing + layout bonus - 60 if red.
The platform level is the 60% quantile of the ground (fill is cheaper than cut: ghosts never remove blocks).

**Fit colours** (`class` in the result, outline colour in game): **red** = lava, > 25% water, > 25% unloaded, fit < 30 or a
cut deeper than 10; **yellow** = fill deeper than 3, cut deeper than 4, average fill/cut over 1 block or > 3% water
(needs foundations or terracing); **lime** = fits (trees only count as obstacles to clear).

**Campus integration** (`terrain.apply`, called by the `campus` tool when a survey is loaded): the real campus footprint is
re-placed (rotated with block states turned: facing, axis, side flags, rotation), the platform sits at the chosen level,
and a `foundation` ghost adds, under every platform/tier column that stands above the ground, a stone-brick retaining
wall on the outline and cobblestone pillars every 4 blocks (first block directly on the ground, so the floater guard is
happy), plus 3-wide stone-brick stair ramps from the middle of each side that stands more than 2 above ground. The campus
result gains `site` (origin, rot, platform_y, fill/cut blocks, max fill depth, foundation blocks, stairs, `trees_to_clear`
as `[x,y,z]`) and `site_note` for the model to mention. Ground above the platform is reported as `cut_blocks`, never removed.

**Survey format** (JSON from `world_survey`): `v`, `x0`, `z0`, `step`, `w`, `h` (cell (i,j) = column `x0+i*step`,
`z0+j*step`, standing for the step x step blocks from there), `y` = `h` strings (north to south) of `w` x 2 base-36 chars
= y + 128 (`??` unknown; y is the top solid ground, water cells give the bed), `f` = `h` strings of `w` chars:
`.` land, `w` water, `l` lava, `t` tree (log/leaves above ground), `s` snow, `?` unknown. Plus `ymin ymax ymed water_pct
lava_pct tree_pct snow_pct unknown_pct slope{mean,p90,max} biome ground[] dominant_ground center radius dim`.

## Mod room registry (mods/)

`architect/mods/` has one small file per mod (`mekanism`, `powah`, `bigreactors` = Extreme Reactors, `create`,
`industrialforegoing`), each defining a `ModRoom`: mod id and display name, an explicit whitelist of real block ids
(all with a texture), a one-line room brief, the best-fit style, pad blocks, centrepiece `pieces`, wall machines and
the ghost-rendering limits (multiblocks do not form in a ghost, so rooms show the unformed casing + glass look; animated
blocks are static). Offline check: `python test_mods.py` (every id exists in the block library, has a texture, no
duplicates; needs the git-ignored `knowledge/blocklib.json` built from the ATM10 instance).

- **Room fit-out**: a campus room `mod_room:<theme>` with a registered theme gets 3x3 pads on a 6-grid with a centrepiece
  on each pad and wall machines along the edges (`interiors._mod_room_registered`). `mod_room:ae2` and unregistered
  themes keep the old generic pads (the service port wall is added to every mod room with a plinth).
- **Agent**: when a campus call uses a registered `mod_room:<theme>`, that mod's whitelist is added to the `blocks` tool
  (also `blocks(mod='<theme>')`) with the cost filter bypassed (mod machines have no recipe cost), and the campus result
  carries the room brief. All other blocks still go through the cheap-survival cost filter. `architect.py --generate
  <style> --feature-mod <theme>` asks for that mod as the showpiece wing.
- **Dev client**: ghosts only render mod blocks whose mod is loaded in the client (the dev `run/mods` needs the mod jars).
- Add a mod: copy a file in `mods/`, list its blocks, import it in `mods/__init__.py`, run `test_mods.py`.

## Service infrastructure (services.py)

Mod wings are sized from their machine count (wing key `machines`, default 14 clusters; `services.size_for`: 27..65 x
33..81, odd, area monotonic in clusters). Every style gets the same services, built by `services.py`:

- **Service trench** (3 wide, 2 deep) from the hub under every wing: lanes ME cable (purple), power (red), fluid (light
  blue), grate/glass hatches in the floor, junction blocks (`ae2:interface`, `ae2:energy_acceptor`) where a wing
  branches off. `campus.Site.service_info` routes it (BFS over the hall network; straight paths for the spine, tiers and
  terrace risers); `services.apply` carves it and appends a `services` ghost (meta: paths, junctions, hub, wings).
- **Port wall**: the wall facing the hub, 5-wide bays on a pitch of 6 with a coloured panel and a white glyph
  M (ME interface / pattern provider), P (energy in), F (fluid in/out), I (item in/out), fed from the trench by a riser grate.
- **Ceiling trays**: dark gantry header + beams (chains) with opaque conduit runs over the room, a drop to each machine pad.
- Not done: steampunk surface pipes along the walls.

### What draws in a ghost (rig client test)

- `ae2:cable_glass/covered/smart/dense_smart` are not blocks. Cables are parts of `ae2:cable_bus`, which is **invisible**.
  Draw: interface, pattern_provider, controller (`state=online|offline`, `type=block|column_y`), energy_acceptor,
  drive[facing], molecular_assembler, crafting_unit[formed], crafting_accelerator, crafting_storage, energy_cell,
  io_port. So AE2 cabling is shown with coloured concrete/glass lanes plus real AE2 end blocks.
- Mekanism transmitters (universal_cable, pressurized_tube, mechanical_pipe, logistical_transporter, thermodynamic_conductor)
  draw only as isolated core cubes (no arms): usable as node markers, not connected cables.
- Powah `energy_cable_*` draws connected only with explicit `north/east/south/west/up/down=true|false`; without states it is a dot.
- Create `fluid_pipe` draws connected only with all six explicit direction states; `glass_fluid_pipe[axis]`, `encased_fluid_pipe`
  (states), `copper_casing`, `mechanical_pump[facing]`, `fluid_tank` draw.
- Vanilla fallbacks that draw: `iron_bars` (states for lines), `chain[axis]`, `end_rod`, copper grates, `lightning_rod`,
  `tinted_glass`, `waxed_copper_bulb`. Translucent glass conduits look like torn sheets; trays use opaque concrete.

## Module layout and the mod protocol

- `architect.py`: CLI, system prompt, tools and the agent loop. `mcp_client.py`: `Mcp` JSON-RPC client, `Guides`, `hold_focus` / `release_focus`, `emit_event`. `views.py`: `view()`, `ref_thumb()`, `camera_pose()` and `prune_old_images()`. `terrain.py`: survey, site picking, foundations.
- Vision context pruning: before every model call only the newest `ARCHITECT_KEEP_IMAGES` (default 2) tool results keep their images; older ones keep their text plus `[earlier view image pruned to save context]`. Reference images you attach to a request are never pruned, and `sessions/<name>/messages.json` keeps everything.
- `--ndjson` (or `ARCHITECT_NDJSON=1`): stdout carries one JSON object per line for the mod: `{"event":"site","summary":...}`, `tool` (`name`, `args`), `cost` (`usd`, `tokens_in`, `tokens_out`, `secs`), `reply` (`text`), `error` (`message`), `done` (`ok`, `usd`). Without the flag only the legacy `SITE ` / `REPLY ` / `cost ~$` lines are printed, so older mods keep working.
