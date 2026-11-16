# MC MCP

A NeoForge 1.21.1 mod that runs an [MCP](https://modelcontextprotocol.io) server inside Minecraft, on
the client and on dedicated servers, so Claude (or any MCP client) can profile and debug a modpack
directly: FPS, TPS, chunks, entities, heap/GC, mixins, spark profiles, and a chat bridge to talk to
Claude from in game.

- Transport: streamable HTTP, plain JSON responses (no SSE). `POST /mcp`.
- Client: `http://127.0.0.1:47860/mcp`, localhost only. In singleplayer it also reaches the
  integrated server (tick stats, server world state, spark `server` side, teleports).
- Dedicated server: `http://127.0.0.1:47870/mcp`, bearer token always required (generated into the
  config on first start), and only loopback/LAN client addresses that match `allowlist` are accepted.
  Set `bind = "0.0.0.0"` (or the LAN IP) to reach it from another machine.
- Read-only by default. `[features] actions = true` adds the `[action]` tools; `actionsCommands`
  adds `run_command` on top.
- spark is optional. Without it the `spark_*` tools say so; nothing else changes.

## Connect Claude Code

```bash
claude mcp add --transport http minecraft http://127.0.0.1:47860/mcp
```

Server (token from `config/mcmcp-common.toml`, `[server] token`):

```bash
claude mcp add --transport http minecraft-server http://<server-ip>:47870/mcp --header "Authorization: Bearer <token>"
```

## Tools

| Tool | Side | What it returns |
|---|---|---|
| `status` | both | versions, mod count, world/player, pause/screen, enabled tool groups, tool list |
| `frame_stats` | client | FPS avg, 1% / 0.1% low, frame ms avg/p50/p95/p99/worst, frames over 50/100 ms, for the last N s (or `fresh=true`: the next N s), plus render settings |
| `measure` | client | waits `settle_s`, then frame stats + integrated-server ticks + GC pauses + heap over `seconds` |
| `client_world_state` | client | loaded chunks, rendered sections (F3 `C:`), entities / block entities / ticking block entities by type, particles, distances, GPU/CPU |
| `tick_stats` | both* | TPS, MSPT avg/p95/max (last 100 ticks), per dimension |
| `server_world_state` | both* | per dimension: loaded chunks, entities, block entities, ticking block entities by type; view/simulation distance |
| `jvm_state` | both | heap, stop-the-world GC pauses vs concurrent cycles in a window, recent GC events, CPU, threads; `details` adds pools, collectors, JVM args |
| `mixins` | both | every mixin config: applied / pending (target not loaded yet) / skipped (target missing, plugin said no, or failed). `status=skipped`, `filter=<mod>` |
| `mods` | both | installed mods + versions |
| `config_list` | both | a mod's NeoForge config values with defaults and comments |
| `spark_start` / `spark_stop` | both | starts spark (`side` client = `sparkc`, server = `spark`, `threads='*'` default); stop saves locally (no upload) and returns JSON: threads, mods by self/inclusive time, hot methods with callers, optional call tree (`tree`, `min_pct`, `max_depth`). Idle time (park/sleep/IO wait/FPS limiter wait) is excluded unless `include_idle` |
| `spark_analyze` | both | re-analyze the last (or a saved) profile with another thread filter or a tree |
| `spark_status` | both | installed? running? saved profiles |
| `chat_send` | both | `[Claude] …` lines to the local player (client) or to one player (server); never broadcast |
| `chat_read` | both | recent chat box lines (client: chat, system, command output) |
| `chat_poll` / `chat_wait` | both | player messages starting with the prefix (default `@claude`); they are intercepted and never reach server chat. `chat_wait` blocks until one arrives |
| `config_set` | both, action | change + save one NeoForge config value (fires the mod's reload event) |
| `spot_save` / `spot_list` / `teleport` | both*, action | named positions in `config/mcmcp/spots.json`; teleport across dimensions |
| `video_get` / `video_set` | client (set = action) | any `Options` value: renderDistance, simulationDistance, enableVsync, framerateLimit, graphicsMode, … |
| `chat_selftest` | client, action | posts `@claude <text>` through NeoForge's chat hook to test the bridge |
| `run_command` | both*, actionsCommands | run a command at op level as the player, returns its output |
| `block_info` | both* | blockstate, block id, block entity type, optional NBT at x/y/z (server-side truth) |
| `screenshot` | client, action | save a PNG of the current frame under `<gameDir>/screenshots/`, returns its path |
| `screen` | client | open screen class/title, GUI size/scale, container geometry, widgets |
| `click` | client, action | click GUI-scaled x/y in the open screen (fires `ScreenEvent.MouseButtonPressed.Pre`) |
| `key` | client, action | send a key press to the open screen |
| `close_screen` | client, action | close the current screen without the mouse |
| `look` / `look_at` | client, action | set the client player's yaw/pitch, or aim at a world position |
| `crosshair` | client | what the crosshair is actually on (block pos/face or entity) |
| `hold_key` | client, action | hold/release a key (shift, sprint/ctrl, use, attack, jump, movement) or any KeyMapping by name, including controller-bound ones |
| `click_world` | client, action | real left/right click through `startAttack`/`useItemOn`; refreshes the pick first |
| `hotbar` | client, action | select hotbar slot 0–8 |
| `chunk_rebuild` | client, action | rebuild all chunk meshes (F3+A) |
| `ghost_set` | client | create or edit a ghost build (see-through blocks drawn only on this client, never placed): palette, boxes, blocks; replace or merge |
| `ghost_list` / `ghost_info` | client | all ghosts, or one ghost's bounds and palette counts |
| `ghost_move` | client | move, shift or rotate a ghost (stairs, logs etc. turn with it) |
| `ghost_show` | client | show/hide and opacity per ghost; global `xray` (draw over terrain), `solid` (full colour), `hud` |
| `ghost_clear` | client | delete one ghost, a `prefix/`, or all |
| `ghost_export` | client | save ghosts as `.litematic` (Litematica), `.schem` or `.nbt` under `<gameDir>/schematics/` |
| `registry_blocks` / `block_describe` | client | blocks that exist in this pack (by mod id or substring, optional state properties), or one block in detail |

\* on a client these need a singleplayer world (they use the integrated server).

A typical A/B test: `spot_save` → `measure` → `config_set` or `video_set` → `teleport` back → `measure`.

## Chat bridge and waking Claude

Type `@claude why is my FPS low?` in game. The message is cancelled before it is sent, shown back to
you as `[You → Claude] …`, and queued for `chat_poll` / `chat_wait`. Claude answers with `chat_send`.

Pushing a message *into* an idle Claude session: Claude Code only supports this through its
research-preview **channels**, which need a stdio MCP server, CLI only (not documented for the
desktop app). `channel/mc_channel.py` is that bridge (stdlib Python): it long-polls `chat_wait`,
emits `notifications/claude/channel` per player message, and offers a `reply` tool.

```bash
claude mcp add minecraft-chat -- python <path-to>/mc-mcp/channel/mc_channel.py
MCP_PROTOCOL_NEGOTIATION=legacy claude --dangerously-load-development-channels server:minecraft-chat
```

Without channels, Claude can hold a conversation by calling `chat_wait` in a loop while you play.

## Config (`config/mcmcp-common.toml`)

`[client]` enabled / bind / port / token · `[server]` enabled / bind / port / token / allowlist ·
`[features]` spark / mixins / chatBridge / chatPrefix / actions / actionsCommands.
`chatBridge = false` also skips the chat capture mixin (read at startup).

## Build

```bat
build.bat build
```

Uses the JDK in `toolchain\` or `..\foxs-tweaks\toolchain\`. Jar: `build/libs/mcmcp-<version>+neoforge-1.21.1.jar`.
Dev runs: `gradlew runServer`, `gradlew runClient -PquickPlay=<world>`.

## Design notes

- No compile-time dependency on any other mod. spark is driven through its own commands
  (`profiler start/stop --save-to-file`) and its saved protobuf is decoded with spark's own classes
  by reflection.
- One mixin (`ChatComponent#addMessage` capture for `chat_read`), optional (`required: false`,
  `defaultRequire 0`), switchable by config through a mixin plugin.
- Game state is read on the game thread (`GameThread.call`, 10–20 s timeout) so tools never block
  rendering; blocking tools (`chat_wait`, `measure`, `spark_stop`) wait on the HTTP worker thread.
- No native dialogs anywhere.
