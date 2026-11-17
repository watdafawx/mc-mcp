"""Check AE2-family multiblocks in an exported build against their formation rules.

    python validate.py build.litematic [--json]

Finds every connected group of multiblock parts and checks it:
- AE2 controller: inside 7x7x7, connected, no block with neighbours on both sides along 2+ axes.
- Crafting CPU (AE2, ExpandedAE, MEGA parts): solid rectangular prism, at least one storage block, edges <= 16.
- AdvancedAE quantum computer: solid prism <= 7, shell all quantum_structure, none inside, exactly one core,
  at most one entangler and one multi-threader.
- ExtendedAE assembler matrix: solid prism 3..7 per edge, frame on the 12 edges, wall/glass on faces, cores inside,
  at least one pattern core and one crafter core.
- AE2 quantum bridge: quantum_link with 8 quantum_ring around it in a flat 3x3.
Also counts blocks per mod, so a build can be scored on how much of the requested gear it actually has.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from multiblocks import check_controller

Cell = tuple[int, int, int]


def load(path: str | Path) -> dict[Cell, str]:
    from litemapy import Schematic
    sch = Schematic.load(str(path))
    cells: dict[Cell, str] = {}
    for reg in sch.regions.values():
        ox, oy, oz = reg.x, reg.y, reg.z
        for x in reg.range_x() if hasattr(reg, "range_x") else reg.xrange():
            for y in reg.range_y() if hasattr(reg, "range_y") else reg.yrange():
                for z in reg.range_z() if hasattr(reg, "range_z") else reg.zrange():
                    bid = reg[x, y, z].id
                    if bid not in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
                        cells[(ox + x, oy + y, oz + z)] = bid
    return cells


def groups(cells: dict[Cell, str], pred) -> list[set[Cell]]:
    pts = {p for p, b in cells.items() if pred(b)}
    out, seen = [], set()
    for p in pts:
        if p in seen:
            continue
        g, todo = {p}, [p]
        seen.add(p)
        while todo:
            x, y, z = todo.pop()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (x + d[0], y + d[1], z + d[2])
                if n in pts and n not in seen:
                    seen.add(n)
                    g.add(n)
                    todo.append(n)
        out.append(g)
    return out


def box(g: set[Cell]):
    lo = [min(c[i] for c in g) for i in range(3)]
    hi = [max(c[i] for c in g) for i in range(3)]
    return lo, hi, [hi[i] - lo[i] + 1 for i in range(3)]


def solid(g: set[Cell]) -> bool:
    _, _, s = box(g)
    return len(g) == s[0] * s[1] * s[2]


def where(cells_map, kinds):
    return ", ".join(f"{k}" for k in kinds)


CPU_RE = re.compile(r"^(ae2:(crafting_unit|crafting_accelerator|crafting_monitor|\d+k_crafting_storage)"
                    r"|expandedae:exp_crafting_\w+"
                    r"|megacells:(mega_crafting_\w+|\d+m_crafting_storage))$")
CPU_STORAGE = re.compile(r"(_crafting_storage$|expandedae:exp_crafting_accelerator_\d+[km]$)")


def check(cells: dict[Cell, str]) -> dict:
    res = {"blocks": len(cells), "mods": dict(Counter(b.split(":")[0] for b in cells.values()).most_common()),
           "multiblocks": []}

    def add(kind, g, errs, extra=None):
        lo, _, s = box(g)
        res["multiblocks"].append({"kind": kind, "at": lo, "size": s, "blocks": len(g), "ok": not errs,
                                   "errors": errs[:6], **(extra or {})})

    for g in groups(cells, lambda b: b == "ae2:controller"):
        add("ae2_controller", g, check_controller(g))

    for g in groups(cells, lambda b: bool(CPU_RE.match(b))):
        errs = []
        ids = Counter(cells[c] for c in g)
        if not solid(g):
            errs.append(f"not a solid prism ({len(g)} blocks in a {box(g)[2]} box)")
        if max(box(g)[2]) > 16:
            errs.append(f"edge {max(box(g)[2])} > 16")
        if not any(CPU_STORAGE.search(b) for b in ids):
            errs.append("no crafting storage block")
        fams = {b.split(":")[0] for b in ids}
        add("crafting_cpu", g, errs, {"families": sorted(fams)})

    for g in groups(cells, lambda b: b.startswith("advanced_ae:quantum_") and b not in (
            "advanced_ae:quantum_alloy_block", "advanced_ae:quantum_alloy_stairs", "advanced_ae:quantum_alloy_slab",
            "advanced_ae:quantum_alloy_wall", "advanced_ae:quantum_crafter")
            or b in ("advanced_ae:data_entangler", "advanced_ae:quantum_multi_threader")):
        errs = []
        lo, hi, s = box(g)
        if not solid(g):
            errs.append(f"not a solid prism ({len(g)} blocks in {s})")
        if max(s) > 7:
            errs.append(f"edge {max(s)} > 7")
        ids = Counter(cells[c] for c in g)
        if ids["advanced_ae:quantum_core"] != 1:
            errs.append(f"{ids['advanced_ae:quantum_core']} quantum cores (need exactly 1)")
        for one in ("advanced_ae:data_entangler", "advanced_ae:quantum_multi_threader"):
            if ids[one] > 1:
                errs.append(f"{ids[one]} x {one} (max 1)")
        if len(g) > 1:
            for c in g:
                shell = any(c[i] in (lo[i], hi[i]) for i in range(3))
                st = cells[c] == "advanced_ae:quantum_structure"
                if shell and not st:
                    errs.append(f"shell block {c} is {cells[c]}, must be quantum_structure")
                elif st and not shell:
                    errs.append(f"quantum_structure inside at {c}")
                if len(errs) > 6:
                    break
        add("quantum_computer", g, errs)

    for g in groups(cells, lambda b: b.startswith("extendedae:assembler_matrix_")):
        errs = []
        lo, hi, s = box(g)
        if not solid(g):
            errs.append(f"not a solid prism ({len(g)} blocks in {s})")
        if min(s) < 3 or max(s) > 7:
            errs.append(f"size {s} outside 3..7")
        ids = Counter(cells[c] for c in g)
        for core in ("pattern", "crafter"):
            if ids[f"extendedae:assembler_matrix_{core}"] < 1:
                errs.append(f"no {core} core")
        for c in g:
            on = sum(c[i] in (lo[i], hi[i]) for i in range(3))
            b = cells[c].split("_matrix_")[1]
            want = {0: ("pattern", "crafter", "speed"), 1: ("wall", "glass")}.get(on, ("frame",))
            if b not in want:
                errs.append(f"{c} is {b}, expected {'/'.join(want)}")
            if len(errs) > 6:
                break
        add("assembler_matrix", g, errs)

    for c, b in cells.items():
        if b == "ae2:quantum_link":
            x, y, z = c
            ok = False
            for ax in range(3):  # ring plane is perpendicular to axis ax
                ring = []
                for a in (-1, 0, 1):
                    for bb in (-1, 0, 1):
                        if a == bb == 0:
                            continue
                        d = [a, bb]
                        d.insert(ax, 0)
                        ring.append((x + d[0], y + d[1], z + d[2]))
                if all(cells.get(r) == "ae2:quantum_ring" for r in ring):
                    ok = True
            add("quantum_bridge", {c}, [] if ok else ["quantum_link without a full 3x3 ring of quantum_ring"])

    mb = res["multiblocks"]
    res["summary"] = {k: f"{sum(m['ok'] for m in mb if m['kind'] == k)}/{sum(m['kind'] == k for m in mb)} valid"
                      for k in sorted({m["kind"] for m in mb})}
    return res


def main():
    r = check(load(sys.argv[1]))
    if "--json" in sys.argv:
        print(json.dumps(r, indent=1))
        return
    print(f"{r['blocks']} blocks; mods: {r['mods']}")
    for k, v in r["summary"].items():
        print(f"  {k}: {v}")
    for m in r["multiblocks"]:
        if not m["ok"]:
            print(f"  BAD {m['kind']} at {m['at']} size {m['size']}: {'; '.join(m['errors'])}")


if __name__ == "__main__":
    main()
