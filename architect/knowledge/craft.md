# Build craft: what makes a build look designed, not like boxes

Distilled from 22 reference builds (the user's mood board, `knowledge/style_refs/`). Read this before any
exterior. The shapes tool kinds `structure`, `platform`, `bridge`, `slope`, `spire` do most of it for you.

## A. Composition (the whole build)
1. **One idea, one silhouette.** Every good reference has a readable overall shape: a ring around a core (space
   station), a tall tower with a crown (telescope tower, eco tower), a platform on legs (sea rig), a stepped
   ziggurat. Pick it first and say it in the plan in one sentence.
2. **Hierarchy of heights 1 : 2 : 3+.** Low wings, a mid block, one landmark that is clearly the tallest
   (spire, antenna mast, dish, dome). Never all wings the same height.
3. **Set it on a base.** A platform/island/plinth 1-3 blocks high, slightly larger than the buildings, with a
   stepped or patterned edge (the snowy disc, the road tile, the sea legs). This alone makes a build look finished.
4. **Overlap volumes, don't line them up.** Wings plug INTO the hub (overlap 2-4 blocks), upper floors set back or
   cantilever over lower ones, a curved wing wraps a square core. Separate floating boxes joined by thin tubes read
   as a diagram.
5. **Mix footprints.** At least one non-rectangle: ring sector, octagon, round, L, or a slope. Curves against
   straight blocks is the single strongest contrast in the references.
6. **Connect with designed links**: glass sky-bridges (`bridge`), stairs, ramps, railings. Corridors are
   architecture too.

## B. Facade (every wall bigger than 5x5)
1. **Depth layers, 2-3 deep.** Wall plane, trim/pillars 1 block proud, windows 1 block recessed. A flat wall is
   the #1 sign of a beginner build. (`structure` does this: ledges + pillars on the outer ring, walls 1 in.)
2. **Horizontal bands** at every floor line (ledges cast shadow lines) and **one accent stripe** in a bold colour
   (orange/red on white, cyan on dark, copper on brick). Bands wrap the whole volume, including curves.
3. **Rhythm.** Mullions/pillars every 3-5 blocks; windows as continuous bands (modern), grids (office) or tall
   slits (gothic). Keep the bay the same across a building.
4. **Light as material.** A glow band (froglight / sea lantern / shroomlight) under a ledge or in the top lintel;
   lights at entrances; glowing floor strips in corridors. Dark palettes need more glow.
5. **Palette discipline: 3 + 1 + glow.** Main wall, secondary (trim), dark/base, ONE accent colour, one glow.
   Use a kit (`kit=station_white|cyber_dark|ae_sky|steampunk|gothic|solarpunk|rust_industrial`) and keep it
   for the whole base; vary it only with `roles` overrides.

## C. Roofline (what the eye reads from far away)
1. Parapet with a rail, never a bare flat edge.
2. Rooftop clutter: vents, AC units, tanks, pools, solar/greenery, 1-3 antennas with a red/lit tip.
3. Pitched/sloped roofs on purpose: a glass slope (`slope`), a stepped crown, a dish, a dome. Real roofs use
   stairs (`gable_roof`, `pyramid_roof`).

## D. Detail scale (greebling)
1. Break big surfaces every 4-6 blocks with something: a pillar, a vent, a sign panel, a pipe run, a light.
2. Pipes and cables run along walls and between buildings (copper/iron bars/chains), with brackets.
3. Entrances are framed: steps, a canopy, lights both sides, a door recess.
4. Small life: planters, vines, banners/signs, benches (refs: cyber shop, solarpunk tower, sea rig).

## E. Interiors (machine halls)
1. Machine on a dais/plinth, framed by pillars, lit from below or behind; floor pattern (grid lines, hazard
   stripes, a ring around the centrepiece) that points at it.
2. Racks in rows with aisles (2-3 wide) and a light strip per row; cable trays in the ceiling.
3. Height: 1.5-2x the machine height; a gallery/balcony level for big halls.

## F. Style kits mapped to the mood board
- **station_white**: space station ring, sausbuilds lab, ramp greenhouse. White + light grey + orange/red stripe,
  blue glass, warm light bands, antennas with red tips.
- **cyber_dark**: data core, cyber motorbike shop, energy core lab. Deepslate/basalt, cyan glow panels, hazard
  stripes (black/yellow concrete), orange accents, signs.
- **steampunk**: workshop diorama, chronocap tower, armillary. Dark brick, copper trim and pipes, warm lights,
  gears (copper rings), wooden furniture.
- **gothic**: telescope tower. Blackstone/deepslate, pale quartz/calcite banding, chains and lanterns, tall
  slit windows, stacked tiers.
- **solarpunk**: eco tower with tree, ramp greenhouse. White + wood + glass + moss roofs, planters, a tree on top.
- **hextech** (Arcane / Piltover; real-world roots: Art Deco + Art Nouveau + Belle Epoque Paris): cream/white
  stone (calcite, quartz, smooth sandstone), quartz vertical piers and frames (NO gold or yellow blocks, no gold emblem on facades; brass only as tiny accents), art-deco chevron/diamond lattice in
  windows (purple glass), blue-teal mansard roofs with dormers (dark prismarine), glass domes with dark ribs,
  hextech-blue glow (sea lantern, light blue glass, crystal clusters). Landmarks: stepped tower crowns with
  finials, sphere-and-gear tops, giant brass gears/armillary rings on facades, round rose windows. Strict symmetry
  on main facades, grand stairs at entrances, lamps and trees on plazas.
- **rust_industrial**: sea rig. Teal concrete, rusty copper frames, iron bars rails, stairs on the outside, vines.
