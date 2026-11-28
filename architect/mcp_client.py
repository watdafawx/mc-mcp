"""mc-mcp client pieces of the architect: the JSON-RPC `Mcp` client, the mod-guide index, the pauseOnLostFocus guard
and the structured NDJSON event channel the mod reads (no `anthropic` import, so tests can load it)."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import zipfile
from pathlib import Path

import floaters

HERE = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------------------- NDJSON events

_NDJSON: bool | None = None  # None = decide from ARCHITECT_NDJSON at call time
EVENTS = ("site", "tool", "cost", "reply", "error", "done")


def set_ndjson(on: bool | None) -> None:
    """--ndjson switch (True/False), or None to fall back to the ARCHITECT_NDJSON environment variable."""
    global _NDJSON
    _NDJSON = on


def ndjson_enabled() -> bool:
    if _NDJSON is not None:
        return _NDJSON
    return os.environ.get("ARCHITECT_NDJSON", "").strip().lower() in ("1", "true", "yes", "on")


def format_event(event_type: str, **fields) -> str:
    """One compact JSON line: {"event": <type>, ...fields}. No newline inside, non-ASCII kept."""
    return json.dumps({"event": event_type, **fields}, ensure_ascii=False, separators=(",", ":"), default=str)


def emit_event(event_type: str, **fields) -> bool:
    """Writes one NDJSON line to stdout (the mod parses it) when --ndjson / ARCHITECT_NDJSON=1; otherwise does nothing
    and the legacy human lines (SITE / REPLY / cost ~$) stay the only protocol. Returns True when a line was written."""
    if not ndjson_enabled():
        return False
    print(format_event(event_type, **fields), flush=True)
    return True


# --------------------------------------------------------------------------------------------- mc-mcp

class Mcp:
    def __init__(self, url: str):
        self.url = url
        self.n = 0
        self.nogold = False  # hextech: swap gold/yellow blocks in every ghost_set for quartz/purple/cyan
        self.swapped = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "architect", "version": "1"}})

    def _rpc(self, method: str, params: dict) -> dict:
        self.n += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if os.environ.get("MCMCP_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["MCMCP_TOKEN"]
        req = urllib.request.Request(self.url, body, headers)
        with urllib.request.urlopen(req, timeout=600) as r:
            msg = json.loads(r.read())
        if "error" in msg:
            raise RuntimeError(msg["error"].get("message", str(msg["error"])))
        return msg["result"]

    def tools(self) -> list[dict]:
        return self._rpc("tools/list", {})["tools"]

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        if name == "ghost_set":  # v26: explicit fluid_pipe connection states (the default all-true state draws nothing)
            args, n = floaters.fix_pipes(args)
            if n:
                print(f"  [pipes] set explicit connections on {n} fluid_pipe entries in ghost_set {args.get('id')}", flush=True)
        if name == "ghost_set" and self.nogold:
            args, n = floaters.swap_gold(args)
            if n:
                self.swapped += n
                print(f"  [no-gold] swapped {n} gold/yellow entries in ghost_set {args.get('id')}", flush=True)
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return text, bool(res.get("isError"))

    def json(self, name: str, args: dict) -> dict:
        text, err = self.call(name, args)
        if err:
            raise RuntimeError(f"{name}: {text}")
        return json.loads(text)


# ----------------------------------------------------------------------------------------- mod guides

class Guides:
    """Searchable index of in-game guide pages from the pack's jars: AE2-style ae2guide pages (AE2, ExtendedAE,
    AdvancedAE, MEGA, ...) and Patchouli books (English)."""

    def __init__(self, mods: Path, cache: Path):
        self.pages: list[dict] = []
        if cache.exists() and mods.exists() and cache.stat().st_mtime > mods.stat().st_mtime:
            self.pages = json.loads(cache.read_text("utf-8"))
            return
        if not mods.exists():
            return
        for jar in sorted(mods.glob("*.jar")):
            try:
                with zipfile.ZipFile(jar) as z:
                    for n in z.namelist():
                        guide = "/ae2guide/" in n and n.endswith(".md") and not re.search(r"/_[a-z]{2}_[a-z]{2}/", n)
                        book = "/patchouli_books/" in n and "/en_us/entries/" in n and n.endswith(".json")
                        if not (guide or book):
                            continue
                        raw = z.read(n).decode("utf-8", "replace")
                        if book:
                            try:
                                d = json.loads(raw)
                                title = d.get("name", n)
                                text = "\n".join(p.get("text", "") for p in d.get("pages", []) if isinstance(p, dict))
                            except ValueError:
                                continue
                        else:
                            m = re.search(r"^\s*title:\s*(.+)$", raw, re.M)
                            title = m.group(1).strip() if m else n.rsplit("/", 1)[-1]
                            text = raw
                        self.pages.append({"mod": n.split("/")[1], "jar": jar.name, "path": n,
                                           "title": title, "text": text[:20000]})
            except (zipfile.BadZipFile, OSError):
                continue
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(self.pages), "utf-8")

    def search(self, query: str, mod: str | None = None, n: int = 3) -> list[dict]:
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 1]
        scored = []
        for p in self.pages:
            if mod and mod.lower() not in (p["mod"].lower(), p["jar"].lower()) and mod.lower() not in p["jar"].lower():
                continue
            title, text = p["title"].lower(), p["text"].lower()
            s = sum(title.count(t) * 8 + min(text.count(t), 20) for t in terms)
            if s:
                scored.append((s, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:n]]


# ------------------------------------------------------------------------------------------ focus guard

PAUSE_MARK = HERE / "sessions" / ".pause_on_lost_focus"


def hold_focus(mcp) -> str | None:
    """While a turn runs, the game must not open the pause menu when its window is in the background (it would cover
    every view). Turns pauseOnLostFocus off without saving options.txt and returns the value to restore. The original
    value is also kept in a marker file, so a killed run is repaired by the next one."""
    try:
        old = mcp.json("video_get", {"filter": "pauseOnLostFocus"}).get("pauseOnLostFocus")
        if old is None:  # mc-mcp older than 0.2.1: no plain-field options
            return None
        if PAUSE_MARK.exists():
            old = PAUSE_MARK.read_text().strip() or old
        PAUSE_MARK.parent.mkdir(parents=True, exist_ok=True)
        PAUSE_MARK.write_text(old)
        mcp.json("video_set", {"option": "pauseOnLostFocus", "value": "false", "save": False})
        scr = mcp.json("screen", {})
        if scr.get("open") and scr.get("class", "").endswith("PauseScreen"):
            mcp.call("close_screen", {})
        return old
    except Exception:
        return None


def release_focus(mcp, old: str | None):
    if old is None:
        return
    try:
        mcp.json("video_set", {"option": "pauseOnLostFocus", "value": old, "save": False})
        PAUSE_MARK.unlink(missing_ok=True)
    except Exception:
        pass
