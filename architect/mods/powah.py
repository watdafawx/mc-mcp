from . import ModRoom

P = "powah:"
ROOM = ModRoom(
    theme="powah", name="Powah", namespaces=("powah",),
    style="hextech", alt_styles=("station_white",),
    pad=("powah:energized_steel_block", "powah:energy_cell_basic"),
    brief="Power plant: a bank of tiered energy cells (basic to nitro) as towers, a reactor cluster ringed by "
          "thermo/magmator/furnator generators, an energizing orb with rods in a pedestal circle, solar panel rows "
          "and a crystal-block feature wall. Cables link the machines along the floor.",
    deck="minecraft:light_gray_concrete", plinth=("minecraft:sea_lantern", "minecraft:white_concrete"), ring_dash=True,
    pieces=(  # v23: lit pads. Cell tower ringed by lower cells, cable spokes; reactor cluster ringed by generators
            ("group", (0, 0, ("stack", P + "energy_cell_nitro", 4)),
             *[(dx, dz, ("stack", P + "energy_cell_niotic", 2)) for dx, dz in ((-3, 0), (3, 0), (0, -3), (0, 3))],
             *[(d, 0, ("single", P + "energy_cable_nitro")) for d in (-2, -1, 1, 2)],
             *[(0, d, ("single", P + "energy_cable_nitro")) for d in (-2, -1, 1, 2)]),
            ("group", (0, 0, ("cube", P + "niotic_crystal_block", P + "blazing_crystal_block", P + "reactor_nitro")),
             (-3, 0, ("single", P + "thermo_generator_blazing")), (3, 0, ("single", P + "thermo_generator_blazing")),
             (0, -3, ("single", P + "magmator_nitro")), (0, 3, ("single", P + "furnator_blazing")),
             *[(d, 0, ("single", P + "energy_cable_blazing")) for d in (-2, 2)]),
            ("group", (0, 0, ("stack", P + "energizing_orb", 1)),
             *[(dx, dz, ("stack", P + "energizing_rod_nitro", 2)) for dx, dz in ((-2, -2), (2, -2), (-2, 2), (2, 2))],
             (-3, 0, ("stack", P + "ender_cell_blazing", 2)), (3, 0, ("stack", P + "ender_cell_blazing", 2))),
            ("group", (0, 0, ("stack", P + "energy_cell_spirited", 4)),
             *[(dx, dz, ("stack", P + "energy_cell_hardened", 2)) for dx, dz in ((-3, 0), (3, 0), (0, -3), (0, 3))],
             *[(d, 0, ("single", P + "energy_cable_spirited")) for d in (-2, -1, 1, 2)])),
    wall=tuple(P + n for n in "energy_cell_basic thermo_generator_blazing magmator_nitro furnator_blazing solar_panel_nitro energy_cell_hardened energy_discharger_basic energy_hopper_basic".split()),
    ghost_rules="Energy cells, reactors and orb are static textured cubes: fine. Energizing orb/rods do not animate or "
                "show beams in a ghost; place rods on pedestals around the orb as a static ring. Cables are thin models: "
                "use sparingly, mass comes from cells and crystal blocks.",
    blocks=tuple(P + n for n in (
        "energy_cell_basic energy_cell_hardened energy_cell_blazing energy_cell_niotic energy_cell_spirited "
        "energy_cell_nitro ender_cell_basic ender_cell_hardened ender_cell_blazing ender_cell_niotic ender_cell_spirited "
        "ender_cell_nitro reactor_starter reactor_basic reactor_hardened reactor_blazing reactor_niotic reactor_spirited "
        "reactor_nitro energizing_orb energizing_rod_basic energizing_rod_hardened energizing_rod_blazing "
        "energizing_rod_niotic energizing_rod_spirited energizing_rod_nitro solar_panel_basic solar_panel_hardened "
        "solar_panel_blazing solar_panel_niotic solar_panel_spirited solar_panel_nitro thermo_generator_basic "
        "thermo_generator_blazing thermo_generator_nitro magmator_basic magmator_blazing magmator_nitro furnator_basic "
        "furnator_blazing furnator_nitro energy_cable_basic energy_cable_hardened energy_cable_blazing "
        "energy_cable_niotic energy_cable_spirited energy_cable_nitro energy_hopper_basic energy_discharger_basic "
        "ender_gate_basic ender_gate_nitro player_transmitter_basic player_transmitter_nitro blazing_crystal_block "
        "niotic_crystal_block spirited_crystal_block nitro_crystal_block energized_steel_block uraninite_block dry_ice").split()),
)
