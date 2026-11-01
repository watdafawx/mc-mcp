#!/usr/bin/env python3
"""
Experimental: a Claude Code *channel* for the Minecraft chat bridge.

Claude Code only lets a stdio MCP server push a prompt into a running session (research-preview
"channels"). This shim is that stdio server. It long-polls the mod's `chat_wait` tool over HTTP and
turns every "@claude ..." message the player types into a `notifications/claude/channel` event, so
an idle Claude Code session wakes up and answers. It also offers one tool, `reply`, which shows a
[Claude] line in the player's chat (the mod's `chat_send`).

Stdlib only. Usage (CLI only; the desktop app does not document channels):

    claude mcp add minecraft-chat -- python X:/Dev/Minecraft/mc-mcp/channel/mc_channel.py --url http://127.0.0.1:47860/mcp
    MCP_PROTOCOL_NEGOTIATION=legacy claude --dangerously-load-development-channels server:minecraft-chat

Add --token <t> for a server whose MCP needs a bearer token.
"""
import argparse
import json
import sys
import threading
import time
import urllib.request

out_lock = threading.Lock()


def send(msg):
    with out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def log(*a):
    print("[mc_channel]", *a, file=sys.stderr, flush=True)


class Mod:
    def __init__(self, url, token):
        self.url, self.token, self.n = url, token, 0

    def call(self, tool, args, timeout):
        self.n += 1
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        body = {"jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": {"name": tool, "arguments": args}}
        req = urllib.request.Request(self.url, json.dumps(body).encode(), h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read())["result"]
        text = res["content"][0]["text"]
        if res.get("isError"):
            raise RuntimeError(text)
        return json.loads(text)


def pump(mod):
    """Forward player messages as channel events, forever."""
    while True:
        try:
            got = mod.call("chat_wait", {"timeout_s": 300}, timeout=330)
            for m in got.get("messages", []):
                send({"jsonrpc": "2.0", "method": "notifications/claude/channel",
                      "params": {"content": m["text"], "meta": {"player": m.get("player", "player"), "source_game": "minecraft"}}})
        except Exception as e:  # game not running, world not loaded, ...
            log("waiting for the game:", e)
            time.sleep(5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:47860/mcp")
    ap.add_argument("--token", default="")
    a = ap.parse_args()
    mod = Mod(a.url, a.token)
    started = False
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        method, rid = req.get("method"), req.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
                "capabilities": {"experimental": {"claude/channel": {}}, "tools": {}},
                "serverInfo": {"name": "minecraft-chat", "version": "0.1.0"},
                "instructions": "Messages from a Minecraft player arrive as <channel> events (they typed '@claude ...' in game chat). "
                                "Answer with the `reply` tool so it shows in their chat; keep replies short (a few lines). "
                                "The `minecraft` MCP server, if connected, has the profiling tools."}})
        elif method == "notifications/initialized":
            if not started:
                started = True
                threading.Thread(target=pump, args=(mod,), daemon=True).start()
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{
                "name": "reply", "description": "Show a [Claude] message in the Minecraft player's chat.",
                "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}]}})
        elif method == "tools/call":
            try:
                mod.call("chat_send", {"text": req["params"]["arguments"]["text"]}, timeout=20)
                result = {"content": [{"type": "text", "text": "shown"}], "isError": False}
            except Exception as e:
                result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
            send({"jsonrpc": "2.0", "id": rid, "result": result})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif rid is not None:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}})


if __name__ == "__main__":
    main()
