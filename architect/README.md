# Architect

LLM architect: designs themed bases as ghost builds in a running Minecraft client through mc-mcp. See `architect.py`
(docstring) for the CLI. In game it is started with `/ghost generate <style> [look|here|x z] [kit] [layout]` or the MCP tools
`ghost_generate` / `ghost_generate_status`.

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
  never touches the key. It loads `site.py` by path like `architect.py` (the name shadows the stdlib `site`).
- Offline test (fake client, canned survey, no API): `python test_suggest.py`.

## World-aware sites (site.py)

`ghost_generate` / `/ghost generate` survey the client world first (`world_survey`), write the JSON to a temp file and run
`architect.py --survey <file> --near x,z` (plus `--site-rect x,z,w,d,rot` for a previewed `/ghost area`). No survey = the
old flat behaviour, unchanged (so batch scripts keep working). The LLM only sees a one-line summary (platform height,
foundations, trees, layout and wing limit), never the grid, so a build stays around $0.03-0.07.

`site.py` is pure python and deterministic (no Minecraft, no API). It shares its name with the stdlib `site`, so
`architect.py` and `test_site.py` load it by path (`importlib`); run it as a script:

    python site.py plan --survey s.json --style hextech --near x,z     # best layout/wings/rectangle (JSON)
    python site.py eval --survey s.json --x 10 --z 20 --w 96 --d 80 [--rot 90]   # score one rectangle (/ghost area move|rotate)
    python site.py demo hill|slope|cliff|forest|shoreline|unknown|flat   # fake surveys
    python test_site.py                                                # offline tests

**Picker.** Every candidate rectangle of the campus footprint (measured per layout and wing count, 88x85 .. 235x170),
also turned 90 degrees, is scored in O(1) from prefix sums: water, lava, trees, unknown cells, height spread, slope,
earthwork (fill + 1.5 x cut) and a small distance penalty to the aimed spot. Layout/wing configs are tried from the most
ambitious (style layout, 5 wings) to the smallest (spine, 1 wing); utility = fit + 4 per wing + layout bonus - 60 if red.
The platform level is the 60% quantile of the ground (fill is cheaper than cut: ghosts never remove blocks).

**Fit colours** (`class` in the result, outline colour in game): **red** = lava, > 25% water, > 25% unloaded, fit < 30 or a
cut deeper than 10; **yellow** = fill deeper than 3, cut deeper than 4, average fill/cut over 1 block or > 3% water
(needs foundations or terracing); **lime** = fits (trees only count as obstacles to clear).

**Campus integration** (`site.apply`, called by the `campus` tool when a survey is loaded): the real campus footprint is
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
