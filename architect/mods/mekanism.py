from . import ModRoom

M, G = "mekanism:", "mekanismgenerators:"
ROOM = ModRoom(
    theme="mekanism", name="Mekanism", namespaces=("mekanism", "mekanismgenerators"),
    style="station_white", alt_styles=("hextech",),
    pad=("mekanism:block_steel", "mekanism:steel_casing"),
    brief="Clean-room machine hall: steel casing and structural glass shells, a Digital Miner and teleporter frame as "
          "centrepieces, rows of tiered energy cubes, a factory line (crusher > enrichment > smelter), chemical tanks "
          "and an induction matrix block of casing + cells behind glass.",
    pieces=(("cube", M + "steel_casing", M + "structural_glass", M + "digital_miner"),
            ("tower", M + "induction_casing", M + "structural_glass", 4, M + "ultimate_induction_cell"),
            ("stack", M + "ultimate_energy_cube", 1),
            ("cube", G + "turbine_casing", G + "reactor_glass", G + "turbine_rotor"),
            ("single", M + "teleporter_frame"),
            ("stack", M + "elite_chemical_tank", 2)),
    wall=tuple(M + n for n in "crusher enrichment_chamber energized_smelter combiner osmium_compressor purification_chamber metallurgic_infuser chemical_infuser electrolytic_separator isotopic_centrifuge ultimate_energy_cube elite_chemical_tank".split()),
    ghost_rules="Multiblocks (induction matrix, boiler, fission/fusion reactor, evaporation tower, SPS) do not form in a "
                "ghost: show them as the unformed look (plain casing + glass, ports on the faces). Do not rely on "
                "machine animations or active textures; show machines as plain blocks. Pipes/cables/tubes are thin "
                "models: prefer casing, tanks and cubes for mass.",
    blocks=tuple(M + n for n in (
        "steel_casing structural_glass block_steel block_osmium block_bronze block_refined_obsidian block_refined_glowstone "
        "block_tin block_lead block_uranium induction_casing induction_port basic_induction_cell advanced_induction_cell "
        "elite_induction_cell ultimate_induction_cell ultimate_induction_provider sps_casing sps_port boiler_casing "
        "boiler_valve dynamic_tank dynamic_valve thermal_evaporation_block thermal_evaporation_controller "
        "thermal_evaporation_valve superheating_element supercharged_coil digital_miner teleporter teleporter_frame "
        "basic_energy_cube advanced_energy_cube elite_energy_cube ultimate_energy_cube basic_chemical_tank "
        "advanced_chemical_tank elite_chemical_tank ultimate_chemical_tank basic_fluid_tank ultimate_fluid_tank "
        "crusher enrichment_chamber combiner osmium_compressor energized_smelter purification_chamber "
        "pressurized_reaction_chamber metallurgic_infuser chemical_infuser chemical_oxidizer chemical_washer "
        "chemical_crystallizer chemical_dissolution_chamber electrolytic_separator isotopic_centrifuge "
        "antiprotonic_nucleosynthesizer formulaic_assemblicator rotary_condensentrator resistive_heater "
        "laser laser_amplifier laser_tractor_beam qio_drive_array qio_dashboard industrial_alarm "
        "basic_smelting_factory elite_crushing_factory ultimate_enriching_factory ultimate_smelting_factory "
        "ultimate_combining_factory basic_bin ultimate_bin personal_chest chargepad modification_station "
        "painting_machine security_desk dimensional_stabilizer seismic_vibrator").split())
    + tuple(G + n for n in (
        "reactor_glass fusion_reactor_frame fusion_reactor_controller fusion_reactor_port fission_reactor_casing "
        "fission_reactor_port fission_fuel_assembly control_rod_assembly turbine_casing turbine_rotor turbine_valve "
        "turbine_vent electromagnetic_coil laser_focus_matrix solar_generator advanced_solar_generator wind_generator "
        "heat_generator bio_generator gas_burning_generator rotational_complex saturating_condenser").split()),
)
