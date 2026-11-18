"""Offline tests for suggest.py with a canned region survey and a fake model client: python test_suggest.py
(no Minecraft, no API, no .env, does not import architect.py)."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
import suggest as S  # noqa: E402


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0

# ---- canned survey: flat ground y=64 over 41x41, one 9x7 flat-roofed box (bbox 10..18 x 64..., z 10..16), lights on the west only
X0, Z0, N = 0, 0, 41
sv0 = S.site.Survey.from_fn(X0, Z0, 1, N, N, lambda x, z: (64, "."))
SURVEY = sv0.to_json()
SURVEY["center"] = [20, 20]
SURVEY["radius"] = 20
SURVEY["biome"] = "minecraft:plains"
SURVEY["region"] = {
    "built_blocks": 410,
    "bbox": [10, 65, 10, 18, 70, 16],
    "distinct_blocks": 1,
    "palette": [["minecraft:oak_planks", 410]],
    "features": {"water_cells": 0, "lava_cells": 0, "near_surface_ores": [], "light_blocks": 2, "glass_blocks": 0, "doors": 1},
    "buildings": [{
        "id": 0, "bbox": [10, 65, 10, 18, 70, 16], "size": [9, 6, 7], "columns": 63, "blocks": 410, "ground_y": 64,
        "palette": [["minecraft:oak_planks", 410]], "distinct_blocks": 1,
        "roof": {"top_y": 70, "distinct_top_heights": 1, "flat_pct": 100.0, "stair_slab_pct": 0.0},
        "lights": {"n": 0, "s": 0, "e": 0, "w": 2, "total": 2}, "glass_blocks": 0, "doors": 1,
    }],
    "bmap": ["." * N] * N,
    "bmap_format": "x",
}
TMP = Path(tempfile.mkdtemp(prefix="test_suggest_"))
SURVEY_FILE = TMP / "region.json"
SURVEY_FILE.write_text(json.dumps(SURVEY), "utf-8")

# ---- summary / prompt
raw, sv = S.load_region(SURVEY_FILE)
sm = S.summarize(raw)
check("summary drops grids", "y" not in sm and "bmap" not in sm and "f" not in sm)
check("summary keeps palette and buildings", sm["palette"][0][1] == 410 and len(sm["buildings"]) == 1)
sysm, user = S.build_prompt(sm, True)
check("prompt carries roof flatness", '"flat_pct":100.0' in user and "JSON" in sysm)
check("prompt is small", len(user) < 3000, str(len(user)))
check("no-overlay note", "does not want an overlay" in S.build_prompt(sm, False)[1])
check("no key material in prompt", "sk-" "ant" not in sysm + user)

# ---- parsing
good = {"suggestions": [
    {"text": "Building 0 roof is 100% flat: add a gable", "fix": "gable_roof", "building": 0, "material": "spruce"},
    {"text": "No light on the east wall: add lanterns", "fix": "lanterns", "building": 0, "material": None},
    {"text": "Palette has 1 block: mix in accents", "fix": "corner_posts", "building": 0, "material": "dark_oak"},
    {"text": "Add windows", "fix": "bogus", "building": 0},
    {"text": "x" * 400, "fix": None, "building": None},
]}
got = S.parse_reply("```json\n" + json.dumps(good) + "\n```", 1)
check("parse fenced json", len(got) == 5, str(len(got)))
check("bad fix dropped", got[3]["fix"] is None)
check("long text clipped", len(got[4]["text"]) <= S.MAX_TEXT)
check("prose around json ok", len(S.parse_reply("Sure! " + json.dumps(good) + " done", 1)) == 5)
over = {"suggestions": [{"text": f"tip {i}"} for i in range(10)]}
check("capped at 6", len(S.parse_reply(json.dumps(over), 1)) == 6)
dup = {"suggestions": [{"text": "a", "fix": "lanterns", "building": 0}, {"text": "b", "fix": "lanterns", "building": 0}]}
d = S.parse_reply(json.dumps(dup), 1)
check("duplicate fix dropped", d[0]["fix"] == "lanterns" and d[1]["fix"] is None)
check("fix needs a valid building", S.parse_reply(json.dumps({"suggestions": [{"text": "t", "fix": "lanterns", "building": 5}]}), 1)[0]["fix"] is None)
for bad in ("", "no json here", "{}", '{"suggestions": []}', '{"suggestions": [{"fix": "lanterns"}]}', "{broken"):
    try:
        S.parse_reply(bad, 1)
        check("rejects " + repr(bad[:20]), False)
    except ValueError:
        check("rejects " + repr(bad[:20]), True)

# ---- overlay blocks
b = SURVEY["region"]["buildings"][0]
L = S.lanterns(b, sv)
check("lanterns placed", len(L) > 0)
ys = {y for (_, y, _) in L}
check("lanterns on posts at ground+1/+2", ys == {65, 66}, str(ys))
check("no lantern on the lit west wall", all(x != 9 for (x, _, _) in L))
check("lantern is outside the bbox", all(not (10 <= x <= 18 and 10 <= z <= 16) for (x, _, z) in L))
G = S.gable_roof(b, sv, "spruce")
check("gable built above roof", G and min(y for (_, y, _) in G) == 71)
check("gable ridge is a slab", any("slab" in v for v in G.values()))
check("gable stairs face inward", G[(12, 71, 10)].endswith("facing=south,half=bottom]") and G[(12, 71, 16)].endswith("facing=north,half=bottom]"))
check("gable inside footprint", all(10 <= x <= 18 and 10 <= z <= 16 for (x, _, z) in G))
check("already pitched roof is left alone", S.gable_roof({**b, "roof": {**b["roof"], "stair_slab_pct": 80.0}}, sv, "oak") == {})
P = S.corner_posts(b, sv, "dark_oak")
check("4 corner posts", len(P) == 4 * 6 and all("axis=y" in v for v in P.values()))
sug = S.parse_reply(json.dumps(good), 1)
blocks = S.overlay_blocks(sug, SURVEY["region"]["buildings"], sv)
check("overlay combines all three", len(blocks) == len(L) + len(G) + len(P), str(len(blocks)))
check("survival blocks only", all(not v.split("[")[0].endswith(("command_block", "barrier", "bedrock")) for _, _, _, v in blocks))
check("default material contrasts with oak", S._default_material(b) != "oak")


# ---- run with a fake client (no API)
class FakeClient:
    def __init__(self, replies, usd):
        self.replies, self.usd, self.calls = list(replies), usd, 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        text = self.replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=SimpleNamespace(cost=self.usd))


cost_fn = lambda u: u.cost  # noqa: E731
out = TMP / "out.json"
c = FakeClient([json.dumps(good)], 0.002)
r = S.run(SURVEY_FILE, out, 0.10, True, client=c, cost_fn=cost_fn, model="fake", log=lambda *_: None)
saved = json.loads(out.read_text("utf-8"))
check("run writes result", saved["suggestions"][0]["fix"] == "gable_roof" and len(saved["blocks"]) == len(blocks) and c.calls == 1)
check("run reports cost", abs(saved["cost"] - 0.002) < 1e-9)
r = S.run(SURVEY_FILE, out, 0.10, False, client=FakeClient([json.dumps(good)], 0.002), cost_fn=cost_fn, model="fake", log=lambda *_: None)
check("no overlay = no blocks", r["blocks"] == [])
c = FakeClient(["garbage", json.dumps(good)], 0.01)
r = S.run(SURVEY_FILE, out, 0.10, True, client=c, cost_fn=cost_fn, model="fake", log=lambda *_: None)
check("one retry on a bad reply", c.calls == 2 and abs(r["cost"] - 0.02) < 1e-9)
c = FakeClient(["garbage", json.dumps(good)], 0.06)
try:
    S.run(SURVEY_FILE, out, 0.05, True, client=c, cost_fn=cost_fn, model="fake", log=lambda *_: None)
    check("cost cap stops the retry", False)
except RuntimeError as e:
    check("cost cap stops the retry", c.calls == 1 and "cap reached" in str(e), str(e))
c = FakeClient(["garbage", "garbage"], 0.001)
try:
    S.run(SURVEY_FILE, out, 0.10, True, client=c, cost_fn=cost_fn, model="fake", log=lambda *_: None)
    check("two bad replies fail", False)
except RuntimeError:
    check("two bad replies fail", c.calls == 2)

# ---- hygiene
src = (Path(__file__).parent / "suggest.py").read_text("utf-8")
check("suggest.py never reads .env or a key", ".env" not in src.replace("architect/.env", "") and "ANTHROPIC_API_KEY" not in src)

print("\n%s" % ("ALL OK" if not check.failed else f"{check.failed} FAILED"))
sys.exit(1 if check.failed else 0)
