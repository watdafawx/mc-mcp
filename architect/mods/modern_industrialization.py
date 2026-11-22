from . import ModRoom, register_signage

M = "modern_industrialization:"
SMC, AMC = M + "steel_machine_casing", M + "advanced_machine_casing"
AHULL = M + "advanced_machine_hull"
ST, BT, AT, QT = M + "steel_tank", M + "bronze_tank", M + "aluminum_tank", M + "quantum_tank"
KAN, CUP, SUP = M + "kanthal_coil", M + "cupronickel_coil", M + "superconductor_coil"
NCAS, FUSION, PLASMA = M + "nuclear_casing", M + "fusion_chamber", M + "plasma_handling_iridium_machine_casing"
GLASS = "minecraft:tinted_glass"  # MI ships no glass block of its own


def _emblem():
    # v28: the hex nut of heavy industry: steel casing rim, orange accent ring, steel body and a bronze hub
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            d = max(abs(v) / 0.866, abs(u) + abs(v) * 0.5)
            if d > 5.2:
                continue
            if d > 4.2:
                b = SMC
            elif d > 2.6:
                b = "minecraft:orange_concrete"
            else:
                b = M + "steel_block"
            out.append((u, v, b))
    for (u, v) in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        out = [c for c in out if (c[0], c[1]) != (u, v)] + [(u, v, M + "bronze_block")]
    return out


# v28 Modern Industrialization: a heavy-industry hall. Every MI machine is a block-entity render with no block texture, so
# nothing but casings, hulls, tanks, barrels, coils and metal blocks is whitelisted; machines show as their casing shells.
ROOM = ModRoom(
    theme="modern_industrialization", name="Modern Industrialization", namespaces=("modern_industrialization",),
    style="rust_industrial", alt_styles=("station_white", "cyber_dark"),
    pad=(SMC, AMC),
    brief="Heavy-industry hall of grey machine casing and dark tinted glass: a steam-boiler tower with a steel hull core, a "
          "fusion chamber inside a nuclear casing cube with plasma-handling pillars and fuel blocks, superconductor coil "
          "batteries on advanced casing, bronze/steel/quantum tanks and barrels round every plinth, a forge hammer line over "
          "fire-clay bricks, mooring-pipe lintels and stacks of steel, titanium and uranium blocks as stock.",
    deck="minecraft:light_gray_concrete", plinth=("minecraft:orange_concrete", "minecraft:gray_concrete"),
    pieces=(  # casings + hulls + tanks only: no MI machine model has a ghost texture
        ("group", (0, 0, ("tower", SMC, GLASS, 6, AHULL)),
         (-3, -3, ("stack", ST, 3)), (3, -3, ("stack", BT, 2)),
         (-3, 3, ("stack", QT, 3)), (3, 3, ("stack", AT, 2)),
         (0, 3, ("stack", KAN, 2)), (0, -3, ("stack", CUP, 2))),
        ("group", (0, 0, ("cube", NCAS, GLASS, FUSION)),
         (-3, 0, ("column", SMC, PLASMA, PLASMA)), (3, 0, ("column", SMC, PLASMA, PLASMA)),
         (0, 3, ("stack", M + "industrial_tnt", 1)), (0, -3, ("stack", M + "nuclear_alloy_machine_casing_pipe", 2)),
         (-2, -2, ("single", M + "nuke")), (2, 2, ("stack", M + "uranium_235_block", 1)),
         (2, -2, ("stack", M + "uranium_238_block", 1)), (-2, 2, ("stack", M + "plutonium_block", 1))),
        ("group", (0, 0, ("tower", AMC, GLASS, 5, SUP)),
         *[(dx, dz, ("column", SMC, SMC, KAN, KAN)) for dx in (-3, 3) for dz in (-3, 3)],
         (-2, 0, ("stack", M + "battery_alloy_block", 1)), (2, 0, ("stack", M + "battery_alloy_block", 1)),
         (0, 3, ("single", M + "trash_can")), (0, -3, ("stack", M + "stainless_steel_tank", 2))),
        ("group", (0, 0, ("cube", M + "clean_stainless_steel_machine_casing", GLASS, AHULL)),
         (-2, 0, ("column", SMC, M + "forge_hammer")), (2, 0, ("column", SMC, M + "solid_titanium_machine_casing")),
         (0, 2, ("stack", M + "bronze_plated_bricks", 2)), (0, -2, ("stack", M + "fire_clay_bricks", 2)),
         (-3, -3, ("stack", M + "steel_barrel", 2)), (3, -3, ("stack", M + "titanium_barrel", 2)),
         (-3, 3, ("stack", M + "stainless_steel_barrel", 2)), (3, 3, ("stack", M + "quantum_barrel", 2))),
    ),
    wall=tuple(M + n for n in (
        "steel_machine_casing advanced_machine_casing quantum_machine_casing highly_advanced_machine_casing "
        "turbo_machine_casing blastproof_casing steel_tank bronze_tank aluminum_tank quantum_tank stainless_steel_tank "
        "steel_barrel aluminum_barrel quantum_barrel nuclear_casing fusion_chamber forge_hammer trash_can "
        "kanthal_coil cupronickel_coil superconductor_coil steel_block stainless_steel_block titanium_block").split()),
    extra={"gate": (SMC, AMC, M + "steel_machine_casing_pipe", "minecraft:shroomlight")},
    ghost_rules="NO MI machine draws in a ghost: every machine (electric/steam macerator, furnace, mixer, boiler, quarry, "
                "distillation tower, storage unit, hatches, pipes, cables) is a block-entity render without a block texture "
                "and is NOT whitelisted. Build the hall out of casings, hulls, tanks, barrels, coils, casing pipes and metal "
                "blocks. Multiblocks (large boiler, heat exchanger, distillation tower, fusion reactor) never form: show the "
                "unformed casing + glass shell with the port blocks on the faces. Coils stack without a state.",
    blocks=tuple(M + n for n in (
        "steel_machine_casing advanced_machine_casing highly_advanced_machine_casing turbo_machine_casing "
        "quantum_machine_casing bronze_machine_casing clean_stainless_steel_machine_casing solid_titanium_machine_casing "
        "heatproof_machine_casing frostproof_machine_casing blastproof_casing nuclear_casing bronze_plated_bricks "
        "fire_clay_bricks bronze_machine_casing_pipe steel_machine_casing_pipe stainless_steel_machine_casing_pipe "
        "nuclear_alloy_machine_casing_pipe iridium_machine_casing_pipe plasma_handling_iridium_machine_casing "
        "basic_machine_hull advanced_machine_hull turbo_machine_hull quantum_machine_hull highly_advanced_machine_hull "
        "kanthal_coil cupronickel_coil superconductor_coil steel_tank bronze_tank aluminum_tank stainless_steel_tank "
        "titanium_tank quantum_tank steel_barrel bronze_barrel iron_barrel aluminum_barrel stainless_steel_barrel "
        "titanium_barrel quantum_barrel steel_block stainless_steel_block titanium_block aluminum_block bronze_block "
        "tungsten_block iridium_block platinum_block uranium_block uranium_235_block uranium_238_block plutonium_block "
        "salt_block silicon_block coke_block lignite_coal_block antimony_block beryllium_block chromium_block "
        "neodymium_block yttrium_block nickel_block lead_block tin_block silver_block sodium_block monazite_block "
        "bauxite_block invar_block kanthal_block cupronickel_block electrum_block annealed_copper_block "
        "battery_alloy_block soldering_alloy_block sulfur_block forge_hammer trash_can fusion_chamber industrial_tnt nuke").split()),
)

register_signage("modern_industrialization", _emblem, (M + "steel_block", "minecraft:orange_concrete"))
