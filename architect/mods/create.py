from . import ModRoom

C = "create:"
AL, BR, CAS = C + "andesite_alloy_block", C + "brass_block", C + "andesite_casing"
OAK = "minecraft:dark_oak_planks"
ROOM = ModRoom(
    theme="create", name="Create", namespaces=("create",),
    style="steampunk", alt_styles=(),
    pad=("create:andesite_casing", "create:brass_casing"),
    brief="Kinetic workshop: gear trains (fake cogwheels: dark-oak discs, alloy teeth, brass hubs, because real cogwheels are "
          "invisible in ghosts) and a big water wheel on casing pillars, a "
          "mechanical press + mixer line over basins, fluid tanks with pipes, an encased fan, brass/andesite/copper "
          "casing machines, a gearbox and clutch, metal girders overhead, brass and zinc blocks as stock.",
    deck="minecraft:smooth_sandstone", plinth=("minecraft:smooth_stone", "minecraft:polished_diorite"),
    pieces=(  # v24: rotating parts (shaft, cogwheel, water wheel, belt) are invisible in ghosts, so they are built from
              # blocks that render: dark-oak wheels with andesite-alloy teeth and brass hubs, alloy shaft runs, slab belts.
            ("gear", CAS, AL, OAK, AL, BR),
            ("group", (0, -1, ("column", C + "depot", C + "mechanical_press[facing=east]")),
             (0, 2, ("belt", 3, "minecraft:polished_blackstone_slab", CAS)),
             (-3, -2, ("stack", C + "fluid_tank", 3)), (3, -2, ("stack", C + "fluid_tank", 3)),
             (-2, -1, ("single", AL)), (-1, -1, ("single", AL)), (1, -1, ("single", AL)), (2, -1, ("single", AL))),
            ("group", (0, 0, ("cog", 3, OAK, "minecraft:spruce_planks", BR, 3, CAS)),
             (-3, 3, ("column", BR, C + "gearbox[axis=x]")), (3, 3, ("column", BR, C + "clutch[axis=x]"))),
            ("group", (0, 0, ("cube", C + "brass_casing", C + "framed_glass", C + "mechanical_mixer")),
             (-3, 0, ("stack", C + "fluid_tank", 3)), (3, 0, ("stack", C + "fluid_tank", 3)),
             (0, 3, ("column", C + "depot", C + "mechanical_press[facing=east]")), (0, -3, ("single", C + "basin")),
             *[(d, 0, ("single", AL)) for d in (-2, 2)]),
            ("gear", C + "brass_casing", AL, "minecraft:stripped_dark_oak_log", "create:brass_block", BR)),
    wall=tuple(C + n for n in "mechanical_press mechanical_mixer fluid_tank gearbox millstone mechanical_saw basin brass_casing depot".split()),
    ghost_rules="INVISIBLE in ghosts (block-entity renderers, nothing is drawn): create:shaft, cogwheel, large_cogwheel, "
                "powered_shaft, water_wheel, large_water_wheel, flywheel, belt, hand_crank, crushing_wheel, fluid_pipe, "
                "sails. Never place them. Fake them: shaft = andesite_alloy_block line, cogwheel = a disc of dark_oak_planks "
                "with andesite_alloy_block teeth and a brass_block hub, belt = a line of polished_blackstone_slab between "
                "andesite_casing pulleys. These DO render: casings, gearbox, clutch, encased_chain_drive, mechanical_press, "
                "mixer, depot, basin, fluid_tank, item_vault, encased_fan, steam_engine, bearings, tunnels, funnels. "
                "Contraptions are not assembled.",
    blocks=tuple(C + n for n in (
        "andesite_casing brass_casing copper_casing railway_casing industrial_iron_block brass_block zinc_block "
        "andesite_alloy_block metal_girder gearbox clutch gearshift "
        " mechanical_press mechanical_mixer mechanical_saw mechanical_harvester mechanical_drill "
        "mechanical_pump mechanical_piston mechanical_bearing windmill_bearing millstone encased_fan depot basin "
        "spout item_drain fluid_tank fluid_valve smart_chute chute item_vault hose_pulley rope_pulley "
        "steam_engine framed_glass tiled_glass andesite_scaffolding brass_scaffolding copper_scaffolding "
        "andesite_bars brass_bars copper_bars speedometer stressometer nixie_tube cuckoo_clock "
        "copper_shingles weathered_iron_block redstone_link deployer").split()),
)
