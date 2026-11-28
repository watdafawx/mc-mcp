"""Offline tests for views.py (vision context pruning, camera math) and the NDJSON event helper in mcp_client.py:
python test_views.py   (no Minecraft, no API, no anthropic import)."""
import copy
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mcp_client as M  # noqa: E402
import views as V  # noqa: E402


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0

PH = V.PRUNED_IMAGE


def img(tag):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": tag}}


def tu(i, name="view"):
    return {"role": "assistant", "content": [{"type": "text", "text": "ok"},
                                             {"type": "tool_use", "id": f"t{i}", "name": name, "input": {}}]}


def tr(i, images=1, text="view iso of x"):
    content = [{"type": "text", "text": text}] + [img(f"v{i}_{k}") for k in range(images)]
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": content,
                                         "is_error": False}]}


def history(n_views, with_user_refs=True):
    msgs = []
    first = [{"type": "text", "text": "reference"}, img("USER_REF_0"), img("USER_REF_1"),
             {"type": "text", "text": "Request: build it"}] if with_user_refs else "build it"
    msgs.append({"role": "user", "content": first})
    for i in range(n_views):
        msgs.append(tu(i))
        msgs.append(tr(i, images=2))  # view image + the reference thumbnail the view attaches
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": "done"}]})
    return msgs


def images_in(m):
    out = []
    for b in m["content"] if isinstance(m["content"], list) else []:
        if b.get("type") == "image":
            out.append(b["source"]["data"])
        elif b.get("type") == "tool_result" and isinstance(b.get("content"), list):
            out += [c["source"]["data"] for c in b["content"] if c.get("type") == "image"]
    return out


def tool_pairs_ok(msgs):
    """every tool_use id has a tool_result with the same id in the very next user message, and vice versa."""
    for i, m in enumerate(msgs):
        if m["role"] != "assistant" or not isinstance(m["content"], list):
            continue
        ids = [b["id"] for b in m["content"] if b.get("type") == "tool_use"]
        if not ids:
            continue
        nxt = msgs[i + 1]["content"]
        got = [b["tool_use_id"] for b in nxt if b.get("type") == "tool_result"]
        if sorted(ids) != sorted(got):
            return False
    return True


# ---- prune_old_images
h = history(5)
snap = copy.deepcopy(h)
p = V.prune_old_images(h, keep_last=2)
check("input is not mutated", h == snap)
check("same length and roles", len(p) == len(h) and [m["role"] for m in p] == [m["role"] for m in h])
kept = [im for m in p for im in images_in(m) if im.startswith("v")]
check("keeps images of the 2 newest view results", kept == ["v3_0", "v3_1", "v4_0", "v4_1"], str(kept))
for i in range(3):
    blk = p[2 + 2 * i]["content"][0]
    cont = blk["content"]
    check(f"old view {i}: images replaced by one placeholder, text kept",
          cont == [{"type": "text", "text": "view iso of x"}, PH], str(cont))
check("user reference images in the first request survive", images_in(p[0]) == ["USER_REF_0", "USER_REF_1"])
check("first request is the same object (untouched)", p[0] is h[0])
check("tool_use / tool_result pairing preserved", tool_pairs_ok(p))
check("tool_result ids and is_error preserved",
      all(p[2 + 2 * i]["content"][0]["tool_use_id"] == f"t{i}" and p[2 + 2 * i]["content"][0]["is_error"] is False
          for i in range(5)))
check("newest results are shared objects (no copy needed)", p[8] is h[8] and p[10] is h[10])
check("placeholder text", PH == {"type": "text", "text": "[earlier view image pruned to save context]"})
json.dumps(p)
check("result is JSON serialisable", True)

check("fewer image results than keep_last: nothing pruned", V.prune_old_images(history(2), 2) == history(2))
check("keep_last=1", sum(im.startswith("v") for m in V.prune_old_images(h, 1) for im in images_in(m)) == 2)
check("keep_last=0 prunes every tool image but not user refs",
      [im for m in V.prune_old_images(h, 0) for im in images_in(m)] == ["USER_REF_0", "USER_REF_1"])
check("string-content user message is fine", V.prune_old_images(history(4, with_user_refs=False), 2)[0]["content"] == "build it")

# text-only tool results do not count toward keep_last
mixed = history(3)
mixed.insert(5, tu(9, "plan"))
mixed.insert(6, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t9", "content": "plan saved"}]})
pm = V.prune_old_images(mixed, 2)
check("text-only results ignored for counting", [im for m in pm for im in images_in(m) if im.startswith("v")]
      == ["v1_0", "v1_1", "v2_0", "v2_1"])
check("text-only tool_result untouched", pm[6] is mixed[6])
check("mixed history keeps pairing", tool_pairs_ok(pm))

# tool_result that is ONLY an image still ends up with valid (non-empty) content
only = [{"role": "user", "content": "go"}, tu(0, "blocks"),
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t0", "content": [img("sheet")]}]},
        tu(1), tr(1), tu(2), tr(2)]
po = V.prune_old_images(only, 2)
check("image-only tool_result becomes a text placeholder", po[2]["content"][0]["content"] == [PH])

# a user turn mixing tool_results AND the user's own pasted image: only the tool_result image can be pruned
tricky = [{"role": "user", "content": "go"}, tu(0),
          {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t0", "content": [img("old")]},
                                       img("USER_PASTE"), {"type": "text", "text": "looks bad"}]},
          tu(1), tr(1), tu(2), tr(2)]
pt = V.prune_old_images(tricky, 2)
check("user image next to a tool_result is kept", images_in(pt[2]) == ["USER_PASTE"], str(images_in(pt[2])))

# ---- camera_pose
eye, look, cy = V.camera_pose([0, 0, 0], [10, 10, 10], "iso", 1.0, None)
check("iso looks at the centre", look == (5.0, 5.0, 5.0), str(look))
check("iso eye is south-west and above", eye[0] < 5 and eye[2] > 5 and eye[1] > 5, str(eye))
eye, look, cy = V.camera_pose([0, 60, 0], [10, 80, 10], "cut", 1.0, 4)
check("cut_y given as local height is lifted to the world", cy == 64 and look[1] == 64, f"{cy} {look}")
eye, look, cy = V.camera_pose([0, 60, 0], [10, 80, 10], "inside", 1.0, None)
check("inside: eye at 1.6 above the floor", abs(eye[1] - 61.6) < 1e-9 and look[2] == -100, f"{eye} {look}")
check("zoom scales distance", V.camera_pose([0] * 3, [10] * 3, "front", 2.0)[0][2]
      > V.camera_pose([0] * 3, [10] * 3, "front", 1.0)[0][2])

# ---- NDJSON events
line = M.format_event("site", summary="fit 90/100 (good)", x=10, z=-4)
d = json.loads(line)
check("event line is one compact JSON object", "\n" not in line and d == {"event": "site", "summary": "fit 90/100 (good)", "x": 10, "z": -4}, line)
check("event key comes first", line.startswith('{"event":"site"'), line)
check("non-ASCII and odd values survive", json.loads(M.format_event("reply", text="é — ok", p=Path("a")))["text"] == "é — ok")
check("known event names", set(M.EVENTS) == {"site", "tool", "cost", "reply", "error", "done"})

os.environ.pop("ARCHITECT_NDJSON", None)
M.set_ndjson(None)
buf = io.StringIO()
with redirect_stdout(buf):
    wrote = M.emit_event("cost", usd=0.0123)
check("disabled by default: nothing written", wrote is False and buf.getvalue() == "")
os.environ["ARCHITECT_NDJSON"] = "1"
buf = io.StringIO()
with redirect_stdout(buf):
    wrote = M.emit_event("cost", usd=0.0123, tokens_in=5)
check("ARCHITECT_NDJSON=1 enables it", wrote is True and json.loads(buf.getvalue()) == {"event": "cost", "usd": 0.0123, "tokens_in": 5})
M.set_ndjson(False)
buf = io.StringIO()
with redirect_stdout(buf):
    wrote = M.emit_event("done", ok=True)
check("--ndjson state beats the env var when set False", wrote is False and buf.getvalue() == "")
M.set_ndjson(True)
os.environ.pop("ARCHITECT_NDJSON", None)
buf = io.StringIO()
with redirect_stdout(buf):
    M.emit_event("error", message="boom")
    M.emit_event("done", ok=False, usd=0.5)
rows = [json.loads(x) for x in buf.getvalue().splitlines()]
check("--ndjson writes one line per event", [r["event"] for r in rows] == ["error", "done"] and rows[0]["message"] == "boom", str(rows))
M.set_ndjson(None)

print("FAILED: %d" % check.failed if check.failed else "all ok")
sys.exit(1 if check.failed else 0)
