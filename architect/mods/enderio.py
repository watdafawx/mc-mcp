from . import ModRoom

E = "enderio:"
DS, VA, ES = E + "dark_steel_block", E + "vibrant_alloy_block", E + "end_steel_block"
# v27 Ender IO: whitelist of ~45 of the 825 blocks (the 357 painted fused-quartz variants are left out): alloy blocks,
# machines, capacitor banks, obelisks, chassis and bars.
ROOM = ModRoom(
    theme="enderio", name="Ender IO", namespaces=("enderio",),
    style="steampunk", alt_styles=("station_white",),
    pad=(DS, E + "soularium_block"),
    brief="Machine hall of dark steel: alloy smelter, SAG mill, soul binder and slice-and-splice as centrepieces between "
          "capacitor bank stacks (basic, advanced, vibrant), fluid tanks, an XP obelisk and travel anchors on vibrant and "
          "pulsating alloy blocks, dark steel bars and a fused quartz window.",
    deck="minecraft:smooth_quartz", plinth=("minecraft:lime_concrete", "minecraft:gray_concrete"), ring_dash=True,
    pieces=(
        ("group", (0, 0, ("column", DS, E + "alloy_smelter[facing=south,powered=false]")),
         (-2, 0, ("column", DS, E + "sag_mill[facing=south,powered=false]")), (2, 0, ("column", DS, E + "soul_binder[facing=south,powered=false]")),
         (0, 2, ("column", DS, E + "slice_and_splice[facing=south,powered=false]")), (0, -2, ("column", DS, E + "vat[facing=south,powered=false]")),
         *[(dx, dz, ("stack", E + "vibrant_capacitor_bank", 3)) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("stack", E + "advanced_capacitor_bank", 4)),
         (-2, 0, ("stack", E + "basic_capacitor_bank", 3)), (2, 0, ("stack", E + "basic_capacitor_bank", 3)),
         (0, 2, ("stack", E + "vibrant_capacitor_bank", 2)), (0, -2, ("stack", E + "vibrant_capacitor_bank", 2)),
         *[(dx, dz, ("column", ES, E + "energetic_alloy_block", E + "pulsating_alloy_block")) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("stack", E + "xp_obelisk", 1)),
         (-2, 0, ("stack", E + "fluid_tank[facing=south]", 3)), (2, 0, ("stack", E + "pressurized_fluid_tank[facing=south]", 3)),
         (0, 2, ("stack", E + "travel_anchor", 1)), (0, -2, ("stack", E + "travel_anchor", 1)),
         (-3, -3, ("stack", E + "dark_steel_bars[north=true,south=true,east=false,west=false]", 3)),
         (3, 3, ("stack", E + "dark_steel_bars[north=true,south=true,east=false,west=false]", 3)),
         (3, -3, ("stack", E + "vibrant_alloy_block", 1)), (-3, 3, ("stack", E + "vibrant_alloy_block", 1))),
        ("group", (0, 0, ("cube", DS, E + "fused_quartz", E + "powered_spawner[facing=south,powered=false]")),
         (-3, 0, ("stack", E + "stirling_generator[facing=south,powered=false]", 1)), (3, 0, ("stack", E + "farming_station", 1)),
         (0, 3, ("stack", E + "enchanter[facing=south]", 1)), (0, -3, ("stack", E + "crafter[facing=south,powered=false]", 1)),
         (-2, -2, ("stack", E + "void_chassis", 1)), (2, 2, ("stack", E + "ensouled_chassis", 1))),
    ),
    wall=tuple(E + n for n in "alloy_smelter[facing=south,powered=false] sag_mill[facing=south,powered=false] "
               "soul_binder[facing=south,powered=false] vat[facing=south,powered=false] dark_steel_block "
               "basic_capacitor_bank painting_machine[facing=south,powered=false] wired_charger[facing=south]".split()),
    extra={"gate": (DS, ES, E + "dark_steel_bars[north=false,south=false,east=true,west=true]", E + "vibrant_alloy_block")},
    ghost_rules="Machines take facing=north|south|east|west and powered=false; conduits and photovoltaic modules are "
                "multipart and are not whitelisted. The fused quartz variants are plain glass, use only fused_quartz. "
                "Capacitor banks stack without a state. Obelisks and anchors are plain cubes in a ghost.",
    blocks=tuple(E + n for n in (
        "dark_steel_block end_steel_block vibrant_alloy_block energetic_alloy_block pulsating_alloy_block "
        "redstone_alloy_block conductive_alloy_block soularium_block reinforced_obsidian_block industrial_insulation "
        "alloy_smelter sag_mill soul_binder slice_and_splice vat enchanter crafter farming_station stirling_generator "
        "basic_capacitor_bank advanced_capacitor_bank vibrant_capacitor_bank fluid_tank pressurized_fluid_tank "
        "xp_obelisk attractor_obelisk weather_obelisk travel_anchor powered_spawner dark_steel_bars end_steel_bars "
        "void_chassis ensouled_chassis soul_engine impulse_hopper vacuum_chest wired_charger wireless_charger "
        "painting_machine drain xp_vacuum fused_quartz fused_quartz_black dark_steel_ladder").split()),
)
