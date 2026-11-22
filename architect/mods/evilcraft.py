from . import ModRoom, register_signage

E = "evilcraft:"
DB, DK, DT = E + "dark_brick", E + "dark_block", E + "dark_tank"
GLASS = E + "obscured_glass"


def _emblem():
    # v28: a blood drop: dark-brick rim, black field, red drop with a hardened-blood centre
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = (u * u + v * v) ** 0.5
            if d > 5.3:
                continue
            out.append((u, v, DB if d > 4.3 else "minecraft:black_concrete"))
    drop = [(0, 4), (0, 3), (-1, 2), (0, 2), (1, 2), (-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1),
            (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1),
            (-1, -2), (0, -2), (1, -2), (0, -3)]
    for (u, v) in drop:
        out = [c for c in out if (c[0], c[1]) != (u, v)] + [(u, v, "minecraft:red_concrete")]
    for (u, v) in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        out = [c for c in out if (c[0], c[1]) != (u, v)] + [(u, v, E + "hardened_blood")]
    return out


# v28 EvilCraft: a blood-magic crypt. Blood Infuser, spirit furnace, purifier and tanks on dark brick; the undead-material
# family carries the mass, and the mod's only real glass (obscured glass) is the window row.
ROOM = ModRoom(
    theme="evilcraft", name="EvilCraft", namespaces=("evilcraft",),
    style="gothic", alt_styles=("cyber_dark",),
    pad=(DB, DK),
    brief="Blood-magic crypt of dark brick and undead wood: a blood infuser tower with obscured-glass windows ringed by "
          "blood chests and dark tanks, a spirit-furnace altar with sanguinary pedestals, a spirit portal arch, a tank farm "
          "with an environmental accumulator and a purifier, a spiked-blood floor run and an undead grove (undead logs, "
          "crowns of undead leaves, reinforced undead planks) in the corner.",
    deck="minecraft:black_concrete", plinth=("minecraft:red_concrete", "minecraft:gray_concrete"), ring_dash=True,
    pieces=(
        ("group", (0, 0, ("tower", DB, GLASS, 5, E + "blood_infuser")),
         (-2, 0, ("column", DK, E + "blood_chest")), (2, 0, ("column", DK, E + "blood_chest")),
         (0, 2, ("column", DK, DT, DT)), (0, -2, ("column", DK, DT, DT)),
         (-3, -3, ("stack", E + "blood_stain", 1)), (3, -3, ("stack", E + "blood_stain", 1)),
         (-3, 3, ("stack", E + "hardened_blood", 2)), (3, 3, ("stack", E + "hardened_blood", 2))),
        ("group", (0, 0, ("column", DK, E + "spirit_furnace")),
         (0, 0, ("ring", (E + "sanguinary_pedestal_0", E + "sanguinary_pedestal_1", E + "spiked_plate"), 2)),
         (-3, -3, ("column", DB, E + "spirit_portal")), (3, -3, ("column", DB, DB, E + "gem_stone_torch")),
         (-3, 3, ("column", DB, DB, E + "gem_stone_torch")), (3, 3, ("column", DB, E + "spirit_reanimator")),
         (-2, 2, ("single", E + "display_stand")), (2, -2, ("column", DB, E + "dark_power_gem_block"))),
        ("group", (0, 0, ("stack", DT, 3)),
         (-2, 0, ("stack", DT, 3)), (2, 0, ("stack", DT, 3)), (0, 2, ("stack", DT, 3)), (0, -2, ("stack", DT, 3)),
         (-2, 2, ("column", DB, E + "environmental_accumulator")), (2, -2, ("column", DB, E + "purifier")),
         (-2, -2, ("stack", E + "colossal_blood_chest", 1)), (2, 2, ("stack", E + "dark_blood_brick", 2))),
        ("group", (0, 0, ("blob", E + "undead_leaves", 2, 4)),
         (0, 0, ("column", E + "undead_log", E + "undead_log", E + "undead_log", E + "undead_log")),
         (-2, 0, ("column", E + "undead_wood", E + "undead_leaves")), (2, 0, ("column", E + "undead_wood", E + "undead_leaves")),
         (0, 2, ("column", E + "undead_wood", E + "undead_sapling")), (0, -2, ("column", E + "undead_log_stripped", E + "undead_leaves")),
         (-3, -3, ("stack", E + "reinforced_undead_planks", 2)), (3, -3, ("stack", E + "undead_planks", 2)),
         (-3, 3, ("stack", E + "undead_planks", 2)), (3, 3, ("stack", E + "reinforced_undead_planks", 2)),
         (-2, 2, ("single", E + "undead_slab")), (2, -2, ("stack", E + "infested_nether_netherrack", 1))),
    ),
    wall=tuple(E + n for n in (
        "dark_brick dark_blood_brick dark_block dark_tank obscured_glass blood_chest blood_infuser spirit_furnace "
        "environmental_accumulator purifier undead_planks reinforced_undead_planks undead_log dark_power_gem_block "
        "hardened_blood colossal_blood_chest").split()),
    extra={"gate": (DB, E + "dark_blood_brick", E + "undead_planks", "minecraft:shroomlight")},
    ghost_rules="Fluid source blocks (blood, poison, eternal_water) exist but are not whitelisted: a fluid never draws in a "
                "ghost. blood_stain is a thin floor decal, keep it as an accent only. EvilCraft machines (blood infuser, "
                "purifier, spirit furnace, spirit reanimator, accumulators) are plain textured cubes; the pedestals are "
                "short models. The spirit portal is a multiblock frame that never forms: show the arch of dark brick. "
                "Nothing here needs a blockstate.",
    blocks=tuple(E + n for n in (
        "dark_brick dark_blood_brick dark_block dark_tank obscured_glass dark_power_gem_block hardened_blood blood_stain "
        "blood_chest colossal_blood_chest blood_infuser spirit_furnace spirit_portal spirit_reanimator "
        "sanguinary_pedestal_0 sanguinary_pedestal_1 environmental_accumulator sanguinary_environmental_accumulator "
        "purifier display_stand spiked_plate gem_stone_torch gem_stone_torch_wall lightning_bomb invisible_redstone "
        "dark_ore dark_ore_deepslate bloody_cobblestone undead_planks reinforced_undead_planks undead_planks_stairs "
        "undead_log undead_log_stripped undead_wood undead_wood_stripped undead_leaves undead_sapling undead_slab "
        "undead_fence undead_fence_gate infested_nether_netherrack infested_nether_nether_bricks infested_nether_soul_sand "
        "dark_brick_stairs dark_blood_brick_stairs blood_waxed_coal_block").split()),
)

register_signage("evilcraft", _emblem, (E + "dark_brick", "minecraft:red_concrete"))
