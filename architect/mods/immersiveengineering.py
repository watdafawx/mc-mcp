from . import ModRoom, register_signage

IE = "immersiveengineering:"
BB, BR, CB, COKE = (IE + n for n in ("blastbrick", "blastbrick_reinforced", "cokebrick", "coke"))
SM_S, SM_I = IE + "sheetmetal_steel", IE + "sheetmetal_iron"
CONC, WOOD, GLASS = IE + "concrete", IE + "treated_wood_horizontal", IE + "insulating_glass"


def _emblem():
    # v28: hazard panel: sheetmetal-steel rim, black/orange diagonal stripes and a steel hub (the warning-sign look of the mod)
    out = []
    for u in range(-5, 6):
        for v in range(-5, 6):
            if (u * u + v * v) ** 0.5 > 5.3:
                continue
            if (u * u + v * v) ** 0.5 > 4.3:
                b = SM_S
            elif (u + v) % 4 in (0, 1):
                b = "minecraft:orange_concrete"
            else:
                b = "minecraft:black_concrete"
            out.append((u, v, b))
    for u in (-1, 0, 1):
        for v in (-1, 0, 1):
            out = [c for c in out if (c[0], c[1]) != (u, v)] + [(u, v, SM_I)]
    return out


# v28 Immersive Engineering: the blast-furnace/coke-oven works. Multiblock controllers draw as their unformed shell and the
# machines are plain textured cubes, so casings, bricks, sheetmetal, scaffolding and coil banks carry the room.
ROOM = ModRoom(
    theme="immersiveengineering", name="Immersive Engineering", namespaces=("immersiveengineering",),
    style="steampunk", alt_styles=("rust_industrial",),
    pad=(CONC, SM_S),
    brief="Works hall of blastbrick and sheetmetal: a blast furnace in a reinforced blastbrick cube with preheaters, a coke "
          "oven battery on coke bricks, a metal-press/crusher line on sheetmetal-steel columns, wet silos and a tank farm "
          "joined by pipes, coil lv/mv/hv banks on transformer plinths, treated-wood catwalks, steel scaffolding and "
          "insulating glass windows, warning-sign orange on grey.",
    deck="minecraft:gray_concrete", plinth=("minecraft:orange_concrete", "minecraft:black_concrete"),
    pieces=(
        ("group", (0, 0, ("cube", BB, GLASS, IE + "blast_furnace")),
         (-2, 0, ("column", BR, IE + "blastfurnace_preheater", IE + "blastfurnace_preheater")),
         (2, 0, ("column", BR, IE + "blastfurnace_preheater", IE + "blastfurnace_preheater")),
         (0, 2, ("column", BR, IE + "arc_furnace")), (0, -2, ("column", BR, IE + "alloy_smelter")),
         (-3, -3, ("stack", IE + "blastbrick_reinforced", 3)), (3, -3, ("stack", IE + "blastbrick_reinforced", 3)),
         (-3, 3, ("stack", IE + "concrete_leaded", 2)), (3, 3, ("stack", IE + "concrete_leaded", 2))),
        ("group", (0, 0, ("column", CB, CB, IE + "coke_oven")),
         (-2, 0, ("stack", COKE, 2)), (2, 0, ("stack", COKE, 2)),
         (0, 2, ("column", SM_S, IE + "crusher")), (0, -2, ("column", SM_S, IE + "mixer")),
         *[(dx, dz, ("stack", CB, 2)) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("tower", SM_S, GLASS, 5, IE + "metal_press")),
         (0, 3, ("column", IE + "heavy_engineering", IE + "sawmill")),
         (0, -3, ("column", IE + "light_engineering", IE + "assembler")),
         (-3, 0, ("column", SM_I, IE + "coil_mv")), (3, 0, ("column", SM_I, IE + "coil_hv")),
         (-3, -3, ("stack", IE + "storage_steel", 2)), (3, -3, ("stack", IE + "storage_aluminum", 2)),
         (-3, 3, ("stack", IE + "storage_nickel", 2)), (3, 3, ("stack", IE + "storage_lead", 2))),
        ("group", (0, 0, ("stack", IE + "tank", 3)),
         (-2, 0, ("stack", IE + "silo", 3)), (2, 0, ("stack", IE + "silo", 3)),
         (0, 2, ("column", SM_S, IE + "refinery")), (0, -2, ("column", SM_S, IE + "fermenter")),
         (-2, 2, ("single", IE + "fluid_pipe")), (2, -2, ("single", IE + "fluid_pipe")),
         (-3, -3, ("column", WOOD, IE + "crate")), (3, -3, ("column", WOOD, IE + "reinforced_crate")),
         (-3, 3, ("single", IE + "radiator")), (3, 3, ("single", IE + "transformer"))),
    ),
    wall=tuple(IE + n for n in (
        "blastbrick blastbrick_reinforced cokebrick coke slag_brick concrete concrete_leaded treated_wood_horizontal "
        "sheetmetal_steel sheetmetal_iron storage_steel storage_aluminum insulating_glass steel_scaffolding_standard "
        "coil_lv coil_mv transformer radiator chute_steel crate silo tank fluid_pipe").split()),
    extra={"gate": (SM_S, IE + "steel_scaffolding_standard", IE + "sheetmetal_iron", "minecraft:shroomlight")},
    ghost_rules="Machines are plain textured cubes (fine), but every IE block with a facing/active property (alloy_smelter, "
                "arc_furnace, crusher, mixer, metal_press, assembler, refinery, fermenter, ...) is placed WITHOUT a state: if "
                "you need a machine to face the aisle add [facing=north|south|east|west] at your own risk (unverified keys). "
                "Multiblocks (blast furnace, coke oven, excavator, diesel generator, lightning rod, crusher) never form: show "
                "the unformed shell of bricks + glass. Scaffolding, catwalks, fences and ladders are thin models: use them as "
                "accents, not mass. Coils stack without a state.",
    blocks=tuple(IE + n for n in (
        "blastbrick blastbrick_reinforced cokebrick coke slag_brick slag_glass clinker_brick concrete concrete_brick "
        "concrete_leaded concrete_reinforced concrete_tile concrete_chiseled concrete_pillar concrete_sheet duroplast "
        "hempcrete hempcrete_brick treated_wood_horizontal treated_wood_vertical treated_wood_packaged alloybrick "
        "sheetmetal_steel sheetmetal_iron sheetmetal_aluminum sheetmetal_copper sheetmetal_lead sheetmetal_nickel "
        "sheetmetal_silver sheetmetal_constantan sheetmetal_uranium storage_steel storage_aluminum storage_nickel "
        "storage_lead storage_silver storage_constantan storage_electrum storage_uranium insulating_glass heavy_engineering "
        "light_engineering rs_engineering machine_interface steel_scaffolding_standard alu_scaffolding_standard "
        "steel_slope alu_catwalk steel_catwalk metal_ladder_steel metal_ladder_alu alloy_smelter arc_furnace assembler "
        "auto_workbench blast_furnace blastfurnace_preheater coke_oven crusher diesel_generator fermenter mixer squeezer "
        "refinery excavator metal_press sawmill bottling_machine circuit_table workbench windmill watermill tesla_coil "
        "lightning_rod floodlight fluid_pipe pipe_valve radiator transformer current_transformer chute_steel crate "
        "reinforced_crate silo tank toolbox_block coil_lv coil_mv coil_hv generator dynamo furnace_heater").split()),
)

register_signage("immersiveengineering", _emblem, (IE + "sheetmetal_steel", "minecraft:orange_concrete"))
