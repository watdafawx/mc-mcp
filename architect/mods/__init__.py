"""Per-mod room registry. One small file per mod; each defines ROOM (a ModRoom).

A campus wing room `mod_room:<theme>` whose theme is registered here gets:
  * a deterministic fit-out in interiors.py (pad blocks + centrepiece machines from `pieces`),
  * the mod's block whitelist in the agent's `blocks` tool, bypassing the cost filter (mod machines have no recipe cost),
  * the room brief in the agent prompt.
Everything else keeps the cheap-survival default (blocks tool cost filter, max_cost) untouched.

Piece kinds (interiors._mod_piece), all anchored on the 5x5 pad centre:
  ("single", block)                  one block on the pad centre
  ("stack", block, n)                column n high
  ("cube", casing, glass, core)      3x3x3 shell: casing, glass window row (middle layer faces), core block inside
  ("tower", casing, glass, n)        3x3 footprint, n high: casing corners/edges, glass faces (unformed multiblock look)
  ("group", (dx, dz, piece), ...)    sub-pieces at offsets from the pad centre (a cluster, plinth 7x7: offsets within +-3)
  ("gear", casing, shaft, cog, large) Create gear train: 3 casing pillars, shaft run, large + small cogwheels, vertical drive
  ("kgear", casing)                  REAL Create gear train (large/small/large cogwheels, axis z) with shafts, bearings, gearbox
  ("kwheel", casing)                 REAL Create large water wheel (axis x) on a shaft between two casing pillars
  ("kbelt", n, end_block)            REAL Create belt along x (2n+1, start/middle/end), end blocks at both ends
  ("field", farmland, (crop, ...), n, age)  (2n+1)^2 farmland with crops (age state added) on top (v27)
  ("blob", block, r, dy)             solid ball of radius r centred dy above the floor (a leaf crown) (v27)
  ("ring", (b1, b2, ...), r)         square perimeter at distance r on the floor, blocks cycling (chalk circle) (v27)
  extra={"gate": (post, cap, lintel, lamp)}  eye-level arches in the aisles between plinths (interiors._mod_gates) (v27)
  ("gear"/"cog"/"belt", ...)         fake (vanilla-block) versions, the fallback when a block-entity block does not draw
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModRoom:
    theme: str                  # mod_room:<theme> and registry key (the mod id)
    name: str                   # display name
    namespaces: tuple           # block namespaces covered
    blocks: tuple               # explicit whitelist of real block ids (all must have a texture)
    brief: str                  # one line: what the room looks like
    style: str                  # best-fit style kit
    alt_styles: tuple = ()
    pad: tuple = ("", "")       # (border, centre) pad blocks for the pads
    deck: str = ""              # v23: contrasting floor over the whole room (light under dark machines, dark under light)
    plinth: tuple = ()          # v23: (ring, field) blocks of the 7x7 plinths under each centrepiece cluster
    ring_dash: bool = False     # ring alternates ring/field blocks (a dashed lit strip)
    pieces: tuple = ()          # centrepieces cycled over the pads (see module doc)
    wall: tuple = ()            # wall machines along the room edges (default: the single pieces)
    ghost_rules: str = ""       # ghost-rendering limits for this mod
    extra: dict = field(default_factory=dict)


REGISTRY: dict[str, ModRoom] = {}


def register_signage(theme: str, emblem, band: tuple):
    """v28: facade signage for a batch-3 mod, registered by its own module file (signs.py keeps the batch-1/2 tables):
    `emblem` is a signs-style emblem cell function, `band` the (a, b) block ids of the three-row lintel band."""
    from .signs import BANDS, EMBLEMS
    EMBLEMS.setdefault(theme, emblem)
    BANDS.setdefault(theme, band)


def _load():
    from . import (mekanism, powah, bigreactors, create, industrialforegoing, ars_nouveau, occultism,
                   mysticalagriculture, productivebees, enderio, modern_industrialization, immersiveengineering,
                   draconicevolution, evilcraft, functionalstorage)
    for m in (mekanism, powah, bigreactors, create, industrialforegoing, ars_nouveau, occultism, mysticalagriculture,
              productivebees, enderio, modern_industrialization, immersiveengineering, draconicevolution, evilcraft,
              functionalstorage):
        REGISTRY[m.ROOM.theme] = m.ROOM


_load()


def get(theme: str) -> ModRoom | None:
    return REGISTRY.get(theme)


def whitelist(themes) -> list[str]:
    seen, out = set(), []
    for t in themes:
        r = REGISTRY.get(t)
        for b in (r.blocks if r else ()):
            if b not in seen:
                seen.add(b)
                out.append(b)
    return out


def themes_in(wings) -> list[str]:
    """Registered themes used by `mod_room:<theme>` rooms in a campus wings list (rooms and upper)."""
    found = []
    for w in wings or []:
        for key in ("rooms", "upper"):
            for r in w.get(key) or []:
                k, _, th = str(r).partition(":")
                if k == "mod_room" and th in REGISTRY and th not in found:
                    found.append(th)
    return found


def prompt_note(theme: str) -> str:
    r = REGISTRY[theme]
    return (f"MOD ROOM {r.name} (mod_room:{r.theme}, style fit {r.style}): {r.brief}\n"
            f"Ghost limits: {r.ghost_rules}\n"
            f"Allowed {r.name} blocks (cost filter bypassed, use these exact ids; blocks(mod='{r.theme}') shows textures): "
            + ", ".join(b.split(":", 1)[1] for b in r.blocks) + f"  [namespace(s): {', '.join(r.namespaces)}]. "
            "Everything else stays cheap survival blocks.")
