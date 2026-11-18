from . import ModRoom

I = "industrialforegoing:"
ROOM = ModRoom(
    theme="industrialforegoing", name="Industrial Foregoing", namespaces=("industrialforegoing",),
    style="steampunk", alt_styles=("station_white",),
    pad=("industrialforegoing:machine_frame_simple", "industrialforegoing:machine_frame_advanced"),
    brief="Machine bays: rows of machine-frame pads each carrying a machine (plant gatherer, sower, fertilizer, mob "
          "crusher, slaughter factory, laser drill with ore laser base), a hydroponic bed corner, a sludge refiner, "
          "latex and biofuel line and a conveyor strip down the spine.",
    pieces=(("single", I + "plant_gatherer"), ("single", I + "mob_crusher"), ("single", I + "laser_drill"),
            ("single", I + "bioreactor"), ("single", I + "plant_sower"), ("single", I + "sludge_refiner"),
            ("single", I + "mob_slaughter_factory"), ("single", I + "latex_processing_unit"),
            ("single", I + "resourceful_furnace")),
    wall=tuple(I + n for n in "plant_gatherer mob_crusher plant_sower resourceful_furnace sludge_refiner bioreactor hydroponic_bed laser_drill".split()),
    ghost_rules="Machines are plain textured cubes with a front face: fine. Fluid, laser and item animations do not show. "
                "Conveyors are flat models: use sparingly. No black-hole units or backpacks (no ghost texture).",
    blocks=tuple(I + n for n in (
        "machine_frame_pity machine_frame_simple machine_frame_advanced machine_frame_supreme plant_gatherer plant_sower "
        "plant_fertilizer hydroponic_bed simulated_hydroponic_bed mob_crusher mob_slaughter_factory animal_rancher "
        "animal_feeder laser_drill ore_laser_base fluid_laser_base bioreactor biofuel_generator pitiful_generator "
        "sludge_refiner sewage_composter latex_processing_unit fermentation_station washing_factory dissolution_chamber "
        "enchantment_factory enchantment_extractor stasis_chamber block_breaker block_placer material_stonework_factory "
        "resourceful_furnace fluid_extractor fluid_collector fluid_placer water_condensator dye_mixer potion_brewer "
        "pink_slime_block mechanical_dirt mob_duplicator infinity_charger conveyor transporter "
        "spores_recreator marine_fisher sewer mob_detector").split()),
)
