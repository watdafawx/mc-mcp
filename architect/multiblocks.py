"""Rule-checked generators for mod multiblocks (ATM10: AE2 19.2, ExtendedAE 2.2, AdvancedAE 1.6).

Each generator returns a ghost spec {palette, boxes, blocks} in local coordinates starting at 0,0,0, so the
result is valid by construction. Rules come from the mods' own guide pages (ae2guide/*.md in the jars).
"""

from __future__ import annotations


class MultiblockError(ValueError):
    pass


# ---------------------------------------------------------------------------------------- AE2 controller

def controller_frame(size: int = 7) -> dict:
    """Hollow cube made of only its 12 edges. Valid AE2 controller for any size 2..7."""
    if not 2 <= size <= 7:
        raise MultiblockError("controller must fit in 7x7x7 (size 2..7)")
    n = size - 1
    return {"palette": {"C": "ae2:controller"}, "boxes": [[0, 0, 0, n, n, n, "C", "frame"]], "blocks": []}


def controller_column(height: int = 7) -> dict:
    if not 1 <= height <= 7:
        raise MultiblockError("controller column height 1..7")
    return {"palette": {"C": "ae2:controller"}, "boxes": [[0, 0, 0, 0, height - 1, 0, "C"]], "blocks": []}


def check_controller(cells: set[tuple[int, int, int]]) -> list[str]:
    """AE2 rules: one connected group, inside 7x7x7, and no block has neighbours on both sides along 2+ axes."""
    errs = []
    if not cells:
        return ["no blocks"]
    for axis in range(3):
        span = max(c[axis] for c in cells) - min(c[axis] for c in cells) + 1
        if span > 7:
            errs.append(f"span {span} on axis {'xyz'[axis]} exceeds 7")
    for (x, y, z) in cells:
        both = [(x - 1, y, z) in cells and (x + 1, y, z) in cells,
                (x, y - 1, z) in cells and (x, y + 1, z) in cells,
                (x, y, z - 1) in cells and (x, y, z + 1) in cells]
        if sum(both) > 1:
            errs.append(f"block {x},{y},{z} has neighbours on both sides along {sum(both)} axes (turns red)")
            if len(errs) > 8:
                break
    start = next(iter(cells))
    seen, todo = {start}, [start]
    while todo:
        x, y, z = todo.pop()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + d[0], y + d[1], z + d[2])
            if n in cells and n not in seen:
                seen.add(n)
                todo.append(n)
    if len(seen) != len(cells):
        errs.append("controller blocks are not all connected")
    return errs


# ---------------------------------------------------------------------------- AdvancedAE quantum computer

def quantum_computer(size: int = 5, accelerator_share: float = 0.5, entangler: bool = True,
                     multi_threader: bool = True, storage: str = "advanced_ae:quantum_storage_256") -> dict:
    """Solid cube: shell of quantum_structure, exactly one core in the middle, at most one data entangler and one
    multi-threader, the rest accelerators and storage. size 3..7 (3 = just the core inside)."""
    if not 3 <= size <= 7:
        raise MultiblockError("quantum computer size 3..7")
    if storage not in ("advanced_ae:quantum_storage_128", "advanced_ae:quantum_storage_256", "advanced_ae:quantum_unit"):
        raise MultiblockError("storage must be quantum_storage_128, quantum_storage_256 or quantum_unit")
    n = size - 1
    pal = {"S": "advanced_ae:quantum_structure", "K": "advanced_ae:quantum_core", "E": "advanced_ae:data_entangler",
           "T": "advanced_ae:quantum_multi_threader", "A": "advanced_ae:quantum_accelerator", "M": storage,
           "U": "advanced_ae:quantum_unit"}
    boxes = [[0, 0, 0, n, n, n, "S", "hollow"]]
    inner = [(x, y, z) for y in range(1, n) for z in range(1, n) for x in range(1, n)]
    c = n // 2
    core = (c, c, c)
    rest = [p for p in inner if p != core]
    blocks = [[*core, "K"]]
    specials = []
    if entangler:
        specials.append("E")
    if multi_threader:
        specials.append("T")
    for key in specials:
        if rest:
            blocks.append([*rest.pop(0), key])
    n_acc = round(len(rest) * max(0.0, min(1.0, accelerator_share)))
    # Interleave so both kinds show through any cut-away; accelerators first.
    for i, p in enumerate(rest):
        blocks.append([*p, "A" if (i * n_acc) // max(1, len(rest)) != ((i + 1) * n_acc) // max(1, len(rest)) else "M"])
    if not rest and size == 3:
        pass
    return {"palette": pal, "boxes": boxes, "blocks": blocks}


# --------------------------------------------------------------------------- ExtendedAE assembler matrix

def assembler_matrix(sx: int = 7, sy: int = 7, sz: int = 7, speed: int = 5, pattern_share: float = 0.33,
                     faces: str = "glass") -> dict:
    """Solid box 3..7 per side: frame on the 12 edges, wall/glass on faces, cores inside.
    Needs >= 1 pattern core and >= 1 crafter core; more than 5 speed cores add nothing.
    faces: glass | wall | window (glass centre, wall border) | checker."""
    for v in (sx, sy, sz):
        if not 3 <= v <= 7:
            raise MultiblockError("assembler matrix sides must be 3..7")
    inner = [(x, y, z) for y in range(1, sy - 1) for z in range(1, sz - 1) for x in range(1, sx - 1)]
    if len(inner) < 2:
        raise MultiblockError("interior must hold at least one pattern core and one crafter core (e.g. 3x3x4)")
    pal = {"F": "extendedae:assembler_matrix_frame", "W": "extendedae:assembler_matrix_wall",
           "G": "extendedae:assembler_matrix_glass", "P": "extendedae:assembler_matrix_pattern",
           "C": "extendedae:assembler_matrix_crafter", "V": "extendedae:assembler_matrix_speed"}
    X, Y, Z = sx - 1, sy - 1, sz - 1
    face_key = {"glass": "G", "wall": "W"}.get(faces, "W")
    boxes = [[0, 0, 0, X, Y, Z, face_key, "hollow"]]
    blocks = []
    if faces in ("window", "checker"):
        for (x, y, z) in ((x, y, z) for x in range(sx) for y in range(sy) for z in range(sz)):
            on_face = x in (0, X) or y in (0, Y) or z in (0, Z)
            if not on_face:
                continue
            if faces == "window":
                # glass in the middle of each face, a ring of wall next to the frame
                in_face = [(v, m) for v, m in ((x, X), (y, Y), (z, Z)) if v not in (0, m)]
                if len(in_face) == 2 and all(2 <= v <= m - 2 for v, m in in_face):
                    blocks.append([x, y, z, "G"])
            elif (x + y + z) % 2 == 0:
                blocks.append([x, y, z, "G"])
    boxes.append([0, 0, 0, X, Y, Z, "F", "frame"])  # after faces so edges win
    n_speed = min(max(0, speed), 5, len(inner) - 2)
    n_pattern = max(1, round((len(inner) - n_speed) * pattern_share))
    n_pattern = min(n_pattern, len(inner) - n_speed - 1)
    # Put speed cores in the middle, patterns next, crafters outward (crafters are the ones you see through glass).
    cx, cy, cz = X / 2, Y / 2, Z / 2
    order = sorted(inner, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2)
    for i, p in enumerate(order):
        key = "V" if i < n_speed else "P" if i < n_speed + n_pattern else "C"
        blocks.append([*p, key])
    # Frame box must be applied after the window/checker glass blocks too: re-add edges as blocks.
    if faces in ("window", "checker"):
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    if [x in (0, X), y in (0, Y), z in (0, Z)].count(True) >= 2:
                        blocks.append([x, y, z, "F"])
    return {"palette": pal, "boxes": boxes, "blocks": blocks,
            "info": {"speed": n_speed, "pattern": n_pattern, "crafter": len(inner) - n_speed - n_pattern,
                     "pattern_slots": n_pattern * 36, "parallel_jobs": (len(inner) - n_speed - n_pattern) * 8}}


# ------------------------------------------------------------------------------------ composed presets

def merge(*parts: tuple[dict, tuple[int, int, int]]) -> dict:
    """Combine specs at offsets into one spec, renaming palette keys to stay unique."""
    out = {"palette": {}, "boxes": [], "blocks": []}
    for i, (spec, (ox, oy, oz)) in enumerate(parts):
        rename = {}
        for k, v in spec["palette"].items():
            nk = f"{k}{i}"
            rename[k] = nk
            out["palette"][nk] = v
        for b in spec.get("boxes", []):
            out["boxes"].append([b[0] + ox, b[1] + oy, b[2] + oz, b[3] + ox, b[4] + oy, b[5] + oz, rename[b[6]], *b[7:]])
        for b in spec.get("blocks", []):
            out["blocks"].append([b[0] + ox, b[1] + oy, b[2] + oz, rename[b[3]]])
    return out


def trinity_core(matrix_faces: str = "window") -> dict:
    """Assembler matrix | 7^3 controller cage around a 5^3 quantum computer | assembler matrix, all touching
    along X (21 x 7 x 7), so every part joins one ME network without cables."""
    cage = controller_frame(7)
    qc = quantum_computer(5)
    left = assembler_matrix(7, 7, 7, faces=matrix_faces)
    right = assembler_matrix(7, 7, 7, faces=matrix_faces)
    return merge((left, (0, 0, 0)), (cage, (7, 0, 0)), (qc, (8, 1, 1)), (right, (14, 0, 0)))


CPU_FAMILIES = {
    "ae2": {"unit": "ae2:crafting_unit", "acc": ["ae2:crafting_accelerator"], "mon": "ae2:crafting_monitor",
            "store": ["ae2:1k_crafting_storage", "ae2:4k_crafting_storage", "ae2:16k_crafting_storage",
                      "ae2:64k_crafting_storage", "ae2:256k_crafting_storage"]},
    "expandedae": {"unit": "expandedae:exp_crafting_unit", "mon": None,
                   "acc": [f"expandedae:exp_crafting_accelerator_{n}" for n in (2, 4, 8, 16, 32, 64, 128, 256, 512)],
                   "store": [f"expandedae:exp_crafting_accelerator_{n}" for n in
                             ("1k", "2k", "4k", "8k", "16k", "32k", "64k", "128k", "256k", "512k", "1m")]},
    "megacells": {"unit": "megacells:mega_crafting_unit", "acc": ["megacells:mega_crafting_accelerator"],
                  "mon": "megacells:mega_crafting_monitor",
                  "store": ["megacells:1m_crafting_storage", "megacells:4m_crafting_storage",
                            "megacells:16m_crafting_storage", "megacells:64m_crafting_storage",
                            "megacells:256m_crafting_storage"]},
}


def crafting_cpu(family: str = "ae2", sx: int = 3, sy: int = 3, sz: int = 3, storage: str | None = None,
                 accelerators: list | None = None, accelerator_share: float = 0.4, monitor: bool = True) -> dict:
    """Crafting CPU: a solid box (edges 1..16) of one family's crafting blocks with at least one storage block.
    family ae2 | expandedae | megacells. storage: a block id from the family (default the 2nd tier).
    accelerators: co-processor ids to cycle through (ExpandedAE tiers, e.g. [..._16, ..._64, ..._256]).
    monitor: a monitor in the middle of the south face (ae2/megacells only). Layered so tiers show in cutaways."""
    if family not in CPU_FAMILIES:
        raise MultiblockError(f"family one of {sorted(CPU_FAMILIES)}")
    if not all(1 <= v <= 16 for v in (sx, sy, sz)):
        raise MultiblockError("crafting CPU edges 1..16")
    f = CPU_FAMILIES[family]
    store = storage or f["store"][min(1, len(f["store"]) - 1)]
    if store not in f["store"]:
        raise MultiblockError(f"storage must be one of {f['store']}")
    accs = accelerators or f["acc"][:1]
    for a in accs:
        if a not in f["acc"]:
            raise MultiblockError(f"accelerators must be from {f['acc']}")
    cells = [(x, y, z) for y in range(sy) for z in range(sz) for x in range(sx)]
    c = (sx // 2, sy // 2, sz // 2)
    pal = {"U": f["unit"], "S": store}
    for i, a in enumerate(accs):
        pal[f"A{i}"] = a
    blocks = []
    mon = (sx // 2, sy // 2, sz - 1) if monitor and f["mon"] else None
    if mon:
        pal["M"] = f["mon"]
    n_acc = round((len(cells) - 1) * max(0.0, min(1.0, accelerator_share)))
    k = 0
    for i, p in enumerate(cells):
        if p == c:
            key = "S"
        elif p == mon:
            key = "M"
        elif k < n_acc and (i * n_acc) // len(cells) != ((i + 1) * n_acc) // len(cells):
            key = f"A{(p[1]) % len(accs)}"
            k += 1
        else:
            key = "S" if (p[0] + p[1] + p[2]) % 3 == 0 else "U"
        blocks.append([*p, key])
    return {"palette": pal, "boxes": [], "blocks": blocks,
            "info": f"{family} CPU {sx}x{sy}x{sz}: storage {store}, co-processors {accs}"}


KINDS = {
    "crafting_cpu": crafting_cpu,
    "controller_frame": controller_frame,
    "controller_column": controller_column,
    "quantum_computer": quantum_computer,
    "assembler_matrix": assembler_matrix,
    "trinity_core": trinity_core,
}


def build(kind: str, **opts) -> dict:
    if kind not in KINDS:
        raise MultiblockError(f"unknown kind {kind}; one of {sorted(KINDS)}")
    spec = KINDS[kind](**opts)
    if kind.startswith("controller"):
        cells = set()
        for b in spec["boxes"]:
            x1, y1, z1, x2, y2, z2 = b[:6]
            mode = b[7] if len(b) > 7 else "fill"
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    for z in range(z1, z2 + 1):
                        e = [x in (x1, x2), y in (y1, y2), z in (z1, z2)].count(True)
                        if mode == "fill" or (mode == "frame" and e >= 2):
                            cells.add((x, y, z))
        errs = check_controller(cells)
        if errs:
            raise MultiblockError("; ".join(errs))
    return spec


if __name__ == "__main__":
    import json
    t = trinity_core()
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in t.items()}))
    print(assembler_matrix()["info"])
