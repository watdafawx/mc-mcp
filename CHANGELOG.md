# Changelog

## Unreleased

- Architect tooling only, no Java change. Create round 5: mod facade signage now also runs on the spine / `_legacy_build` path, with real cogwheel emblems on the doors; mod-room scale changes; `fix_pipes` tidies pipe runs (`floaters.py`); `test_mods.py` extended. Honest status: the Create room reads about 8/10 in judged shots. The facade panel contrast and the in-room gear visibility are still weak.

- Ghosts now draw block-entity-rendered blocks: Create shafts, cogwheels, belts, water wheels, flywheels, and vanilla chest, sign, banner, shulker box, bell and enchanting table. New `ghost/GhostBlockEntities.java` runs the block's renderer on a client-only dummy block entity and bakes the quads into the ghost mesh (other texture sheets become extra buffers, with the same tint, solid and xray handling). New config `ghostRender.blockEntities` (default true); off gives the old models-only behaviour. For Create, the Flywheel backend is switched off by reflection during a bake and restored after, and if that fails the ghost falls back to the Ponder virtual model. Parts are static (no animation). No compile-time dependency on Create.
- Architect: the Create room uses real kinetic blocks (cogwheels, large cogwheels, water wheel, belt) instead of fake stand-ins; the fakes stay as a fallback.

- Architect tooling only, no Java change. Create rooms no longer place kinetic blocks that ghosts cannot draw (shaft, cogwheel, large_cogwheel, belt, water wheels, flywheel, fluid_pipe are drawn by block-entity renderers, so their ghosts are invisible). Instead they use fake stand-ins: cog discs (new `mods/shapes.py`), gear trains, a belt strip between casing pulleys and a water wheel, built from dark oak, andesite alloy and brass blocks. This is a fallback, not real Create parts: in judged shots the discs still read as brown plates with brass hubs rather than cogs. Every mod wing also gets facade signage (colour band under the roofline and two door emblems, `mods/signs.py`); only the Create signage was checked in a screenshot. `test_mods.py` checks for both.
- Architect tooling only, no Java change. Mod wing is now the biggest wing (size x, one tall floor, grid windows), mod rooms get a contrasting deck and 7x7 plinths per cluster (`group` and `gear` piece kinds), and the judge writes a `_modroom` sheet (facade, overhead, low front, low side) with the interior cut forced onto the mod room. Mekanism and Powah read better; Create kinetics (cogwheels, shafts) still do not show in ghosts and are pending.
- Architect tooling only, no Java change. New mod registry (`architect/mods/`) with room kits for Mekanism, Powah, Extreme Reactors, Create and Industrial Foregoing, wired into `architect.py`, `blocklib.py` and `interiors.py` (+ offline `test_mods.py`, README section). Honest status: the mod rooms exist and place real mod blocks, but they do not read well yet in judged screenshots (small, low-contrast, multiblocks do not form in ghosts).
- Architect tooling only (v22), no Java change. Gothic wings get light stone trim lines on the roof surface (eave row and every 4th height band), so roofs are grey-and-black instead of all black. Gothic hub gets a glazed lantern drum with stepped cap, spire and corner pinnacles; the tower gets a stepped spire with corner pinnacles (`_gothic_roof`, `_gothic_crowns` in `campus.py`). The tower crown is not yet checked in a screenshot.
- Steampunk wall pipes are now thicker runs (3 high x 2 deep, with flange collars, valves, brackets and risers). Colour contrast is still pending: the pipes are teal on teal and barely stand out from the walls.
- Judge tooling (`architect/judge/judge2.py`): new per-wing "massing front-on" close-ups on the detail sheet, and the interior camera sits further back (span*1.3+14, cap 72) so rooms are not clipped.

## 0.5.0

- New `/ghost suggest [look|here|x z] [r=N] [nooverlay]` command and `ghost_suggest` / `ghost_suggest_status` tools: look at an area and get 3-6 short improvement suggestions (flat roof, unlit walls, one-block palette...) from one Claude Haiku call over a survey of the real blocks, plus an optional `suggest` ghost with the proposed additions (gable roof, lanterns, corner posts; cheap survival blocks, clear with `/ghost clear suggest`). Own cost cap `ghostGenerate.suggestCostCapUsd` (default $0.10), 5 min timeout. New `WorldSurvey.region` scan (palette counts, buildings, roof flatness, lights per wall, ores/water/lava), `architect/suggest.py` (+ offline `test_suggest.py`), `usage_cost()` hook in `architect.py`. Needs the same `architect/.env` and venv as `/ghost generate`.
- Architect tooling only (v21), no Java change. Gothic wings get steep roofs only (gable_steep/hip_steep) in dark lead-look materials with ridge cresting, spirelets and eave-corner pins (`_gothic_roof` in `campus.py`); hextech and station_white wings get per-wing massing variety (colonnade, corner turrets, cornice and oriel; fins, module pods, corner towers); the judge interior cut aims at the room's wall centre (`judge/room_pick.py`).

## 0.4.1

- Architect/Python tooling changes only (v19, v20). Mod Java code is unchanged since 0.4.0.

- Architect roof detail: steampunk slope roofs get copper seams, dormers, ridge with lightning rods and chimneys; solarpunk flat wings get a rooftop garden deck (planter hedge, skylight, pergola, beds). Fix: floater guard now forgets cells a merge-mode air box/block erased, so later parts no longer count phantom blocks as support and hang in the air. Offline test: `python architect/test_floaters.py`.
- Architect gothic wing variety: each wing gets its own facade rhythm (flying buttresses with blind tracery arches, stepped piers with staggered pinnacles, tall buttresses with rose windows) via `_gothic_variety` in `campus.py`.
- Architect judge tooling in `architect/judge/` (`judge2.py`, `room_pick.py`, `judge_call.py`): interior cut now aims at a real built room (ceiling-light cluster with a floor below) found from the replayed campus cells instead of a fixed ceiling layer.

## 0.4.0

- World-aware base generation. New `world_survey` tool: compact terrain survey of the loaded client world (heightmap grid in base-36 rows, flags for water/lava/trees/snow/unloaded, slope stats, biome, dominant ground block). Never loads chunks.
- `ghost_generate` now surveys first (`target` look/here/x,z, `fit` default true, `use_area`) and passes the survey to the architect (`--survey`). New `architect/site.py` picks the best campus rectangle (flatness, water, trees, unknown, slope; 90-degree rotation; smaller layout and fewer wings when tight), puts the campus at its own ground level, adds stone-brick foundation walls, support pillars and access stairs where the ground drops away, and reports fill/cut and the trees to clear. Nothing is removed from the world. Without a survey the architect behaves exactly as before.
- `/ghost area <style> [look|here|x z]` and `ghost_area` tool: preview the site as a thin outline ghost with corner posts (lime = fits, yellow = needs foundations, red = blocked/water) and one chat line, with no LLM call. `/ghost area move|rotate|clear`, `/ghost generate confirm` (or `/ghost generate <style>` right after a preview) builds in the previewed area. Tab completion for all of it. `/ghost generate <style>` with no coordinates now uses the looked-at block; new words `here` and `nofit`.
- Fix: area-preview ghosts render in their own colours (no blue xray tint), via the `kind=area` tag in `GhostRenderer`.
- Docs: README tables, `architect/README.md` (site picker, survey format, fit colours). Offline tests: `python architect/test_site.py`.
- Screenshots of the area preview in `docs/ghost-area-shots/`, used as captions in the README.

## 0.3.1

- Architect refresh (in the repo's `architect/` folder, not in the jar): per-wing facades and roofs in campus layouts, gothic porch and spire, hextech palette and airship dock, steampunk gears and pipes, station radar dish, solarpunk roof pond and waterfall, footprint guard and `room_origins` retargeting for room ghosts.
- Docs: `docs/ARCHITECT.md` and the README gallery use the v17 judge sheets, with v6 vs v17 comparisons, what changed, and a list of what is not verified.
- No mod behaviour change; no Java changes.

## 0.3.0

- `ghost_import` tool and `/ghost import <name> [x y z]` command (tab completion lists schematics): load a `.schem` (Sponge v2/v3) or vanilla `.nbt` as a ghost; bare names are searched in `config/shapewright/schematics`, `schematics`, `config/worldedit/schematics`, `world/generated/minecraft/structures`.
- `ghost_info` returns `block_list` `[{x,y,z,state}]` with full block-state syntax (`blocks=false` to omit, `limit`, `block_list_truncated`).
- `GhostApi` (`isAvailable()`, `set(id, blocks, origin)`): in-process, thread-safe entry point so other mods can show ghosts without mc-mcp depending on them.
- `run_client_command` dev tool (config `features.devClientCommands`, default false): runs client commands through the dispatcher, with `suggest=true` for tab completions.
- `/ghost hide|show|list|clear|generate` client commands, with tab completion. `hide`/`show`/`clear` share their code with `ghost_show` / `ghost_clear`.
- `ghost_generate` / `ghost_generate_status`: run the LLM architect asynchronously (one job at a time, cost-capped by `ghostGenerate.costCapUsd`, default $0.15). The API key stays in `architect/.env` and is never read by the mod.
- Architect campus and judge improvements (layouts, massing kits, floater guard, judge sheets) live in the repo's `architect/` folder, not in the jar. See `docs/ARCHITECT.md`.

## 0.2.1

- `video_get` / `video_set` also cover plain boolean options such as `pauseOnLostFocus`, so a tool can stop the pause menu from opening while the game window is in the background.
- `video_set` takes `save=false` to change an option only until the game restarts (options.txt untouched), and returns the old value for restoring.

## 0.2.0

- Ghost builds: `ghost_set`, `ghost_list`, `ghost_info`, `ghost_move`, `ghost_show`, `ghost_clear`, `ghost_export`. See-through blocks drawn only on this client, never placed in the world. Specs use a palette plus boxes (fill / hollow / walls / frame) and single blocks; edits merge in place.
- `ghost_show` view modes: `xray` draws ghosts over terrain, `solid` draws them in full colour, `hud` hides the HUD for clean screenshots.
- `ghost_export` saves ghosts as `.litematic`, `.schem` (Sponge v2) or vanilla `.nbt`.
- `registry_blocks` and `block_describe`: list the blocks that exist in the pack (by mod id or substring, with state properties) and describe one block.
- Client tools for driving the game: `block_info`, `screenshot`, `screen`, `click`, `key`, `close_screen`, `look` / `look_at`, `crosshair`, `hold_key`, `click_world`, `hotbar`, `chunk_rebuild`.

## 0.1.1

- Author is now watdafawx (was mtop); Java packages moved from dev.mtop to dev.watdafawx. No gameplay changes.

## 0.1.0

Initial release.

- In-game MCP server (streamable HTTP, `POST /mcp`) on the client (`127.0.0.1:47860`) and on dedicated servers (`47870`, bearer token + address allowlist).
- Read-only by default; `[features] actions` / `actionsCommands` unlock action tools and `run_command`.
- Performance tools: `frame_stats`, `measure`, `tick_stats`, `client_world_state`, `server_world_state`, `jvm_state` (heap, GC pauses, CPU, threads).
- Inspection: `status`, `mods`, `mixins` (applied / pending / skipped), `config_list`.
- Optional spark integration: `spark_start` / `spark_stop` / `spark_analyze` / `spark_status`, with profiles decoded to JSON (threads, mods, hot methods, call tree).
- Chat bridge: `@claude` messages are intercepted and queued for `chat_poll` / `chat_wait`; replies via `chat_send`; `chat_read` for recent chat lines.
- Actions: `config_set`, `video_get` / `video_set`, `spot_save` / `spot_list` / `teleport`, `chat_selftest`.
- `channel/mc_channel.py`: stdio bridge that pushes in-game messages into a Claude Code session via channels.
