from . import ModRoom

P = "productivebees:"
V = "minecraft:"
HIVE = P + "advanced_oak_beehive[facing=south,honey_level=5,expanded=none]"
# v27 Productive Bees: an apiary. Wooden nests and advanced beehives (honey level 5) on honeycomb plinths, flower beds,
# centrifuges and a bottler, petrified honey and honey blocks. Vanilla flowers/bee nests are used as filler.
ROOM = ModRoom(
    theme="productivebees", name="Productive Bees", namespaces=("productivebees",),
    style="solarpunk", alt_styles=(),
    pad=(V + "honeycomb_block", P + "wax_block"),
    brief="Apiary: stacks of wooden bee nests and advanced oak beehives glowing with honey level 5, vanilla bee nests, "
          "flower beds (sunflowers, dandelions, poppies, cornflowers) around each cluster, honey and petrified honey "
          "pillars, a centrifuge, heated centrifuge and bottler row, amber blocks.",
    deck="minecraft:smooth_quartz", plinth=("minecraft:orange_concrete", "minecraft:yellow_concrete"), ring_dash=True,
    pieces=(
        ("group", (0, 0, ("stack", HIVE, 1)),
         (0, 0, ("ring", (V + "dandelion", V + "poppy", V + "cornflower", V + "azure_bluet", V + "allium"), 2)),
         *[(dx, dz, ("stack", P + "oak_wood_nest[axis=y,facing=south]", 2)) for dx in (-3, 3) for dz in (-3, 3)],
         (0, 3, ("stack", P + "orange_petrified_honey", 3)), (0, -3, ("stack", P + "yellow_petrified_honey", 3))),
        ("group", (0, 0, ("column", V + "bee_nest[facing=south,honey_level=5]", V + "bee_nest[facing=south,honey_level=5]", V + "bee_nest[facing=south,honey_level=5]")),
         (-2, 0, ("stack", P + "advanced_birch_beehive[facing=south,honey_level=5,expanded=none]", 2)),
         (2, 0, ("stack", P + "advanced_cherry_beehive[facing=south,honey_level=5,expanded=none]", 2)),
         (0, 2, ("stack", P + "sugarbag_nest[facing=south,honey_level=5]", 2)), (0, -2, ("stack", P + "bumble_bee_nest", 2)),
         *[(dx, dz, ("single", V + "sunflower[half=lower]")) for dx, dz in ((3, 3), (-3, -3), (3, -3), (-3, 3))],
         *[(dx, dz, ("single", V + "lilac[half=lower]")) for dx, dz in ((2, 2), (-2, -2), (2, -2), (-2, 2))]),
        ("group", (0, 0, ("stack", P + "powered_centrifuge[running=false]", 1)),
         (-2, 0, ("stack", P + "heated_centrifuge[running=false]", 1)), (2, 0, ("stack", P + "centrifuge[running=false]", 1)),
         (0, 2, ("stack", P + "bottler[has_bottle=false]", 1)), (0, -2, ("stack", P + "incubator", 1)),
         (-3, 0, ("stack", P + "honey", 2)), (3, 0, ("stack", P + "honey", 2)),
         *[(dx, dz, ("stack", P + "amber[facing=south]", 2)) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("stack", P + "breeding_chamber", 1)),
         (-2, 0, ("stack", P + "gene_indexer", 1)), (2, 0, ("stack", P + "cryo_stasis", 1)),
         (0, 2, ("stack", P + "catcher", 1)), (0, -2, ("stack", P + "honey_generator[full=false,facing=south,on=false]", 1)),
         *[(dx, dz, ("stack", P + "advanced_oak_beehive[facing=south,honey_level=5,expanded=none]", 3)) for dx in (-3, 3) for dz in (-3, 3)],
         (-2, -2, ("single", V + "sunflower[half=lower]")), (2, 2, ("single", V + "sunflower[half=lower]"))),
    ),
    wall=tuple(P + n for n in "centrifuge heated_centrifuge powered_centrifuge bottler incubator breeding_chamber "
               "gene_indexer honey wax_block petrified_honey".split()),
    extra={"gate": (P + "oak_wood_nest[axis=y,facing=south]", P + "wax_block", V + "honeycomb_block", P + "amber[facing=south]")},
    ghost_rules="Bees themselves are not drawn. Nests and hives have state: advanced_*_beehive[facing=...,honey_level=0..5,"
                "expanded=none], *_wood_nest[axis=y,facing=...], sugarbag_nest[facing=...,honey_level=...]; honey_level=5 shows "
                "the dripping honey face. Only these confirmed families are whitelisted; use vanilla flowers (dandelion, "
                "poppy, sunflower[half=lower]) round them.",
    blocks=tuple(P + n for n in (
        "oak_wood_nest acacia_wood_nest sugarbag_nest sugar_cane_nest bumble_bee_nest advanced_oak_beehive "
        "advanced_birch_beehive advanced_cherry_beehive advanced_jungle_beehive advanced_dark_oak_beehive "
        "advanced_spruce_beehive expansion_box_oak expansion_box_birch bamboo_hive dragon_egg_hive inactive_dragon_egg "
        "feeder centrifuge heated_centrifuge powered_centrifuge incubator bottler catcher breeding_chamber gene_indexer "
        "cryo_stasis honey_generator honey jar_oak amber wax_block petrified_honey orange_petrified_honey "
        "yellow_petrified_honey white_petrified_honey red_petrified_honey comb_milky comb_powdery configurable_comb").split()),
)
