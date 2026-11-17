"""Reference images and videos for the architect: find them in a request, fetch them, turn them into image blocks.

A reference can be a local image or video path, an http(s) URL to one, a YouTube (or any yt-dlp) link, or the
clipboard (the word `/paste` in a request). Videos become up to MAX_FRAMES scene-change keyframes in time order.
Everything is stored under the session's refs/ folder, so later turns and re-runs can see it again.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageGrab

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "twitch.tv", "streamable.com", "reddit.com/r/")
MAX_SIDE = 1024          # ~1.5k tokens per image
MAX_FRAMES = 8
VIDEO_SECONDS = 900      # only look at the first 15 min of long videos

_URL = re.compile(r"https?://\S+")
_QUOTED = re.compile(r"\"([^\"]+)\"|'([^']+)'")


def find(text: str) -> tuple[str, list[str]]:
    """Split a request into (text without the references, references)."""
    refs: list[str] = []

    def take(m: re.Match) -> str:
        refs.append(m.group(0).rstrip(").,]"))
        return ""

    out = _URL.sub(take, text)

    def quoted(m: re.Match) -> str:
        s = m.group(1) or m.group(2)
        if Path(s).suffix.lower() in IMAGE_EXT | VIDEO_EXT and Path(s).exists():
            refs.append(s)
            return ""
        return m.group(0)

    out = _QUOTED.sub(quoted, out)
    words = []
    for w in out.split():
        if w == "/paste":
            refs.append("clipboard:")
        elif Path(w).suffix.lower() in IMAGE_EXT | VIDEO_EXT and Path(w).exists():
            refs.append(w)
        else:
            words.append(w)
    return " ".join(words), refs


def _norm(img: Image.Image, dst: Path) -> Path:
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    img.save(dst, "JPEG", quality=88)
    return dst


def _video_frames(video: Path, outdir: Path, stem: str) -> list[Path]:
    tmp = outdir / f"{stem}_scenes"
    tmp.mkdir(parents=True, exist_ok=True)
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-t", str(VIDEO_SECONDS), "-i", str(video)]
    subprocess.run(base + ["-vf", f"select='gt(scene,0.3)',scale='min({MAX_SIDE},iw)':-2", "-vsync", "vfr",
                           str(tmp / "s_%04d.jpg")], check=True)
    frames = sorted(tmp.glob("s_*.jpg"))
    if len(frames) < 3:  # few hard cuts (one long orbit shot): sample evenly instead
        for f in frames:
            f.unlink()
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(video)], capture_output=True, text=True, check=True).stdout.strip() or 0)
        fps = MAX_FRAMES / max(1.0, min(dur, VIDEO_SECONDS))
        subprocess.run(base + ["-vf", f"fps={fps:.5f},scale='min({MAX_SIDE},iw)':-2", str(tmp / "s_%04d.jpg")],
                       check=True)
        frames = sorted(tmp.glob("s_*.jpg"))
    if len(frames) > MAX_FRAMES:  # spread the picks over the whole video
        frames = [frames[round(i * (len(frames) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    out = []
    for i, f in enumerate(frames):
        dst = outdir / f"{stem}_f{i + 1}.jpg"
        shutil.copy(f, dst)
        out.append(dst)
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def fetch(ref: str, outdir: Path) -> list[Path]:
    """Turn one reference into normalized JPEG frames in outdir. Raises with a readable message on failure."""
    outdir.mkdir(parents=True, exist_ok=True)
    stem = "ref_" + hashlib.sha1(ref.encode()).hexdigest()[:8]
    done = sorted(outdir.glob(f"{stem}*.jpg"))
    if done and ref != "clipboard:":
        return [p for p in done if "_scenes" not in str(p)]
    if ref == "clipboard:":
        img = ImageGrab.grabclipboard()
        if isinstance(img, list):  # files copied in Explorer
            return [p for f in img for p in fetch(f, outdir)]
        if img is None:
            raise ValueError("no image on the clipboard")
        stem = "ref_clip_" + hashlib.sha1(img.tobytes()).hexdigest()[:8]
        return [_norm(img, outdir / f"{stem}.jpg")]
    if ref.startswith("http"):
        if any(h in ref for h in VIDEO_HOSTS):
            subprocess.run(["yt-dlp", "-q", "--no-playlist", "-f", "bv*[height<=720][ext=mp4]/b[height<=720]/b",
                            "--download-sections", f"*0-{VIDEO_SECONDS}", "-o", str(outdir / f"{stem}.%(ext)s"), ref],
                           check=True)
            vids = [p for p in outdir.glob(f"{stem}.*") if p.suffix.lower() in VIDEO_EXT]
            if not vids:
                raise ValueError(f"yt-dlp got no video from {ref}")
            return _video_frames(vids[0], outdir, stem)
        req = urllib.request.Request(ref, headers={"User-Agent": "Mozilla/5.0 (architect reference fetch)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data, ctype = r.read(), r.headers.get("content-type", "")
        except OSError:  # some CDNs hang on IPv6 here; curl -4 gets through
            data = subprocess.run(["curl", "-sSfL4", "-m", "120", "-A", "Mozilla/5.0", ref],
                                  capture_output=True, check=True).stdout
            ctype = ""
        if ctype.startswith("video/") or Path(ref.split("?")[0]).suffix.lower() in VIDEO_EXT:
            vid = outdir / f"{stem}.mp4"
            vid.write_bytes(data)
            return _video_frames(vid, outdir, stem)
        return [_norm(Image.open(io.BytesIO(data)), outdir / f"{stem}.jpg")]
    p = Path(ref)
    if not p.exists():
        raise ValueError(f"no such file: {ref}")
    if p.suffix.lower() in VIDEO_EXT:
        return _video_frames(p, outdir, stem)
    return [_norm(Image.open(p), outdir / f"{stem}.jpg")]


def blocks(paths: list[Path]) -> list[dict]:
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(p.read_bytes()).decode()}}
            for p in paths]


INSTRUCTIONS = """REFERENCE MODE: {n} reference image(s) are attached{video}. Work in this order:
1. Study them. Save a brief with plan(action=set), merged into the existing plan under "reference": what it is;
   footprint and proportions in blocks (scale from known sizes: a door is 2 high, a storey is 4-5 blocks, a person
   is 2; or the size the user asked for); massing as a list of volumes; roof form; wall depth layers; palette
   mapped to real block ids; signature features; the closest theme in knowledge/themes.
2. Build it to match the reference's shape, proportions and silhouette first, then details. If the user asks for
   a mod theme or other materials, change the materials, not the shape.
3. view from the angle closest to the reference's camera. Compare the screenshot with the reference and list
   concrete differences (proportions, missing features, wrong colours). Fix them. At most 2 compare rounds.
4. Tell the user what matches and what you simplified.
If the reference shows one organic object (a statue, creature, ship, vehicle, tree), don't hand-build it: call
image_to_3d with image="ref", then add a plinth, lighting or setting around it with boxes and shapes."""


def instructions(n: int, from_video: bool) -> str:
    return INSTRUCTIONS.format(n=n, video=" (keyframes from a video, in time order)" if from_video else "")
