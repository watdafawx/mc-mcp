# Changelog

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
