# Changelog

## Unreleased

- **Architect refactor**: `site.py` renamed `terrain.py` (it shadowed the stdlib `site`; the importlib hacks are gone, tests are `test_terrain.py`). `architect.py` split: `mcp_client.py` (`Mcp`, `Guides`, focus guard, `emit_event`) and `views.py` (`view`, `ref_thumb`, `camera_pose`, `prune_old_images`).
- **Vision context pruning**: only the newest 2 tool results keep their images in each model call (`ARCHITECT_KEEP_IMAGES`); older ones become a short text placeholder. Reference images and `messages.json` are untouched.
- **NDJSON IPC**: `architect.py --ndjson` (or `ARCHITECT_NDJSON=1`) prints JSON event lines (`site`, `tool`, `cost`, `reply`, `error`, `done`); `GhostGenerate` passes it and parses them, with the old `SITE ` / `REPLY ` / `cost ~$` lines as fallback.

## 0.7.1 (2026-11-23)

- **One-click Ghost Undo**: 10-step in-memory undo stack in `GhostStore` (`snapshot`, `canUndo`, `undo`), auto-snapshot before every `Iterate` run in `GhostGenerate`, `/ghost undo` command, and `Undo` button on the Ghost Builder GUI (`Undo | Export | Clear | Ghosts`).
- **Architect upgrades**:
  - 6 new shape generators in `shapes.py` (`square_tower` with machicolations, `dormer`, `buttress_row`, `spiral_stair`, `arch_bridge`/`bridge`, `wall_segment`) + smoothed crow-stepped gables and small domes (`r <= 5`).
  - `postcheck.py`: proportion sanity warnings wired into `view()` + automatic local hillside foundations (`auto_foundation`) on `--prompt` builds (zero LLM tokens).
  - `llm_client.py`: stdlib-only OpenAI-compatible LLM backend (DeepSeek API, OpenRouter, Ollama `/v1`, LM Studio, vLLM) alongside Anthropic.
  - `services.py` & prompt: live-tested AE2/Mekanism/Powah/Create ghost block IDs in `SYSTEM` prompt; Gothic port-wall bay packer (4–6 bays) + multi-trunk ceiling trays (`drops == pads`).
  - Mods batch 3: room kits for Modern Industrialization, Immersive Engineering, Draconic Evolution, EvilCraft, and Functional Storage (`architect/mods/`).
- **CI**: bumped `actions/checkout@v5` and `actions/setup-java@v5` in `.github/workflows/release.yml`.

## 0.7.0 (2026-11-23)

- **Prompt / Image mode in Ghost Builder GUI (`/ghost gui`, `G`)**: switch between **Prompt / Image** (default) and **Base Style**. Type any free-text description for a single structure or component, attach an image path/URL or toggle **Clip: on** (reads clipboard image directly), optionally toggle **3D: on** (forces Hunyuan3D photo→voxel via `image_to_3d`), pick Position + Kit, then **Generate** (new session) or **Iterate** (continues latest session in place to refine the ghost).
- **One-click Export**: **Export** button in `GhostScreen` and `/ghost export [name] [litematic|schem|nbt]` save the latest session's ghosts (or all ghosts) directly to `<gameDir>/schematics/`.
- **FreeCam toggle (`FreeCam: on/off` / `/ghost freecam`)**: client-side detached screenshot camera (`GhostCamera` + `CameraMixin` + `ghost_camera` MCP tool) so `architect.py`'s `view()` can orbit and inspect builds without `/gamemode spectator`, `/tp`, or cheats, and never moves the player.
- **New client commands & MCP tools**: `/ghost prompt <text>`, `/ghost ref <clip|url|path> [text]`, `/ghost ref3d <clip|url|path> [text]`, `/ghost iterate <change>`, `/ghost export [name] [format]`, `/ghost freecam [on|off]`, plus `ghost_prompt` and `ghost_camera` MCP tools.
- **Architect improvements**: component-first `--prompt` wrapper (skips full `campus` unless requested, grounds at exact looked-at block `y+1`), `--iterate`, `--force-3d`, `--freecam`, in-game chat `REPLY` summary echo, and **user reference compare-and-fix** in `view()` (attaches the user's own reference image side-by-side with the screenshot).

## 0.6.0 (2026-11-22)

- Ghost builder screen (`/ghost gui`, or the `G` keybind under Controls → MC MCP): a vanilla `Screen` with a style picker, position (look-at / here / coordinates), kit, layout and fit, plus Generate / Stop / Clear, a show/hide toggle, the xray/solid mode and an Idle / Generating... / Done / Stopped / Error status line. It runs the same `/ghost generate` code path and does not pause the game. New `ghost/GhostScreen.java`, `assets/mcmcp/lang/en_us.json`.
- New `/ghost stop`: cancels the running generate job, kills the architect process (and its children) on a worker thread and marks the job `stopped`, so a new job can start immediately. `ghost_generate_status` reports `stopped` too.
- Clearer `/ghost generate` errors: an unplaceable word now lists the valid styles, kits and layouts, gives three examples, says that the words "kit" and "layout" are not typed, and points at the architect CLI (`python architect.py -s mine "<description>"`) or `@claude <text>` in chat for a free-text description. An unknown kit fails with the same message instead of being accepted.
- Architect tooling only (no Java change). Mod rooms and wings: each mod wing is now sized from its machine count, and every style gets service infrastructure: a 3-wide, 2-deep trench from the hub under each wing (ME / power / fluid lanes, hatches, junction blocks), a port wall with labelled M/P/F/I bays facing the hub, and ceiling cable trays with drops to the machines (`architect/services.py`, `test_services.py`). Honest status: AE2 cables are invisible in a ghost, so ME runs are shown as coloured lanes with real AE2 end blocks; Mekanism cables only draw as core cubes; steampunk surface pipes not done. Ghost-render findings are in the architect README.

## 0.5.1

- Fix: ghosts no longer wipe the depth buffer in xray. After `/ghost generate` (or any xray view), other mods' particles (Ars Nouveau and others) drew through ground and walls, because xray cleared the whole depth buffer. Ghosts now draw with depth test and depth writes off and restore LEQUAL / depth mask on, so later stages (particles, weather, hand) keep terrain depth. Side effect: xray ghosts no longer hide their own back faces.
- New `/ghost xray [on|off]` and `/ghost solid [on|off]` commands (toggle without argument, tab completion, chat feedback). The architect restores the view modes (xray, solid, HUD) after a generate / suggest run instead of leaving xray on.
- Ghosts now draw block-entity-rendered blocks: Create shafts, cogwheels, belts, water wheels, flywheels, and vanilla chest, sign, banner, shulker box, bell and enchanting table. New `ghost/GhostBlockEntities.java` runs the block's renderer on a client-only dummy block entity and bakes the quads into the ghost mesh (other texture sheets become extra buffers, with the same tint, solid and xray handling). New config `ghostRender.blockEntities` (default true); off gives the old models-only behaviour. For Create, the Flywheel backend is switched off by reflection during a bake and restored after; if that fails the ghost falls back to the Ponder virtual model. Parts are static (no animation). No compile-time dependency on Create.
- Architect mod registry (`architect/mods/`): room kits for Mekanism, Powah, Extreme Reactors, Create, Industrial Foregoing, Ars Nouveau, Occultism, Mystical Agriculture, Productive Bees and Ender IO, with facade signage, real mod blocks, and a mod wing that is the biggest wing of the campus. The featured registry wing is protected from clear and replace during a run. Honest status: the rooms are early. Judged shots read about 8/10 for Create, 7/10 for Occultism and Mystical Agriculture, 5/10 for Productive Bees and Ender IO, and Mekanism and Powah read better than before but are not finished. Ars Nouveau was 3/10 before the wing protection and needs a rerun. The Create room uses real kinetic blocks, with fake stand-ins as a fallback.
- Architect v22: gothic roofs get light stone trim lines, a glazed lantern drum with spire and pinnacles on the hub, and a stepped spire on the tower (not yet checked in a screenshot). Steampunk wall pipes are thicker runs with flanges, valves and brackets. The judge adds per-wing front-on close-ups and moves the interior camera further back.
- `/ghost generate` and `/ghost suggest` need the architect folder and its Python venv on the same machine as the game; point `ghostGenerate.architectDir` at it.

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
