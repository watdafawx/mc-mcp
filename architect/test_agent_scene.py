"""Offline end-to-end tests for the scene_set / scene_patch tools of architect.py: python test_agent_scene.py
(no Minecraft, no API: Mcp is a recording mock, the model client is never called; sessions go to a temp dir).

Covers: scene_set (hall + roof spire + wall porch) emits one ghost_set per node and saves scene.json with 0 floaters;
scene_patch resizing the spire re-sends ONLY the spire; widening the hall repositions attached children through their
anchors with 0 floaters; removing a leaf clears its ghost; a fresh Architect on the same session directory (--iterate)
patches and diffs cleanly (and re-sends ghosts the game lost); a vanilla-only registry resolves every kit block to
minecraft:*; a missing / truncated registry; atomic failures; massing.KITS still equal to kits.json element 0.

Prints "ok"/"FAIL" per check and exits non-zero on any failure.
"""
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
if "anthropic" not in sys.modules:  # architect.py imports the SDK at the top; the tests never call it
    try:
        import anthropic  # noqa: F401
    except ImportError:
        sys.modules["anthropic"] = types.ModuleType("anthropic")

import architect  # noqa: E402
import massing  # noqa: E402
import palettes  # noqa: E402
from scene import SceneError  # noqa: E402

failed = 0


def check(name, cond, extra=""):
    global failed
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  " + str(extra)))
    if not cond:
        failed += 1


# ------------------------------------------------------------------------------------------ mocks

class Game:
    """What the mocked game knows: every recorded call, the ghosts that exist, the registry it would report."""

    def __init__(self, registry="unset"):
        self.calls: list[tuple[str, dict]] = []
        self.ghosts: dict[str, dict] = {}
        self.registry = registry  # None = tool errors; "unset" = ATM10-like (every kit block exists); list of ids; callable

    def sets(self):
        return [a["id"] for n, a in self.calls if n == "ghost_set"]

    def clears(self):
        return [a["id"] for n, a in self.calls if n == "ghost_clear"]

    def reset_calls(self):
        self.calls.clear()


class MockMcp:
    nogold = False
    swapped = 0

    def __init__(self, game: Game):
        self.game = game

    def tools(self):
        return [{"name": n, "description": n, "inputSchema": {"type": "object"}} for n in architect.FORWARD]

    def json(self, name, args):
        g = self.game
        g.calls.append((name, args))
        if name == "ghost_set":
            g.ghosts[args["id"]] = args
            return {"id": args["id"], "ok": True}
        if name == "ghost_clear":
            gid = args["id"]
            for k in [k for k in g.ghosts if k == gid or (gid.endswith("/") and k.startswith(gid)) or gid == "*"]:
                del g.ghosts[k]
            return {"cleared": gid}
        if name == "ghost_list":
            return {"ghosts": [{"id": k} for k in g.ghosts]}
        if name == "registry_blocks":
            if g.registry is None:
                raise RuntimeError("registry_blocks: no client world")
            if callable(g.registry):
                return g.registry(args)
            return {"blocks": g.registry}
        raise RuntimeError(f"unexpected {name}")

    def call(self, name, args):
        return json.dumps(self.json(name, args)), False


architect.Mcp = lambda url, _g=None: MockMcp(CURRENT[0])
architect.llm_client.make_client = lambda: (None, {"provider": "anthropic", "local": False})
TMP = Path(tempfile.mkdtemp(prefix="test_agent_scene_"))
architect.HERE = TMP
CURRENT: list[Game] = [Game()]


def new_architect(session: str, game: Game) -> architect.Architect:
    CURRENT[0] = game
    return architect.Architect(session)


def atm10_like() -> list[str]:
    """Every block the kits mention plus all of vanilla."""
    out = set(palettes.vanilla_blocks())
    for kit in palettes.load_kits()["kits"].values():
        for chain in kit["roles"].values():
            out.update(palettes.base_id(b) for b in chain)
    return sorted(out)


SCENE = {
    "id": "base", "origin": [100, 64, -200], "kit": "station_white",
    "nodes": [
        {"id": "hall", "kind": "structure", "tag": "volume",
         "params": {"shape": "rect", "w": 21, "d": 15, "floors": 1, "floor_hs": [6], "roof": "flat",
                    "roof_details": 0, "antennas": 0}},
        {"id": "spire", "kind": "spire", "tag": "roof",
         "attach": {"target": "hall", "surface": "top", "align": "center"}, "params": {"h": 12, "base": 5}},
        {"id": "porch", "kind": "structure", "tag": "porch",
         "attach": {"target": "hall", "surface": "wall:south", "align": "center"},
         "params": {"shape": "rect", "w": 7, "d": 5, "floors": 1, "floor_hs": [4], "roof": "flat",
                    "roof_details": 0, "antennas": 0}},
    ]}


def redraw(out: str) -> dict:
    last = out.strip().splitlines()[-1]
    assert last.startswith("redraw: "), last
    return json.loads(last[len("redraw: "):])


def center_x(g):
    b = g["bounds"]
    return (b["min"][0] + b["max"][0]) / 2


# ------------------------------------------------------------------------------------------ massing consolidation

print("== massing reads kits.json")
check("KITS == kits.json element 0 (every kit)",
      massing.KITS == {n: palettes.resolve_kit(n) for n in palettes.list_kits()})
check("ROOF_DEFAULT keeps the three mansard kits",
      massing.ROOF_DEFAULT == {"hextech": "mansard", "gothic": "mansard", "steampunk": "mansard"}, massing.ROOF_DEFAULT)
check("known preferred blocks unchanged", massing.KITS["steampunk"]["glass"] == "minecraft:cyan_stained_glass"
      and massing.KITS["station_white"]["glass"] == "connectedglass:borderless_glass_light_blue"
      and massing.KITS["hextech"]["wall"] == "minecraft:quartz_bricks")
check("_kit: kit name", massing._kit("gothic")["glow"] == "minecraft:shroomlight")
check("_kit: name + overrides", massing._kit("gothic", {"glow": "minecraft:glowstone"})["glow"] == "minecraft:glowstone")
check("_kit: role dict over station_white", massing._kit({"wall": "minecraft:stone"})["wall"] == "minecraft:stone"
      and massing._kit({"wall": "minecraft:stone"})["glass"] == massing.KITS["station_white"]["glass"])
try:
    massing._kit("nope")
    check("_kit: unknown kit raises", False)
except massing.ShapeError:
    check("_kit: unknown kit raises", True)
check("_kit returns a copy", massing._kit("gothic") is not massing.KITS["gothic"])

# ------------------------------------------------------------------------------------------ scene_set / scene_patch

print("== scene_set")
game = Game(registry=atm10_like())
arch = new_architect("s1", game)
check("tools registered", {"scene_set", "scene_patch"} <= {t["name"] for t in arch.tools})
check("no registry fetched at startup", not any(n == "registry_blocks" for n, _ in game.calls))
out = arch.run_local("scene_set", {"scene": SCENE})
rd = redraw(out)
check("registry fetched once and cached", [n for n, _ in game.calls].count("registry_blocks") == 1
      and arch._available_blocks is not None)
check("one ghost_set per node", game.sets() == ["base/hall", "base/spire", "base/porch"], game.sets())
check("no ghost_clear", game.clears() == [])
check("redraw summary", rd["set"] == ["base/hall", "base/spire", "base/porch"] and rd["keep"] == 0 and rd["clear"] == [], rd)
check("scene.json saved", arch.scene_file.exists() and json.loads(arch.scene_file.read_text("utf-8"))["id"] == "base")
check("saved scene has the 3 nodes", [n["id"] for n in json.loads(arch.scene_file.read_text("utf-8"))["nodes"]]
      == ["hall", "spire", "porch"])
check("0 floaters", arch._last_scene_compile.floating == [] and "warnings" not in rd, (arch._last_scene_compile.floating, rd))
check("describe in reply (no block dump)", "scene base kit station_white" in out and "3 nodes" in out
      and "roof_deck" in out and len(out) < 4000, len(out))
hall, spire, porch = (arch._last_scene_compile.ghost(n) for n in ("hall", "spire", "porch"))
check("spire sits on top of the hall", spire["bounds"]["min"][1] > hall["bounds"]["min"][1] + 5
      and abs(center_x(spire) - center_x(hall)) < 1, (spire["bounds"], hall["bounds"]))
check("porch touches the south wall", porch["bounds"]["min"][2] == hall["bounds"]["max"][2] + 1,
      (porch["bounds"], hall["bounds"]))
check("ghost_set args are compact (palette + boxes/blocks)", all(set(a) >= {"id", "origin", "palette", "mode"}
                                                                for n, a in game.calls if n == "ghost_set"))
check("guard knows the scene ghosts", set(arch.guard.cells) >= {"base/hall", "base/spire", "base/porch"}
      and all(arch.guard.cells[k] for k in ("base/hall", "base/spire", "base/porch")))

print("== scene_patch")
game.reset_calls()
out = arch.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"params": {"h": 18}}}]})
rd = redraw(out)
check("resize spire: only the spire is re-sent", game.sets() == ["base/spire"] and game.clears() == [], game.calls)
check("resize spire: keep == 2", rd["keep"] == 2 and rd["set"] == ["base/spire"] and rd["clear"] == [], rd)
check("resize spire: taller", arch._last_scene_compile.ghost("spire")["bounds"]["size"][1]
      > spire["bounds"]["size"][1])
check("resize spire: scene.json updated", json.loads(arch.scene_file.read_text("utf-8"))["nodes"][1]["params"]["h"] == 18)
check("resize spire: no registry refetch", [n for n, _ in game.calls].count("registry_blocks") == 0)

game.reset_calls()
out = arch.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "hall", "patch": {"params": {"w": 31}}}]})
rd = redraw(out)
res = arch._last_scene_compile
check("widen hall: children follow through anchors", set(game.sets()) == {"base/hall", "base/spire", "base/porch"}, game.sets())
check("widen hall: 0 floaters", res.floating == [] and "warnings" not in rd, (res.floating, rd))
check("widen hall: wider", res.ghost("hall")["bounds"]["size"][0] > hall["bounds"]["size"][0], res.ghost("hall")["bounds"])
check("widen hall: spire and porch stay centred", abs(center_x(res.ghost("spire")) - center_x(res.ghost("hall"))) < 1
      and abs(center_x(res.ghost("porch")) - center_x(res.ghost("hall"))) < 1)
check("widen hall: porch still on the wall", res.ghost("porch")["bounds"]["min"][2] == res.ghost("hall")["bounds"]["max"][2] + 1)

game.reset_calls()
out = arch.run_local("scene_patch", {"ops": [{"op": "remove_node", "id": "porch"}]})
rd = redraw(out)
check("remove leaf: ghost_clear for its ghost id", game.clears() == ["base/porch"], game.calls)
check("remove leaf: nothing re-sent", game.sets() == [] and rd["keep"] == 2 and rd["clear"] == ["base/porch"], rd)
check("remove leaf: guard forgets it", "base/porch" not in arch.guard.cells and "base/spire" in arch.guard.cells)
check("remove leaf: game no longer has it", "base/porch" not in game.ghosts)

game.reset_calls()
before = arch.scene_file.read_text("utf-8")
try:
    arch.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "hall", "patch": {"params": {"w": 25}}},
                                           {"op": "remove_node", "id": "hall"}]})
    check("bad patch raises", False)
except SceneError as e:
    check("bad patch raises with orphans hint", "orphans" in str(e), str(e))
check("bad patch: nothing sent, scene.json untouched", game.calls == [] and arch.scene_file.read_text("utf-8") == before)
check("bad patch: in-memory scene untouched", arch._scene.index()["hall"].params["w"] == 31)
try:
    arch.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"attach": {"target": "hall", "surface": "roof_dek"}}}]})
    check("bad anchor raises", False)
except SceneError as e:
    check("bad anchor raises with did-you-mean", "roof_deck" in str(e), str(e))
check("bad anchor: nothing sent", game.calls == [])

print("== --iterate: a fresh Architect on the same session directory")
game.reset_calls()
arch2 = new_architect("s1", game)
check("fresh instance has no scene in memory yet", arch2._scene is None and arch2._last_scene_compile is None)
out = arch2.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"params": {"h": 9}}}]})
rd = redraw(out)
check("reloaded scene.json: patch re-sends only the spire", game.sets() == ["base/spire"] and rd["keep"] == 1
      and rd["clear"] == [], (game.sets(), rd))
check("reloaded: registry cached once for the new instance", [n for n, _ in game.calls].count("registry_blocks") == 1)
check("reloaded: nothing queued for re-send", arch2._scene_unsent == set())
check("reloaded: still 0 floaters", arch2._last_scene_compile.floating == [])
check("reloaded: 2 nodes (porch stayed removed)", [g["id"] for g in arch2._last_scene_compile.ghosts] == ["hall", "spire"])

game.reset_calls()
game.ghosts.clear()  # the game restarted: every ghost is gone
arch3 = new_architect("s1", game)
out = arch3.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"params": {"h": 10}}}]})
rd = redraw(out)
check("game lost its ghosts: all scene ghosts re-sent", set(game.sets()) == {"base/hall", "base/spire"}
      and rd["keep"] == 0, (game.sets(), rd))

game.reset_calls()
arch4 = new_architect("s1", game)
arch4.run_local("scene_patch", {"ops": [{"op": "set_scene", "origin": [100, 64, -190]}]})
check("set_scene origin move re-sends every ghost", set(game.sets()) == {"base/hall", "base/spire"}, game.sets())

game.reset_calls()
fresh = new_architect("s_none", game)
try:
    fresh.run_local("scene_patch", {"ops": [{"op": "remove_node", "id": "x"}]})
    check("scene_patch with no scene raises", False)
except ValueError as e:
    check("scene_patch with no scene raises", "scene_set" in str(e), str(e))
check("no scene: nothing sent", game.sets() == [] and game.clears() == [])

print("== replacing the scene")
game.reset_calls()
arch5 = new_architect("s1", game)
new = json.loads(json.dumps(SCENE))
new["nodes"] = new["nodes"][:2]  # drop the porch
new["nodes"][1]["params"]["h"] = 10
out = arch5.run_local("scene_set", {"scene": new})
rd = redraw(out)
check("scene_set diffs against the saved scene", game.sets() == [] or set(game.sets()) <= {"base/hall", "base/spire"}, rd)
check("scene_set after resume: no porch left", "base/porch" not in game.ghosts)
other = {"id": "tower2", "origin": [0, 64, 0], "kit": "gothic", "nodes": [
    {"id": "keep", "kind": "structure", "params": {"shape": "rect", "w": 9, "d": 9, "floors": 1, "floor_hs": [5],
                                                    "roof": "flat", "roof_details": 0, "antennas": 0}}]}
game.reset_calls()
rd = redraw(arch5.run_local("scene_set", other))  # top-level form (no `scene` key)
check("top-level scene keys accepted", game.sets() == ["tower2/keep"], game.sets())
check("a new scene id clears the old scene's ghosts", sorted(game.clears()) == ["base/hall", "base/spire"], game.clears())
try:
    arch5.run_local("scene_set", {})
    check("empty scene_set raises", False)
except ValueError:
    check("empty scene_set raises", True)

# ------------------------------------------------------------------------------------------ registries

print("== pack-aware palettes through the tool")
vgame = Game(registry=sorted(palettes.vanilla_blocks()))
va = new_architect("v1", vgame)
out = va.run_local("scene_set", {"scene": SCENE})
res = va._last_scene_compile
check("vanilla registry: scene palette all minecraft:", all(b.startswith("minecraft:") for b in res.palette.values()), res.palette)
used = {b for n, a in vgame.calls if n == "ghost_set" for b in a["palette"].values()}
check("vanilla registry: every block sent is minecraft:*", all(palettes.base_id(b).startswith("minecraft:") for b in used),
      sorted(b for b in used if not b.startswith("minecraft:")))
check("vanilla registry: kit glass fell back", res.palette["glass"] == "minecraft:light_blue_stained_glass", res.palette["glass"])
check("vanilla registry: nothing missing", res.missing_blocks == {}, res.missing_blocks)
check("vanilla registry: fallbacks reported to the model", "palette fallbacks" in out)

cgame = Game(registry=atm10_like())
ca = new_architect("c1", cgame)
ca.run_local("scene_set", {"scene": SCENE})
check("ATM10-like registry: preferred blocks", ca._last_scene_compile.palette["glass"]
      == "connectedglass:borderless_glass_light_blue")
check("vanilla and ATM10 compile to the same bounds", [g["bounds"] for g in ca._last_scene_compile.ghosts]
      == [g["bounds"] for g in res.ghosts])

ngame = Game(registry=None)
na = new_architect("n1", ngame)
out = na.run_local("scene_set", {"scene": SCENE})
check("registry_blocks error: falls back to preferred blocks", na._available_blocks is None
      and na._last_scene_compile.palette["glass"] == "connectedglass:borderless_glass_light_blue")
check("registry_blocks error: build still works", ngame.sets() == ["base/hall", "base/spire", "base/porch"])
na.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"params": {"h": 14}}}]})
check("registry_blocks error: tried only once", [n for n, _ in ngame.calls].count("registry_blocks") == 1)


def truncated(args):
    """Like the real tool: the unfiltered list is capped; namespace queries return the whole namespace."""
    van = sorted(palettes.vanilla_blocks())
    allb = atm10_like()
    if not args.get("namespace"):
        return {"matched": len(allb), "blocks": van[:5], "truncated": True,
                "namespaces": {n: 1 for n in {b.split(":")[0] for b in allb} | {"zzz_unrelated"}}}
    return {"matched": 1, "blocks": [b for b in allb if b.split(":")[0] == args["namespace"]]}


tgame = Game(registry=truncated)
ta = new_architect("t1", tgame)
ta.run_local("scene_set", {"scene": SCENE})
asked = {a.get("namespace") for n, a in tgame.calls if n == "registry_blocks"}
check("truncated registry: kit namespaces fetched one by one", {"minecraft", "connectedglass", "luminax", "chisel"} <= asked
      and "zzz_unrelated" not in asked, asked)
check("truncated registry: mod blocks resolved", ta._last_scene_compile.palette["glass"]
      == "connectedglass:borderless_glass_light_blue")

print("== hand clears and per-ghost errors")
hgame = Game(registry=atm10_like())
ha = new_architect("h1", hgame)
ha.run_local("scene_set", {"scene": SCENE})
ha._scene_unsent |= {"base/spire"}  # what turn() records after a manual ghost_clear of that ghost
hgame.reset_calls()
rd = redraw(ha.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "porch", "patch": {"params": {"w": 9}}}]}))
check("manually cleared scene ghost is re-sent with the next call", set(hgame.sets()) == {"base/porch", "base/spire"}, hgame.sets())

orig_json = MockMcp.json


def flaky(self, name, args):
    if name == "ghost_set" and args["id"] == "base/spire":
        raise RuntimeError("ghost_set: bad_palette")
    return orig_json(self, name, args)


MockMcp.json = flaky
hgame.reset_calls()
rd = redraw(ha.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "spire", "patch": {"params": {"h": 15}}}]}))
MockMcp.json = orig_json
check("failed ghost_set is reported and queued", "base/spire" in ha._scene_unsent
      and any("base/spire failed" in w for w in rd.get("warnings", [])), rd)
hgame.reset_calls()
rd = redraw(ha.run_local("scene_patch", {"ops": [{"op": "patch_node", "id": "porch", "patch": {"params": {"w": 11}}}]}))
check("queued ghost is retried next call", "base/spire" in hgame.sets() and ha._scene_unsent == set(), (hgame.sets(), rd))

print("== prompts")
check("SYSTEM mentions scene_set and scene_patch", "scene_set" in architect.SYSTEM and "scene_patch" in architect.SYSTEM
      and "attach" in architect.SYSTEM)
brief = architect.prompt_request("a keep", 1, 66, 2, "gothic", "keep1")
check("PROMPT_BRIEF formats and prefers scenes", "scene_set" in brief and "scene_patch" in brief and "keep1" in brief
      and "{id}" not in brief and "{x}" not in brief and "attach {target, surface, align}" in brief, brief[:300])
check("campus / shapes / multiblock / ghost_set still offered", {"campus", "shapes", "multiblock", "ghost_set"}
      <= {t["name"] for t in arch.tools})

print(f"\n{'FAILED: ' + str(failed) if failed else 'all checks passed'}")
sys.exit(1 if failed else 0)
