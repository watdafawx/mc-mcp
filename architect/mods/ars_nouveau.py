from . import ModRoom

A = "ars_nouveau:"
SS, SSL, SM = A + "sourcestone", A + "sourcestone_large_bricks", A + "smooth_sourcestone"
LOG, LEAF = A + "purple_archwood_log[axis=y]", A + "purple_archwood_leaves"
# v27 Ars Nouveau: a sourcestone sanctum. Enchanting apparatus on a ring of arcane pedestals, an imbuement chamber,
# a scribe library, an archwood grove. Block-entity blocks (jars, apparatus, pedestals) draw their base model.
ROOM = ModRoom(
    theme="ars_nouveau", name="Ars Nouveau", namespaces=("ars_nouveau",),
    style="gothic", alt_styles=("hextech",),
    pad=(SM, SSL),
    brief="Source-magic sanctum: dark purple sourcestone with gilded trim on a pale floor, an enchanting apparatus ringed by four "
          "arcane pedestals and source jars, an imbuement chamber with relays and prisms, a scribe's library (scribes "
          "table, alteration table, lecterns), a purple archwood tree with leaf crown, source lamps on sourcestone pillars.",
    deck="minecraft:smooth_quartz", plinth=("minecraft:purple_concrete", "minecraft:light_gray_concrete"), ring_dash=True,
    pieces=(
        ("group", (0, 0, ("column", SSL, A + "enchanting_apparatus")),
         (2, 0, ("column", SS, A + "arcane_pedestal")), (-2, 0, ("column", SS, A + "arcane_pedestal")),
         (0, 2, ("column", SS, A + "arcane_pedestal")), (0, -2, ("column", SS, A + "arcane_pedestal")),
         *[(dx, dz, ("column", SSL, SSL, SSL, SSL, A + "source_lamp[lit=true]")) for dx in (-3, 3) for dz in (-3, 3)],
         (2, 2, ("single", A + "source_jar[fill=11]")), (-2, -2, ("single", A + "source_jar[fill=11]")),
         (2, -2, ("single", A + "potion_jar[fill=11]")), (-2, 2, ("single", A + "potion_jar[fill=11]"))),
        ("group", (0, 0, ("column", SSL, A + "imbuement_chamber")),
         (-3, 0, ("column", SS, A + "arcane_pedestal")), (3, 0, ("column", SS, A + "arcane_pedestal")),
         (0, 3, ("column", SSL, SSL, A + "spell_prism[facing=north]")), (0, -3, ("column", SSL, SSL, A + "void_prism")),
         (-2, -2, ("single", A + "relay")), (2, 2, ("single", A + "relay")),
         (-2, 2, ("column", SS, A + "ritual_brazier")), (2, -2, ("column", SS, A + "ritual_brazier"))),
        ("group", (0, 0, ("column", SSL, A + "scribes_table")),
         (-2, 0, ("single", A + "alteration_table")), (2, 0, ("single", A + "alteration_table")),
         (0, 2, ("single", A + "storage_lectern")), (0, -2, ("single", A + "planarium")),
         (-3, -3, ("stack", A + "repository", 2)), (3, 3, ("stack", A + "repository", 2)),
         (3, -3, ("stack", A + "arcane_core", 1)), (-3, 3, ("stack", A + "arcane_core", 1))),
        ("group", (0, 0, ("stack", LOG, 5)), (0, 0, ("blob", LEAF, 2, 6)),
         (-2, -2, ("stack", A + "magebloom_block", 1)), (2, 2, ("stack", A + "magebloom_block", 1)),
         (2, -2, ("stack", A + "magebloom_block", 1)), (-2, 2, ("stack", A + "magebloom_block", 1)),
         *[(d, 0, ("single", A + "sourceberry_bush[age=3]")) for d in (-3, 3)],
         (0, 3, ("single", A + "whirlisprig_flower")), (0, -3, ("single", A + "source_gem_block"))),
    ),
    wall=tuple(A + n for n in "repository storage_lectern scribes_table alteration_table planarium source_gem_block mage_block arcane_core".split()),
    extra={"gate": (SSL, A + "gilded_sourcestone_large_bricks", A + "gold_grate[facing=up]", A + "source_lamp[lit=true]")},
    ghost_rules="Block-entity parts (floating items, the apparatus book, jar contents) are not drawn: the apparatus, pedestals "
                "and jars show as their base model, a jar's fill state is only a colour. Use [fill=0..11] on source_jar and "
                "potion_jar, facing on pedestals. Crops need age: magebloom_crop[age=7]. Sourcestone variants are the mass "
                "(gilded for trim); archwood logs [axis=y], leaves plain.",
    blocks=tuple(A + n for n in (
        "sourcestone smooth_sourcestone sourcestone_large_bricks sourcestone_small_bricks sourcestone_mosaic "
        "sourcestone_basketweave sourcestone_alternating gilded_sourcestone_large_bricks gilded_sourcestone_small_bricks "
        "gilded_sourcestone_mosaic smooth_gilded_sourcestone_large_bricks "
        "sourcestone_large_bricks_stairs sourcestone_large_bricks_slab sourcestone_grate gold_grate archwood_planks "
        "purple_archwood_log blue_archwood_log green_archwood_log red_archwood_log purple_archwood_leaves "
        "blue_archwood_leaves green_archwood_leaves red_archwood_leaves magebloom_block magebloom_crop mage_block "
        "source_gem_block source_jar potion_jar enchanting_apparatus arcane_pedestal imbuement_chamber arcane_core "
        "scribes_table alteration_table storage_lectern repository planarium scryers_crystal "
        "wixie_cauldron relay spell_prism void_prism ritual_brazier source_lamp sourcestone_sconce alchemical_sourcelink "
        "vitalic_sourcelink agronomic_sourcelink volcanic_sourcelink spell_turret falseweave mirrorweave arcane_platform "
        "potion_melder potion_diffuser scryers_oculus sourceberry_bush whirlisprig_flower").split()),
)
