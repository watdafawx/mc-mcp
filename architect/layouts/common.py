"""Shared constants, kit tables and small helpers for the campus layouts.

Kit tables (roof cycle, roof materials, glass cycle, ...) come from kits.json through palettes.py; nothing here keeps
mutable module state, so builds are independent of each other and of call order.
"""
from __future__ import annotations

import shapes  # noqa: F401  (loads massing in the right order)

import massing
import palettes
import services

SIZES = {"s": (19, 25), "m": (23, 31), "l": (29, 41), "x": (37, 49)}  # wing width (along the gallery) x depth
GAP = 7  # courtyard between wings
GD = 11  # gallery depth
HUB = 33  # hub octagon size
STEPS = 2  # platform height; buildings stand on y=STEPS
RISE = 5  # terrace tier height
N4 = massing.N4

# default archetype per kit (a kit not listed here gets "spine"); build(layout=...) overrides it
DEFAULT_LAYOUT = {"steampunk": "spine", "hextech": "radial", "gothic": "cloister",
                  "station_white": "linear", "solarpunk": "terraces"}
LAYOUT_NAMES = ("spine", "radial", "cloister", "linear", "terraces")


# ------------------------------------------------------------------------------------------ kit tables (kits.json)
def _meta_table(key: str) -> dict:
    """{kit: meta[key]} for every kit in kits.json that defines `key`."""
    return {name: kit["meta"][key] for name, kit in palettes.load_kits()["kits"].items() if key in (kit.get("meta") or {})}


ALT_ROOF = _meta_table("alt_roof")      # second roof shape per kit, used on every other wing
TOWER_ROOF = _meta_table("tower_roof")  # roof of the landmark's top stage
HUB_ROOF = _meta_table("hub_roof")      # roof of the hub octagon
HALL_STYLE = _meta_table("hall_style")  # promenade style ("open" arcades for gothic, else glazed)
ROOF_CYCLE = _meta_table("roof_cycle")  # 7 distinct forms per kit, so neighbouring wings never share a roof form
# roof material per wing (cycled): the preferred block of every chain (no registry here), the tower keeps the kit roof
ROOF_MATS = {name: palettes.resolve_list(chains) for name, chains in _meta_table("roof_mats").items()}
# glass colour cycle per kit, as colour names ("light_blue" -> minecraft:light_blue_stained_glass)
GLASS = {name: [g.split(":")[-1].removesuffix("_stained_glass") for g in cycle]
         for name, cycle in _meta_table("glass_cycle").items()}
# per-kit role overrides applied to every wing unless the wing sets its own (gothic: pale stone walls)
WING_ROLES = {name: palettes.resolve_meta(name)["wing_roles"] for name in _meta_table("wing_roles")}

FLOWERS = ("minecraft:poppy", "minecraft:dandelion", "minecraft:allium", "minecraft:oxeye_daisy", "minecraft:cornflower",
           "minecraft:azure_bluet", "minecraft:lily_of_the_valley")
HEDGE = "minecraft:azalea_leaves[persistent=true]"
BLOOM = "minecraft:flowering_azalea_leaves[persistent=true]"
LEAF = "minecraft:azalea_leaves[persistent=true]"
LEAFWALL = "minecraft:azalea_leaves[persistent=true]"


def _wood(K, kit):
    import interiors
    return K.get("wood") or interiors.WOOD.get(kit if isinstance(kit, str) else "", "oak")


def _tree(out, x, z, y, wood, rnd=0, kit=""):
    """A small tree on (x, z); solarpunk gets the thin, airy crown. The kit is passed in, never read from global state."""
    h = 5 + rnd % 2
    thin = kit == "solarpunk"
    for dy in range(h):
        out.append([x, y + dy, z, f"minecraft:{wood}_log[axis=y]"])
    leaf = "minecraft:" + {"dark_oak": "dark_oak_leaves", "spruce": "spruce_leaves", "birch": "birch_leaves"}.get(
        wood, "oak_leaves") + "[persistent=true]"
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            for dy in range(h - 1 if thin else h - 2, h + (1 if thin else 2)):
                r = abs(dx) + abs(dz) + max(0, dy - h)
                if r <= (2 if thin else 3) and not (dx == 0 and dz == 0 and dy < h):
                    out.append([x + dx, y + dy, z + dz, leaf])


def _lamp(out, x, z, y, K):
    for dy in range(3):
        out.append([x, y + dy, z, K["rail"]])
    out.append([x, y + 3, z, K["glow"]])
    out.append([x, y + 4, z, K["trim"]])




def _cells(x, z, w, d):
    return {(a, b) for a in range(x, x + w) for b in range(z, z + d)}


def _expand(centres, r=2):
    return {(a + i, b + j) for a, b in centres for i in range(-r, r + 1) for j in range(-r, r + 1)}


def _roof_for(wing, kit, i):
    cyc = ROOF_CYCLE.get(kit if isinstance(kit, str) else "", ["flat", "crown"])
    if kit == "solarpunk" and i == 2:  # v19b: guarantee one flat wing so _solar_deck (pergola, planters) is built
        return "flat"
    return wing.get("roof") or cyc[i % len(cyc)]


def _windows(kit, i):
    return "lancet" if kit in ("gothic", "hextech") else ("grid" if i % 2 else "band")


def _dims(w):
    """(w, d) of a wing: explicit dims (mod wings sized from their machine count) or the size letter."""
    d = w.get("dims")
    return tuple(d) if d else SIZES.get(str(w.get("size", "m"))[:1], SIZES["m"])


def _rooms_door_first(rooms, door, w, d):
    """Mod rooms first, and the end of the long axis that holds them next to the door (port wall faces the hub)."""
    rooms = list(rooms or [])
    mods = [r for r in rooms if str(r).startswith("mod_room")]
    rest = [r for r in rooms if r not in mods]
    rooms = mods + rest
    long_x = w >= d
    if (long_x and door == "e") or (not long_x and door == "s"):
        rooms = rooms[::-1]
    return rooms


def _plan_sizes(wings):
    return [_dims(w) for w in wings]


def with_home(wings, home):
    """The wing list a non-spine layout builds: the home wing first when asked, a lone mod room when nothing is listed."""
    wings = list(wings or [])
    if home:
        wings.insert(0, {"name": "home", "rooms": ["living", "living", "workshop", "storage"]})
    return wings or [{"name": "machines", "rooms": ["mod_room", "expansion"]}]


def _is_mod_wing(w):
    try:
        import mods
    except ImportError:
        return False
    for key in ("rooms", "upper"):
        for r in w.get(key) or []:
            k, _, th = str(r).partition(":")
            if k == "mod_room" and th in mods.REGISTRY:
                return True
    return False


def _wing_mod(w):
    """The registered mod theme of a wing's first mod_room, or None."""
    try:
        import mods
    except ImportError:
        return None
    for key in ("rooms", "upper"):
        for r in w.get(key) or []:
            k, _, th = str(r).partition(":")
            if k == "mod_room" and th in mods.REGISTRY:
                return th
    return None


def _feature_mod_wings(wings, layout, home):
    """v23: the first wing with a registered mod room becomes the showpiece: size x (37x49), one tall floor, big-pane
    windows, and never wing 0 of the linear layout (that slot is the habitat ring round the hub, which swallowed it)."""
    wings = [dict(w) for w in wings]
    idx = next((i for i, w in enumerate(wings) if _is_mod_wing(w)), None)
    if idx is None:
        return wings
    for v in wings:  # v28: every mod wing is sized from its machine count (floor area ~ clusters x footprint + services)
        if _is_mod_wing(v):
            v["dims"] = services.size_for(services.machine_count(v, _wing_mod(v)))
            v["floors"] = 1
            v["floor_h"] = max(int(v.get("floor_h") or 0), 12)
            v.setdefault("windows", "grid")
    w = wings[idx]
    w["size"] = "x"
    if layout == "linear" and idx == 0 and not home:
        other = next((i for i, v in enumerate(wings) if i and not _is_mod_wing(v)), None)
        if other is None:
            wings.insert(0, {"name": "habitat", "rooms": ["living", "workshop"], "upper": ["living", "storage"]})
        else:
            wings[0], wings[other] = wings[other], wings[0]
    return wings


def summary(ghosts: list, wings: list) -> dict:
    xs = [g["origin"][0] for g in ghosts]
    return {"ghosts": [g["id"] for g in ghosts], "blocks": sum(len(g["blocks"]) for g in ghosts)}
