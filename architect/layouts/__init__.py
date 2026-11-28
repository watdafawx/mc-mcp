"""Horizontal mod campuses with style-specific plans (the former architect/campus.py monolith, split by layout).

Spine uses enclosed galleries; radial, cloister, linear and terraces use level outdoor promenades. Each wing retains its
room program and only the landmark rises above the low working ranges. Returned ghost origins are site offsets.

    layouts.build(kit, wings, home, landmark, roles, seed, layout)   -> ghost list
    layouts.LAYOUTS                                                 -> {"spine": spine.build, "radial": ..., ...}

Every layout module exposes build(kit, wings, home, landmark, roles, seed); shared constants and kit tables (read from
kits.json through palettes.py) live in layouts.common. No module keeps mutable global state between builds.
"""
from __future__ import annotations

from . import cloister, common, linear, radial, spine, terraces
from .common import (ALT_ROOF, DEFAULT_LAYOUT, GAP, GD, GLASS, HALL_STYLE, HUB, HUB_ROOF, LAYOUT_NAMES, RISE, ROOF_CYCLE,
                     ROOF_MATS, SIZES, STEPS, TOWER_ROOF, _feature_mod_wings, summary)

LAYOUTS = {"spine": spine.build, "radial": radial.build, "cloister": cloister.build, "linear": linear.build,
           "terraces": terraces.build}
assert tuple(LAYOUTS) == LAYOUT_NAMES

__all__ = ["ALT_ROOF", "DEFAULT_LAYOUT", "GAP", "GD", "GLASS", "HALL_STYLE", "HUB", "HUB_ROOF", "LAYOUTS", "LAYOUT_NAMES",
           "RISE", "ROOF_CYCLE", "ROOF_MATS", "SIZES", "STEPS", "TOWER_ROOF", "build", "common", "summary"]


def build(kit="hextech", wings=None, home=True, landmark="tower", roles=None, seed=1, layout=None):
    """Style-specific horizontal campuses. layout overrides the kit's default archetype."""
    layout = layout or DEFAULT_LAYOUT.get(kit, "spine")
    wings = _feature_mod_wings(wings or [], layout, home)
    if layout not in LAYOUTS:
        raise ValueError("unknown layout: " + str(layout))
    return LAYOUTS[layout](kit, wings, home, landmark, roles, seed)
