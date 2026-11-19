from . import ModRoom

C = "create:"
ROOM = ModRoom(
    theme="create", name="Create", namespaces=("create",),
    style="steampunk", alt_styles=(),
    pad=("create:andesite_casing", "create:brass_casing"),
    brief="Kinetic workshop: a shaft and cogwheel gear train along the spine with a large water wheel at one wall, a "
          "mechanical press + mixer line over basins, fluid tanks with pipes, an encased fan, brass/andesite/copper "
          "casing machines, a gearbox and clutch, metal girders overhead, brass and zinc blocks as stock.",
    deck="minecraft:smooth_sandstone", plinth=("minecraft:smooth_stone", "minecraft:polished_diorite"),
    pieces=(  # v23: light floor under the dark kinetic parts; gear trains on casing pillars instead of a plain grid
            ("gear", C + "andesite_casing", C + "shaft", C + "cogwheel", C + "large_cogwheel"),
            ("group", (0, 0, ("cube", C + "brass_casing", C + "framed_glass", C + "mechanical_mixer")),
             (-3, 0, ("stack", C + "fluid_tank", 3)), (3, 0, ("stack", C + "fluid_tank", 3)),
             (0, 3, ("single", C + "mechanical_press")), (0, -3, ("single", C + "basin")),
             *[(d, 0, ("single", C + "shaft[axis=x]")) for d in (-2, 2)]),
            ("group", (0, 3, ("gear", C + "brass_casing", C + "shaft", C + "cogwheel", C + "large_cogwheel")),
             (0, -2, ("stack", C + "encased_fan", 2)), (-3, -3, ("stack", C + "andesite_casing", 3)),
             (3, -3, ("stack", C + "andesite_casing", 3))),
            ("group", (0, 0, ("stack", C + "water_wheel", 1)), (-3, 0, ("stack", C + "brass_casing", 3)),
             (3, 0, ("stack", C + "brass_casing", 3)), (0, 3, ("single", C + "gearbox")), (0, -3, ("single", C + "clutch"))),
            ("gear", C + "brass_casing", C + "shaft", C + "cogwheel", C + "large_cogwheel")),
    wall=tuple(C + n for n in "mechanical_press mechanical_mixer fluid_tank gearbox millstone mechanical_saw basin brass_casing depot".split()),
    ghost_rules="Shafts/cogwheels do not rotate in a ghost: they are static. Belts, chutes and pipes are thin models, "
                "belts have no ghost texture (skip them): use casings, tanks, wheels, presses, mixers and girders for "
                "mass. Contraptions are not assembled.",
    blocks=tuple(C + n for n in (
        "andesite_casing brass_casing copper_casing railway_casing industrial_iron_block brass_block zinc_block "
        "andesite_alloy_block metal_girder shaft cogwheel large_cogwheel gearbox clutch gearshift water_wheel "
        "large_water_wheel mechanical_press mechanical_mixer mechanical_saw mechanical_harvester mechanical_drill "
        "mechanical_pump mechanical_piston mechanical_bearing windmill_bearing millstone encased_fan depot basin "
        "spout item_drain fluid_tank fluid_pipe fluid_valve smart_chute chute item_vault hose_pulley rope_pulley "
        "steam_engine flywheel framed_glass tiled_glass andesite_scaffolding brass_scaffolding copper_scaffolding "
        "andesite_bars brass_bars copper_bars hand_crank speedometer stressometer nixie_tube cuckoo_clock "
        "copper_shingles weathered_iron_block redstone_link deployer").split()),
)
