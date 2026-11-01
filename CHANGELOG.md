# Changelog

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
