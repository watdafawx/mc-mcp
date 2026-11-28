"""Screenshot views for the architect and vision-context pruning.

view()/ref_thumb() take the `Architect` instance as `arch` (its mcp client, session dir, plan file and the
spectator / prev_view state). prune_old_images() keeps long runs cheap: only the newest image-bearing tool results
are sent to the model with their pictures, older ones keep their text and a short placeholder, so the history stays
a valid tool_use/tool_result sequence (messages.json is never touched)."""

from __future__ import annotations

import base64
import io
import json
import math
import time
from pathlib import Path

import postcheck

HERE = Path(__file__).resolve().parent
KNOWLEDGE = HERE / "knowledge"
PRUNED_IMAGE = {"type": "text", "text": "[earlier view image pruned to save context]"}


# ------------------------------------------------------------------------------- vision context pruning

def _has_image(block) -> bool:
    return isinstance(block, dict) and block.get("type") == "tool_result" and isinstance(block.get("content"), list)         and any(isinstance(c, dict) and c.get("type") == "image" for c in block["content"])


def prune_old_images(messages: list[dict], keep_last: int = 2) -> list[dict]:
    """Returns a copy of `messages` where the images inside OLDER `tool_result` blocks (view, blocks, image_to_3d,
    style_refs outputs, ...) are replaced by one text placeholder each run, keeping only the `keep_last` most recent
    image-bearing tool results intact. Images the player supplied (image blocks directly in a user message, such as
    the reference frames of the first request) are never touched, and every tool_use/tool_result pair, id and text
    block is preserved. The input list and its messages are not mutated."""
    keep_last = max(0, int(keep_last))
    spots = []  # (message index, block index) of every image-bearing tool_result, oldest first
    for mi, m in enumerate(messages):
        if m.get("role") != "user" or not isinstance(m.get("content"), list):
            continue
        for bi, b in enumerate(m["content"]):
            if _has_image(b):
                spots.append((mi, bi))
    old = set(spots[:max(0, len(spots) - keep_last)])
    if not old:
        return list(messages)
    out = []
    for mi, m in enumerate(messages):
        if not any(s[0] == mi for s in old):
            out.append(m)
            continue
        blocks = []
        for bi, b in enumerate(m["content"]):
            if (mi, bi) not in old:
                blocks.append(b)
                continue
            content = []
            for c in b["content"]:
                if isinstance(c, dict) and c.get("type") == "image":
                    if not content or content[-1] != PRUNED_IMAGE:  # several images in a row -> one placeholder
                        content.append(dict(PRUNED_IMAGE))
                else:
                    content.append(c)
            blocks.append({**b, "content": content})
        out.append({**m, "content": blocks})
    return out


# ------------------------------------------------------------------------------------------------- views

def camera_pose(lo, hi, angle: str, zoom: float = 1.0, cut_y=None):
    """Camera math for view(): bounds lo..hi (world) -> (eye, look, cut_y). cut_y given as a local height (below the
    bounds) is lifted to a world y. Pure function, no Minecraft needed."""
    if cut_y is not None and int(cut_y) < lo[1]:  # a local height (e.g. 4) instead of a world y
        cut_y = lo[1] + int(cut_y)
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    size = max(hi[i] - lo[i] for i in range(3))
    d = (size * 0.95 + 6) * zoom
    offsets = {"iso": (-0.7, 0.55, 0.7), "iso_ne": (0.7, 0.55, -0.7), "front": (0, 0.25, 1), "back": (0, 0.25, -1),
               "side": (1, 0.25, 0), "top": (0.01, 1, 0.01), "inside": (0, 0, 0), "cut": (-0.35, 1, 0.45),
               "se": (0.7, 0.55, 0.7), "nw": (-0.7, 0.55, -0.7)}
    ox, oy, oz = offsets.get(angle, offsets["iso"])
    if angle == "inside":
        eye = (c[0], lo[1] + 1.6, c[2])
        look = (c[0], lo[1] + 1.6, lo[2] - 100)
    elif angle == "street":
        ext = [hi[i] - lo[i] for i in range(3)]
        eye = (c[0], lo[1] + 2.6, hi[2] + max(ext[0], ext[2]) * 0.6 + 10)
        look = (c[0], lo[1] + ext[1] * 0.3, c[2])
    else:
        if angle in ("se", "nw"):  # bounding-sphere fit at FOV 70, the same rule the A/B shots used
            d = 0.5 * math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3))) / math.tan(math.radians(35)) * zoom
        norm = math.sqrt(ox * ox + oy * oy + oz * oz)
        if angle == "cut":
            c[1] = int(cut_y) if cut_y is not None else lo[1] + 4
        eye = (c[0] + ox / norm * d, c[1] + oy / norm * d, c[2] + oz / norm * d)
        look = tuple(c)
    return eye, look, cut_y


def view(arch, target: str, angle: str, zoom: float, cut_y=None, *, freecam: bool = False, path_map: str = "",
         shot_delay: float = 1.5, xray: bool = True):
    """Moves the camera (client-only freecam or spectator + /tp), takes a screenshot and returns tool_result content blocks."""
    ghosts = arch.mcp.json("ghost_list", {})["ghosts"]
    sel = [g for g in ghosts if "world_min" in g and (target == "*" or g["id"] == target
                                                     or (target.endswith("/") and g["id"].startswith(target)))]
    if not sel:
        raise ValueError(f"no ghost matches {target}")
    lo = [min(g["world_min"][i] for g in sel) for i in range(3)]
    hi = [max(g["world_max"][i] for g in sel) + 1 for i in range(3)]
    eye, look, cut_y = camera_pose(lo, hi, angle, zoom, cut_y)
    if not freecam and not arch.spectator:
        # Daylight, no HUD, ghosts drawn over terrain and opaque: the screenshot shows the design, not the woods.
        for cmd in ("gamemode spectator", "time set noon", "gamerule doDaylightCycle false",
                    "weather clear"):
            arch.mcp.call("run_command", {"command": cmd})
        arch.spectator = True
    # Every view: terrain can't hide the ghosts, they draw opaque, no HUD.
    if arch.prev_view is None:  # remember the player's own view modes so restore_view() can put them back
        try:
            arch.prev_view = arch.mcp.json("ghost_show", {"id": "*"})
        except Exception:
            arch.prev_view = {}
    show = {"id": "*", "xray": bool(xray), "solid": True, "hud": False}
    if angle == "cut":
        show["clip_y"] = int(cut_y) if cut_y is not None else lo[1] + 4
    else:
        show["clip_off"] = True
    arch.mcp.call("ghost_show", show)
    if freecam:
        arch.mcp.call("ghost_camera", {"x": eye[0], "y": eye[1], "z": eye[2],
                                       "look_x": look[0], "look_y": look[1], "look_z": look[2]})
        try:
            time.sleep(1.5 if angle in ("se", "nw", "street") else 0.5)  # let a frame render from the detached camera
            shot = arch.mcp.json("screenshot", {})
        finally:
            arch.mcp.call("ghost_camera", {"off": True})
    else:
        arch.mcp.call("run_command", {"command": f"tp @s {eye[0]:.1f} {eye[1]:.1f} {eye[2]:.1f}"})
        arch.mcp.call("look_at", {"x": look[0], "y": look[1], "z": look[2]})
        time.sleep(shot_delay)  # let chunks and the ghost mesh draw
        shot = arch.mcp.json("screenshot", {})
    path = shot["path"].replace("\\.\\", "\\")
    if path_map:
        src, dst = path_map.split("=", 1)
        if path.upper().startswith(src.upper()):
            path = dst + path[len(src):]
    data = base64.standard_b64encode(Path(path).read_bytes()).decode()
    plan = json.loads(arch.plan_file.read_text("utf-8")) if arch.plan_file.exists() else {}
    pwarns = postcheck.proportion_check(plan, sel)
    warn_txt = ("\nPROPORTION WARNINGS: " + "; ".join(pwarns)) if pwarns else ""
    out = [{"type": "text", "text": f"view {angle} of {target}: bounds {lo}..{hi}, camera at "
                                    f"{[round(v) for v in eye]}{warn_txt}"},
           {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}]
    ref = ref_thumb(arch) if angle != "cut" else None
    if ref:
        name, b64, is_user_ref = ref
        if is_user_ref:
            out += [{"type": "text", "text": f"USER REFERENCE ({name}). Compare the view above with this reference "
                     "and list the concrete differences (proportions, silhouette, roofline, palette, missing features), "
                     "then fix the biggest ones."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}]
        else:
            out += [{"type": "text", "text": f"REFERENCE ({name}, the player's mood board). Before your next build "
                     "step, compare the view above with this reference and write the 3 biggest gaps (silhouette, "
                     "roofline, facade depth, palette, detail, light), then fix the worst one."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}]
    return out


def ref_thumb(arch):
    """One small reference image for side-by-side comparison on view(). Prefers user-supplied refs in
    sessions/<name>/refs/ over kit mood boards so reference-image runs get a real compare-and-fix loop."""
    from PIL import Image
    import io
    user_refs_dir = arch.dir / "refs"
    user_refs = sorted(user_refs_dir.glob("*.jpg")) if user_refs_dir.exists() else []
    if user_refs:
        arch.user_ref_i = getattr(arch, "user_ref_i", -1) + 1
        p = user_refs[arch.user_ref_i % len(user_refs)]
        im = Image.open(p).convert("RGB")
        im.thumbnail((640, 640))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        return p.name, base64.standard_b64encode(buf.getvalue()).decode(), True
    kit = getattr(arch, "kit", None)
    if not kit:
        return None
    d = KNOWLEDGE / "style_refs"
    refs = [r for r in json.loads((d / "index.json").read_text("utf-8")) if r["kit"] == kit]
    if not refs:
        return None
    arch.ref_i = getattr(arch, "ref_i", -1) + 1
    r = refs[arch.ref_i % len(refs)]
    im = Image.open(d / r["file"]).convert("RGB")
    im.thumbnail((640, 640))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return r["file"], base64.standard_b64encode(buf.getvalue()).decode(), False
