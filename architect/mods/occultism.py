from . import ModRoom

O = "occultism:"
OB, OP, OS = O + "otherstone_bricks", O + "polished_otherstone", O + "otherstone"
GLYPH = tuple(O + f"chalk_glyph_{c}[facing=north,sign={n}]" for c, n in
              (("gold", 3), ("white", 8), ("gold", 11), ("white", 1), ("gold", 6), ("white", 12)))
# v27 Occultism: a ritual hall. Chalk-glyph circle round a golden sacrificial bowl altar, candle pillars, a storage
# controller ringed by stabilizers, spirit fire and lanterns. Glyphs are flat decals on the floor.
ROOM = ModRoom(
    theme="occultism", name="Occultism", namespaces=("occultism",),
    style="gothic", alt_styles=(),
    pad=(OB, OP),
    brief="Ritual hall of pale cream otherstone on a black floor: a chalk-glyph circle (gold and white) round a pentacle altar of "
          "golden sacrificial bowls, tall otherstone pillars with spirit lanterns, a storage controller ringed by "
          "stabilizers, an iesnium anvil, silver and iesnium blocks, large purple candles and a spirit campfire.",
    deck="minecraft:black_concrete", plinth=("minecraft:purple_concrete", "minecraft:gray_concrete"),
    pieces=(
        ("group", (0, 0, ("column", OB, O + "golden_sacrificial_bowl")),
         (0, 0, ("ring", GLYPH, 2)),
         *[(dx, dz, ("single", O + "golden_sacrificial_bowl")) for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2))],
         *[(dx, dz, ("column", OB, OB, OB, OB, O + "spirit_lantern[hanging=false]")) for dx in (-3, 3) for dz in (-3, 3)],
         (-3, 0, ("stack", O + "large_candle_purple", 1)), (3, 0, ("stack", O + "large_candle_purple", 1)),
         (0, -3, ("stack", O + "large_candle_white", 1)), (0, 3, ("stack", O + "large_candle_white", 1))),
        ("group", (0, 0, ("stack", O + "storage_controller", 2)),
         (-2, 0, ("stack", O + "storage_stabilizer_tier3[facing=up]", 1)), (2, 0, ("stack", O + "storage_stabilizer_tier3[facing=up]", 1)),
         (0, 2, ("stack", O + "storage_stabilizer_tier5[facing=up]", 1)), (0, -2, ("stack", O + "storage_stabilizer_tier5[facing=up]", 1)),
         *[(dx, dz, ("column", OB, OB, O + "iesnium_block", O + "spirit_attuned_crystal")) for dx in (-3, 3) for dz in (-3, 3)]),
        ("group", (0, 0, ("column", OP, O + "celestial_chalice")),
         (0, 0, ("ring", GLYPH[::-1], 3)),
         (-2, 0, ("column", OB, O + "silver_sacrificial_bowl")), (2, 0, ("column", OB, O + "silver_sacrificial_bowl")),
         (0, 2, ("column", OB, O + "copper_sacrificial_bowl")), (0, -2, ("column", OB, O + "dark_sacrificial_bowl")),
         (-2, -2, ("single", O + "iesnium_anvil[facing=east]")), (2, 2, ("single", O + "spirit_campfire[facing=north,lit=true]"))),
        ("group", (0, 0, ("column", OB, O + "dimensional_mineshaft[rotation=0]")),
         (-2, 0, ("stack", O + "iesnium_block", 1)), (2, 0, ("stack", O + "silver_block", 1)),
         (0, 2, ("single", O + "dimensional_extractor")), (0, -2, ("single", O + "eldritch_chalice")),
         *[(dx, dz, ("column", OB, OB, OB, O + "spirit_torch")) for dx in (-3, 3) for dz in (-3, 3)],
         (-2, 2, ("single", O + "spirit_fire[color=void]")), (2, -2, ("single", O + "spirit_fire[color=purple]"))),
    ),
    wall=tuple(O + n for n in "storage_controller storage_stabilizer_tier2 iesnium_block silver_block otherstone_bricks "
               "chiseled_otherstone_bricks dimensional_extractor polished_otherstone".split()),
    extra={"gate": (OB, O + "chiseled_otherstone_bricks", O + "iesnium_block", O + "spirit_lantern[hanging=true]")},
    ghost_rules="Floating items and ritual particles are not drawn. Chalk glyphs are flat floor decals "
                "(chalk_glyph_<colour>[facing=north,sign=0..13], mix colours, one block each); sacrificial bowls draw as "
                "bowls; spirit_fire[color=...] is a flat flame. Otherstone family is the mass; keep the iesnium and silver "
                "blocks as accents.",
    blocks=tuple(O + n for n in (
        "otherstone polished_otherstone otherstone_bricks chiseled_otherstone_bricks cracked_otherstone_bricks otherrock "
        "otherrock_bricks othercobblestone otherplanks otherworld_log otherworld_leaves otherstone_pedestal "
        "otherstone_pedestal_silver golden_sacrificial_bowl silver_sacrificial_bowl copper_sacrificial_bowl "
        "dark_sacrificial_bowl sacrificial_bowl storage_controller storage_controller_stabilized storage_stabilizer_tier0 "
        "storage_stabilizer_tier1 storage_stabilizer_tier2 storage_stabilizer_tier3 storage_stabilizer_tier4 "
        "storage_stabilizer_tier5 dimensional_mineshaft dimensional_extractor stable_wormhole iesnium_block "
        "silver_block iesnium_anvil spirit_attuned_crystal celestial_chalice eldritch_chalice spirit_lantern spirit_torch "
        "spirit_fire spirit_campfire spirit_grindstone large_candle_purple large_candle_white large_candle_black "
        "chalk_glyph_white chalk_glyph_gold chalk_glyph_red chalk_glyph_purple chalk_glyph_black chalk_glyph_blue "
        "datura otherflower").split()),
)
