from . import ModRoom, register_signage

D = "draconicevolution:"
DRA, AWK, OBS = D + "draconium_block", D + "awakened_draconium_block", D + "infused_obsidian"
GLASS = "minecraft:tinted_glass"  # DE ships no glass block of its own


def _emblem():
    # v28: a draconic energy star: draconium rim, black field, awakened-draconium diagonals and a lit energy-core hub
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = (u * u + v * v) ** 0.5
            if d > 5.3:
                continue
            out.append((u, v, DRA if d > 4.3 else "minecraft:black_concrete"))
    for u in range(-3, 4):
        for (a, b) in ((u, u), (u, -u)):
            out = [c for c in out if (c[0], c[1]) != (a, b)] + [(a, b, AWK if abs(a) > 1 else D + "chaos_crystal")]
    out = [c for c in out if (c[0], c[1]) != (0, 0)] + [(0, 0, D + "energy_core")]
    return out


# v28 Draconic Evolution: the energy-core temple. The reactor and energy core multiblocks never form, so the room is the
# unformed look: infused obsidian shells, stabilizer pillars, pylons, crafted crystals and draconium blocks.
ROOM = ModRoom(
    theme="draconicevolution", name="Draconic Evolution", namespaces=("draconicevolution",),
    style="cyber_dark", alt_styles=("ae_sky",),
    pad=(OBS, DRA),
    brief="Dark energy temple: a glowing energy core inside an infused-obsidian and tinted-glass cube ringed by stabilizer "
          "pillars and pylons, a reactor core on a draconium plinth with injectors and stabilizers around it, a crafting "
          "ritual (crafting core on infused obsidian, five tiers of crafting injector in a ring, chaos crystals), draconium "
          "chests and the grinder/generator behind them, awakened draconium blocks and draconium ore samples as accents.",
    deck="minecraft:black_concrete", plinth=("minecraft:purple_concrete", "minecraft:gray_concrete"),
    pieces=(
        ("group", (0, 0, ("cube", OBS, GLASS, D + "energy_core")),
         (-2, 0, ("column", OBS, D + "energy_core_stabilizer", D + "energy_core_stabilizer")),
         (2, 0, ("column", OBS, D + "energy_core_stabilizer", D + "energy_core_stabilizer")),
         (0, 2, ("column", OBS, D + "energy_core_stabilizer", D + "energy_core_stabilizer")),
         (0, -2, ("column", OBS, D + "energy_core_stabilizer", D + "energy_core_stabilizer")),
         (-3, -3, ("column", OBS, D + "energy_pylon", D + "energy_pylon")),
         (3, -3, ("column", OBS, D + "energy_pylon", D + "energy_pylon")),
         (-3, 3, ("column", OBS, D + "energy_pylon", D + "energy_pylon")),
         (3, 3, ("column", OBS, D + "energy_pylon", D + "energy_pylon"))),
        ("group", (0, 0, ("column", OBS, DRA, D + "reactor_core")),
         (-2, 0, ("column", OBS, D + "reactor_injector")), (2, 0, ("column", OBS, D + "reactor_injector")),
         (0, 2, ("column", OBS, D + "reactor_stabilizer", D + "reactor_stabilizer")),
         (0, -2, ("column", OBS, D + "reactor_stabilizer", D + "reactor_stabilizer")),
         *[(dx, dz, ("stack", AWK if (dx + dz) % 2 == 0 else DRA, 2)) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("column", OBS, D + "crafting_core")),
         (0, 0, ("ring", (D + "basic_crafting_injector", D + "wyvern_crafting_injector",
                          D + "awakened_crafting_injector", D + "chaotic_crafting_injector"), 2)),
         (-3, -3, ("column", OBS, D + "energy_transfuser")), (3, -3, ("column", OBS, D + "chaos_crystal")),
         (-3, 3, ("column", OBS, D + "chaos_crystal_part")), (3, 3, ("column", OBS, D + "energy_transfuser")),
         (-2, 2, ("single", D + "potentiometer")), (2, -2, ("single", D + "entity_detector_advanced"))),
        ("group", (0, 0, ("column", DRA, D + "draconium_chest")),
         (-2, 0, ("column", OBS, D + "grinder")), (2, 0, ("column", OBS, D + "generator")),
         (0, 2, ("column", OBS, D + "disenchanter")), (0, -2, ("column", OBS, D + "celestial_manipulator")),
         (-3, -3, ("column", OBS, D + "basic_io_crystal")), (3, -3, ("column", OBS, D + "wyvern_wireless_crystal")),
         (-3, 3, ("column", OBS, D + "draconic_relay_crystal")), (3, 3, ("column", OBS, D + "portal"))),
    ),
    wall=tuple(D + n for n in (
        "infused_obsidian draconium_block awakened_draconium_block chaos_crystal chaos_crystal_part energy_core "
        "energy_core_stabilizer energy_pylon energy_transfuser draconium_chest reactor_core reactor_stabilizer "
        "crafting_core basic_crafting_injector wyvern_crafting_injector dislocator_pedestal disenchanter grinder "
        "overworld_draconium_ore").split()),
    extra={"gate": (OBS, DRA, D + "infused_obsidian", "minecraft:shroomlight")},
    ghost_rules="Every DE multiblock (reactor core, energy core, crafting core with injectors, fusion) never forms in a "
                "ghost: show the unformed shells (infused obsidian + tinted glass) with the controller block in the middle, "
                "that is the whitelisted look. The energy core and the crystals are glowing cubes (fine); pylons, "
                "stabilizers and injectors are plain textured blocks. Placed items and floating crystals do not exist: no "
                "ghost texture, they are not whitelisted. Nothing here needs a blockstate.",
    blocks=tuple(D + n for n in (
        "draconium_block awakened_draconium_block infused_obsidian chaos_crystal chaos_crystal_part energy_core "
        "energy_core_stabilizer energy_pylon energy_transfuser reactor_core reactor_injector reactor_stabilizer "
        "crafting_core basic_crafting_injector wyvern_crafting_injector "
        "awakened_crafting_injector chaotic_crafting_injector draconium_chest grinder generator disenchanter "
        "dislocator_pedestal dislocator_receptacle celestial_manipulator entity_detector entity_detector_advanced "
        "fluid_gate flux_gate portal particle_generator potentiometer rain_sensor stabilized_spawner comet_spawner "
        "basic_io_crystal wyvern_io_crystal draconic_io_crystal basic_relay_crystal wyvern_relay_crystal "
        "draconic_relay_crystal basic_wireless_crystal wyvern_wireless_crystal draconic_wireless_crystal "
        "overworld_draconium_ore nether_draconium_ore deepslate_draconium_ore end_draconium_ore").split()),
)

register_signage("draconicevolution", _emblem, (D + "draconium_block", "minecraft:purple_concrete"))
