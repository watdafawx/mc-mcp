from . import ModRoom

M = "mysticalagriculture:"
INF, PRO = M + "inferium_block", M + "prosperity_block"
FARM = M + "inferium_farmland[moisture=7]"
# v27 Mystical Agriculture: essence farm. Crop fields on inferium farmland, an infusion altar with eight pedestals,
# an awakening altar on soulstone, machine row. Crops need an age state; farmland goes under them (field piece).
ROOM = ModRoom(
    theme="mysticalagriculture", name="Mystical Agriculture", namespaces=("mysticalagriculture",),
    style="solarpunk", alt_styles=(),
    pad=(INF, PRO),
    brief="Essence farm greenhouse: fields of mature crops on inferium farmland with growth accelerators in the corners, "
          "an infusion altar ringed by infusion pedestals and essence vessels, an awakening altar on soulstone with "
          "four pedestals, and a row of harvester, seed reprocessor, soul extractor and tinkering table.",
    deck="minecraft:smooth_quartz", plinth=("minecraft:lime_concrete", "minecraft:green_concrete"),
    pieces=(
        ("group", (0, 0, ("field", FARM, (M + "inferium_crop", M + "iron_crop", M + "diamond_crop"), 2, 7)),
         *[(dx, dz, ("column", INF, M + "inferium_growth_accelerator")) for dx in (-3, 3) for dz in (-3, 3)],
         (0, -3, ("stack", M + "essence_vessel", 1)), (0, 3, ("stack", M + "essence_vessel", 1)),
         (-3, 0, ("stack", M + "essence_vessel", 1)), (3, 0, ("stack", M + "essence_vessel", 1))),
        ("group", (0, 0, ("column", PRO, M + "infusion_altar")),
         *[(dx, dz, ("single", M + "infusion_pedestal")) for dx, dz in
           ((2, 0), (-2, 0), (0, 2), (0, -2), (2, 2), (-2, -2), (2, -2), (-2, 2))],
         *[(dx, dz, ("stack", M + "essence_vessel", 2)) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("field", FARM, (M + "diamond_crop", M + "inferium_crop"), 2, 4)),
         *[(dx, dz, ("column", M + "soulstone_bricks", M + "soulstone_bricks", M + "tertium_growth_accelerator")) for dx in (-3, 3) for dz in (-3, 3)],
         (0, 3, ("stack", M + "prosperity_block", 2)), (0, -3, ("stack", M + "inferium_block", 2))),
        ("group", (0, 0, ("column", M + "soulstone_smooth", M + "awakening_altar")),
         *[(dx, dz, ("column", M + "soulstone_bricks", M + "awakening_pedestal")) for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2))],
         (-3, -3, ("stack", M + "soulium_block", 1)), (3, 3, ("stack", M + "soulium_block", 1)),
         (3, -3, ("stack", M + "soulium_block", 1)), (-3, 3, ("stack", M + "soulium_block", 1)),
         (2, 2, ("single", M + "soul_extractor[facing=north,running=false]")), (-2, -2, ("single", M + "enchanter[facing=south]"))),
    ),
    wall=tuple(M + n for n in "harvester[facing=south,running=false] seed_reprocessor[facing=south,running=false] "
               "soul_extractor[facing=south,running=false] tinkering_table machine_frame infusion_pedestal "
               "inferium_block prosperity_block".split()),
    extra={"gate": (M + "soulstone_bricks", INF, M + "witherproof_glass", M + "essence_vessel")},
    ghost_rules="Crops are flat plants: every crop needs age (crop[age=0..7], 7 = mature) and farmland UNDER it "
                "(inferium_farmland[moisture=7]); only inferium_crop, iron_crop and diamond_crop are confirmed to draw. "
                "Altar and pedestal contents (floating items) are not drawn. Machines take facing and running=false. "
                "Use the farm field as the mass, the altars as the focus.",
    blocks=tuple(M + n for n in (
        "inferium_block prosperity_block imperium_block supremium_block soulium_block tertium_block prudentium_block "
        "inferium_farmland prudentium_farmland imperium_farmland supremium_farmland inferium_crop iron_crop diamond_crop "
        "gold_crop emerald_crop coal_crop redstone_crop lapis_lazuli_crop copper_crop "
        "inferium_growth_accelerator tertium_growth_accelerator imperium_growth_accelerator supremium_growth_accelerator "
        "infusion_altar infusion_pedestal awakening_altar awakening_pedestal essence_vessel soul_extractor "
        "seed_reprocessor harvester enchanter tinkering_table machine_frame soulstone soulstone_bricks soulstone_smooth "
        "soulstone_chiseled_bricks soulstone_cobble soul_glass witherproof_block witherproof_bricks witherproof_glass "
        "inferium_ingot_block inferium_gemstone_block prosperity_ingot_block").split()),
)
