"""Backwards-compatible entry point for the campus generator.

The 2,500-line monolith was split into the architect/layouts/ package (one module per layout plus shared helpers);
this module keeps the old import surface so `import campus; campus.build(...)` and the constants other modules and
tests read keep working. New code should import `layouts` directly.
"""
from __future__ import annotations

import layouts
from layouts import (ALT_ROOF, GAP, GD, GLASS, HALL_STYLE, HUB, HUB_ROOF, LAYOUT_NAMES, LAYOUTS as LAYOUT_BUILDERS, RISE,
                     ROOF_CYCLE, ROOF_MATS, SIZES, STEPS, TOWER_ROOF, build, summary)
from layouts.common import DEFAULT_LAYOUT as LAYOUTS  # kit -> default layout name (the old campus.LAYOUTS)

__all__ = ["ALT_ROOF", "GAP", "GD", "GLASS", "HALL_STYLE", "HUB", "HUB_ROOF", "LAYOUTS", "LAYOUT_BUILDERS", "LAYOUT_NAMES",
           "RISE", "ROOF_CYCLE", "ROOF_MATS", "SIZES", "STEPS", "TOWER_ROOF", "build", "layouts", "summary"]
