from . import ModRoom

C = "create:"
ROOM = ModRoom(
    theme="create", name="Create", namespaces=("create",),
    style="steampunk", alt_styles=(),
    pad=("create:andesite_casing", "create:brass_casing"),
    brief="Kinetic workshop: a shaft and cogwheel gear train along the spine with a large water wheel at one wall, a "
          "mechanical press + mixer line over basins, fluid tanks with pipes, an encased fan, brass/andesite/copper "
          "casing machines, a gearbox and clutch, metal girders overhead, brass and zinc blocks as stock.",
    pieces=(("stack", C + "fluid_tank", 3), ("single", C + "mechanical_press"), ("single", C + "large_cogwheel"),
            ("cube", C + "brass_casing", C + "framed_glass", C + "mechanical_mixer"),
            ("single", C + "gearbox"), ("stack", C + "shaft", 4), ("single", C + "water_wheel"),
            ("stack", C + "encased_fan", 2)),
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
