# Architect

LLM architect: designs themed bases as ghost builds in a running Minecraft client through mc-mcp. See `architect.py`
(docstring) for the CLI. In game it is started with `/ghost generate <style> [x z] [kit] [layout]` or the MCP tools
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
