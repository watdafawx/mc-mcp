"""usage: shoot.py <brief> <arm>  -> raw/<brief>_<arm>_{se,nw,street}.png + raw/<brief>_<arm>.json"""
import sys, json, math, time, shutil, base64
from pathlib import Path
sys.path.insert(0, r"X:\Dev\Minecraft\mc-mcp\architect")
import architect
brief, arm = sys.argv[1], sys.argv[2]
raw = Path(r"X:\Dev\Minecraft\mc-mcp\architect\exports\ab_test\raw")
m = architect.Mcp("http://127.0.0.1:47861/mcp")
pre = f"ab/{brief}_{arm}/"
ghosts = [g for g in m.json("ghost_list", {})["ghosts"] if g["id"].startswith(pre) and "world_min" in g]
if not ghosts:
    print("NO GHOSTS", pre); sys.exit(2)
lo = [min(g["world_min"][i] for g in ghosts) for i in range(3)]
hi = [max(g["world_max"][i] for g in ghosts) + 1 for i in range(3)]
blocks = sum(g.get("blocks", 0) for g in ghosts)
c = [(lo[i] + hi[i]) / 2 for i in range(3)]
ext = [hi[i] - lo[i] for i in range(3)]
r = 0.5 * math.sqrt(sum(e * e for e in ext))
# only this build visible
m.call("ghost_show", {"id": "*", "visible": False})
m.call("ghost_show", {"id": pre, "visible": True})
for g in ghosts:
    m.call("ghost_show", {"id": g["id"], "visible": True})
m.call("ghost_show", {"id": "*", "xray": False, "solid": True, "hud": False, "clip_off": True})
FOV = 70.0
FILL = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
D = r / (math.tan(math.radians(FOV / 2)) * FILL)  # bounding-sphere fit, same rule for every arm
def shot(name, eye, look):
    for _ in range(4):
        st = m.call("status", {})[0]
        if "PauseScreen" in st or "\"screen\"" in st:
            m.call("close_screen", {}); time.sleep(0.5)
        else: break
    m.call("ghost_camera", {"x": eye[0], "y": eye[1], "z": eye[2], "look_x": look[0], "look_y": look[1], "look_z": look[2]})
    time.sleep(1.5)
    s = m.json("screenshot", {})
    p = s["path"].replace("\.\\", "\\")
    if p.upper().startswith("G:\\"): p = "Q:\\" + p[3:]
    shutil.copyfile(p, raw / f"{brief}_{arm}_{name}.png")
n = math.sqrt(0.7 ** 2 * 2 + 0.55 ** 2)
for name, sx, sz in (("se", 1, 1), ("nw", -1, -1)):
    eye = (c[0] + sx * 0.7 / n * D, c[1] + 0.55 / n * D, c[2] + sz * 0.7 / n * D)
    shot(name, eye, c)
# street level: south face (+z), eye 2.6 above ground (build floor), distance ~ 0.9 * footprint depth + 10
dist = max(ext[0], ext[2]) * 0.6 + 10
shot("street", (c[0], lo[1] + 2.6, hi[2] + dist), (c[0], lo[1] + ext[1] * 0.3, c[2]))
m.call("ghost_camera", {"off": True})
json.dump({"lo": lo, "hi": hi, "blocks": blocks, "ghosts": len(ghosts), "D": round(D, 1)}, open(raw / f"{brief}_{arm}.json", "w"))
print("ok", lo, hi, blocks, round(D, 1))
