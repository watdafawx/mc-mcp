from . import ModRoom

C = "create:"
AL, BR, CAS = C + "andesite_alloy_block", C + "brass_block", C + "andesite_casing"
ROOM = ModRoom(
    theme="create", name="Create", namespaces=("create",),
    style="steampunk", alt_styles=(),
    pad=("create:andesite_casing", "create:brass_casing"),
    brief="Kinetic workshop: real gear trains (large + small cogwheels on shafts into casing bearings), a large water "
          "wheel on a shaft between casing pillars, a belt line with a mechanical press on a depot, a mixer over a basin, "
          "fluid tanks with pipes, an encased fan, brass/andesite/copper casing machines, gearboxes and clutches, metal "
          "girders overhead, brass and zinc blocks as stock.",
    deck="minecraft:smooth_sandstone", plinth=("minecraft:smooth_stone", "minecraft:polished_diorite"),
    pieces=(  # v25: real rotating parts. mc-mcp ghosts draw block-entity renderers now (static, not turning).
              # The fake kinds (gear/cog/belt in interiors.py) stay as a fallback for packs where they do not draw.
            ("kgear", CAS),
            ("group", (0, -1, ("column", C + "depot", C + "mechanical_press[facing=east]")),
             (0, 2, ("kbelt", 2, CAS)),
             (-3, -2, ("stack", C + "fluid_tank", 3)), (3, -2, ("stack", C + "fluid_tank", 3)),
             (-2, -1, ("single", C + "shaft[axis=x]")), (-1, -1, ("single", C + "shaft[axis=x]")),
             (1, -1, ("single", C + "shaft[axis=x]")), (2, -1, ("single", C + "shaft[axis=x]"))),
            ("group", (0, 0, ("kwheel", CAS)),
             (-3, 3, ("column", BR, C + "gearbox[axis=x]")), (3, 3, ("column", BR, C + "clutch[axis=x]"))),
            ("group", (0, 0, ("cube", C + "brass_casing", C + "framed_glass", C + "mechanical_mixer")),
             (-3, 0, ("stack", C + "fluid_tank", 3)), (3, 0, ("stack", C + "fluid_tank", 3)),
             (0, 3, ("column", C + "depot", C + "mechanical_press[facing=east]")), (0, -3, ("single", C + "basin")),
             *[(d, 0, ("single", C + "shaft[axis=x]")) for d in (-2, 2)]),
            ("kgear", C + "brass_casing")),
    wall=tuple(C + n for n in "mechanical_press mechanical_mixer fluid_tank gearbox millstone mechanical_saw basin brass_casing depot".split()),
    ghost_rules="Rotating parts DO show in ghosts now (static, not turning): shaft, cogwheel, large_cogwheel, water_wheel, "
                "large_water_wheel, flywheel, belt, hand_crank. Give them their state: shaft/cogwheel/large_cogwheel/flywheel "
                "[axis=x|y|z], large_water_wheel[axis=x|z] (no facing), water_wheel[facing=...], "
                "belt[facing=east,part=start|middle|end,slope=horizontal] in a straight run, fluid_pipe with ALL six of "
                "north/south/east/west/up/down set (the default all-true pipe draws nothing). Cogwheels mesh when a small and a "
                "large one sit diagonally next to each other in the same plane. Contraptions are not assembled. If a block "
                "still shows nothing in view, fake it: shaft = andesite_alloy_block line, cogwheel = dark_oak_planks disc "
                "with andesite_alloy_block teeth and a brass_block hub.",
    blocks=tuple(C + n for n in (
        "andesite_casing brass_casing copper_casing railway_casing industrial_iron_block brass_block zinc_block "
        "andesite_alloy_block metal_girder gearbox clutch gearshift shaft cogwheel large_cogwheel water_wheel "
        "large_water_wheel flywheel belt hand_crank fluid_pipe "
        " mechanical_press mechanical_mixer mechanical_saw mechanical_harvester mechanical_drill "
        "mechanical_pump mechanical_piston mechanical_bearing windmill_bearing millstone encased_fan depot basin "
        "spout item_drain fluid_tank fluid_valve smart_chute chute item_vault hose_pulley rope_pulley "
        "steam_engine framed_glass tiled_glass andesite_scaffolding brass_scaffolding copper_scaffolding "
        "andesite_bars brass_bars copper_bars speedometer stressometer nixie_tube cuckoo_clock "
        "copper_shingles weathered_iron_block redstone_link deployer").split()),
)
