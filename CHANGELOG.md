# Changelog

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
