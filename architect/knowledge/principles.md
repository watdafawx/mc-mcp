# Minecraft build principles (for ghost designers)

Target: All the Mods 10, MC 1.21.1 NeoForge. You output a palette of block ids plus `box` fills and single `set` blocks in LOCAL coordinates.
Pack decorative mods exist (Chipped, Rechiseled, Create, Supplementaries, Macaw's, Handcrafted, Framed Blocks, Simply Light), but use VANILLA for ~85% of any palette. Mod blocks are accents.
Block ids in `themes.json` and `multiblocks.md` are verified against the pack jars. Never invent ids. For a stairs/slab/wall variant, derive by suffix only when it exists (all vanilla stone, brick, wood, copper, sandstone and deepslate families have them).

## 0. Notation used below

```
box(x1,y1,z1 -> x2,y2,z2, block)      inclusive fill, any corner order
set(x,y,z, block)                     single block
x = east(+)/west(-), y = up, z = south(+)/north(-)
```
- y=0 is the FLOOR LAYER (floor blocks). Interior clear space is y=1..h, ceiling layer is y=h+1. Subfloor (for hidden lights) is y=-1. Walls/shell surround the interior box.
- **Stairs** (checked in the 1.21.1 model files): `facing` = the direction you climb; the tall back is on that side. `half=bottom|top`, `shape=straight|inner_left|inner_right|outer_left|outer_right`.
  `minecraft:oak_stairs[facing=north,half=bottom]` = steps rise toward -z, back on the north side. `half=top` is the upside-down version (overhang/cornice; the extra block hangs on the `facing` side).
- **Slabs**: `[type=bottom|top|double]`. **Trapdoors**: `[facing=dir,half=top|bottom,open=true|false]`. Checked in the models: with `open=true` the flap lies on the side OPPOSITE `facing` (facing=north -> flap against the block's south face; facing=west -> flap on the east face). See T6.
- **Logs/pillars**: `[axis=x|y|z]`. **Lanterns**: `[hanging=true]` hangs, `[hanging=false]` sits. **Chain**: `[axis=y]`. **Candles**: `[candles=1..4,lit=true]`.
- **Buttons**: `[face=wall|floor|ceiling,facing=dir,powered=false]`. **Fences/panes/walls/iron bars** auto-connect; set just the id.
- **minecraft:light[level=N]** places an invisible light; it is fine in ghosts but players cannot see it. Prefer real hidden blocks (L-rules) and use `light` only for filler glow.

---

## D. Depth and layering (walls are never flat)

Rule of thumb: every wall surface should have at least 3 different depth planes within any 4x4 window of blocks.

**D1. Three-plane wall.** Base wall plane, a pillar/recess plane, and a trim/overhang plane.
```
cross-section, looking down, wall facing +z (outside):
plane 0 (base):     stone_bricks wall at z=0
plane +1 (pillars): log pillars every 4 blocks at z=1
plane +2 (trim):    stair/slab cornice at the top y at z=2
plane -1 (recess):  windows set back at z=-1
```
Example: `box(0,0,0 -> 12,4,0, minecraft:stone_bricks)`; `set(4,0..4,1, minecraft:dark_oak_log[axis=y])` repeated at x=0,4,8,12; windows: remove blocks at x=2,y=1..2 and put `minecraft:glass_pane` at z=-1.

**D2. Inset windows.** Never put glass in the same plane as the wall. Place glass 1 block behind the wall plane (recessed) and frame it with stairs/slabs/trapdoors.
```
Window 2 wide x 2 tall at x=2..3, y=1..2 in a wall at z=0 (outside is +z, interior is -z):
  box(2,1,0 -> 3,2,0, air)                       hole in the wall plane
  box(2,1,-1 -> 3,2,-1, minecraft:glass_pane)    glass set 1 block back, inside the wall thickness
  sill:   set(2,0,1, minecraft:stone_brick_slab[type=top]) and set(3,0,1, same)        1 block proud of the wall
  lintel: set(2,3,0, minecraft:stone_brick_stairs[facing=south,half=top])  set(3,3,0, same)
  shutters (outside, z=1, flaps hug the window sides):
    set(1,1,1, minecraft:spruce_trapdoor[facing=west,half=bottom,open=true])    flap on the east side of its cell, next to the window
    set(4,1,1, minecraft:spruce_trapdoor[facing=east,half=bottom,open=true])    flap on the west side of its cell
```

**D3. Protruding pillars/buttresses.** Pillars 1 block proud of the wall, spaced 3-5 apart; caps in a different block. Corners get an L-shaped pillar.
`set(0..4, 0, 1)` as `minecraft:stripped_spruce_log[axis=y]`, cap `set(0,5,1, minecraft:spruce_slab[type=bottom])`.

**D4. Beams.** Horizontal timbers rest on pillars and run across the ceiling, 1 block lower than the ceiling plane.
With interior height h=5 (ceiling layer y=6): `box(0,5,2 -> 12,5,2, minecraft:dark_oak_log[axis=x])` and cross beams every 4 blocks `axis=z`. Beams hang 1 below the ceiling plane at y=h.

**D5. Overhang the top.** A roof/cornice should project 1-2 blocks past the wall; second floors project 1 block over the first.
Cornice: `box(-1,5,-1 -> 13,5,-1, minecraft:stone_brick_stairs[facing=north,half=top])` under a flat roof edge. Underside shows the stair's reverse shape.

**D6. Plinth/foundation.** The base course is 1-2 blocks and one step outward, in a darker/rougher block.
`box(-1,0,-1 -> 13,0,-1, minecraft:cobblestone)` under a plank wall, with a `stone_brick_stairs[...]` step lip.

**D7. Frame doors.** Doors/arches get a 1-block frame (different block) and sit 1 block inside the wall.
Door at `(5,0..1,0)`; frame: `set(4,0..2,0)`, `set(6,0..2,0)` trim logs, lintel `set(5,2,0)` stair upside-down; door set 1 block back at z=-1.

**D8. Replace solids with open blocks.** Where a plain wall panel is, substitute iron bars, panes, trapdoors, walls or fences for a lighter look. A 3x3 panel of `iron_bars` over a darker block behind it reads as depth.

**D9. Corners count.** Break every convex corner: use a pillar, a stair at 45 degrees (`shape=outer_left`), or a chamfer. Avoid 90-degree sharp edges of the same block on both faces.

**D10. Ceilings are surfaces too.** Coffers: inset 1 block panels of a different block between beams; slab grid; hanging banners. A flat ceiling is a mistake, same as a flat wall.

**D11. Flush-with-neighbours rule.** If two adjacent blocks of different type are in the same plane, the eye sees a stripe. If you want a stripe, make it intentional (1-wide, full length, in-line with other trim).

---

## P. Palettes (3-5 blocks, 60/30/10)

**P1. 60/30/10.** Primary 60% of surface (calm wall/floor block), secondary 30% (structure: pillars, beams, roof), accent 10% (doors, lamps, banners, signs, machine-matching colour).
Do not exceed 5 distinct full blocks. Variants of one family (stone bricks, cracked, mossy) count as ONE colour group but add texture.

**P2. Texture contrast, not just hue contrast.** Pair rough with smooth (cobblestone + polished andesite; planks + stone bricks) and dark with light. A palette of all similar mid-grays reads as a blob.
Good pairs: dark oak + white concrete; spruce + stone bricks; deepslate tiles + quartz; copper + deepslate; blackstone + cyan glass.

**P3. Value (light/dark) structure.** Frame darker than infill, or infill darker than frame, never equal. In a room, dark floor + mid walls + light ceiling feels grounded; the reverse feels floaty.

**P4. 3-4 step gradient.** To fade a surface use 3-4 same-colour blocks light-to-dark: smooth_stone, stone, andesite, polished_andesite... or concrete / terracotta / wool in one hue. Apply bottom-dark to top-light on towers, or edge-dark to centre-light for floors.
Example gradients: `white_concrete -> light_gray_concrete -> gray_concrete -> black_concrete`; `calcite -> diorite -> andesite -> polished_blackstone`; `birch_planks -> oak_planks -> spruce_planks -> dark_oak_planks`; `oxidized_cut_copper -> weathered_cut_copper -> exposed_cut_copper -> cut_copper`.

**P5. Noise/weathering (10-15%).** Replace random 10-15% of wall blocks with a related variant: stone_bricks -> cracked_stone_bricks, mossy_stone_bricks; planks -> darker planks; concrete -> gray concrete. Cluster the noise in patches (2-4 blocks), not single scattered pixels. Remove a few blocks at tops and corners and replace with stairs/slabs for broken edges (ruins/old builds).

**P6. Accent colour from the machine.** If a showcase machine is cyan/purple, echo that exact hue in 2-3 places (glass strip, banners, lights); nowhere else.

**P7. Rare materials are accents.** Gold, diamond, emerald, netherite, quantum alloy, fluix: small touches (a ring, a frame, a pedestal), never walls.

**P8. Lights are part of the palette.** Pick ONE light block family per room (sea lantern, lantern, shroomlight, end rod). Mixing 3 kinds looks noisy.

**P9. Colour temperature.** Warm palette (oak, orange, red, gold) with warm light (lantern, shroomlight, glowstone). Cool palette (concrete, quartz, deepslate, cyan) with cool light (sea lantern, soul lantern, end rod). Mismatch only for a deliberate accent.

**P10. Substitute colours.** Missing a hue? Pumpkin / terracotta for orange, melon / moss block for green, packed ice / blue ice for light blue, amethyst for purple, calcite for white-grey.

---

## S. Shape language

**S1. No plain boxes.** Every building mass needs at least one of: L/T/plus plan, stepped height, a projecting bay, a tower or turret, a roof of a different shape. For interiors: alcoves, bays, varied ceiling heights, a raised dais.

**S2. Odd widths for centred features.** If something needs a centre (door, pillar, machine, arch, aisle), the width must be odd (7, 9, 11, 15). Even widths force a 2-wide centre and look off.

**S3. Silhouette first.** Block the outline of a mass in 2-3 steps of height variation before any detail. A strong profile survives distance.

**S4. Symmetry with one break.** Symmetric spaces (axis along door to focal point) feel grand; add ONE asymmetry (a side tower, offset window, a corner prop) so it is not sterile.

**S5. Rule of repetition.** Repeat a module (bay) 3-5 times with identical rhythm, then break the rhythm once (a taller, wider or different one) at the focal point.

**S6. Roof types.**
```
Gable (ridge along x, walls z=0 and z=W):
  south slope: stairs[facing=north,half=bottom]  rising toward the ridge at z=W/2
  north slope: stairs[facing=south,half=bottom]
  ridge: slabs or a 1-block-wide row of full blocks at the top
  pitch: 1 up per 1 across (45 degrees) steep (fantasy); alternate stair+slab rows for a 2:1 shallow pitch
  eaves: extend the stair rows 1-2 blocks past the wall, with stair/slab under them as corbels
Hip: gable plus stairs[shape=outer_*] corners where slopes meet
Flat + parapet: flat slab roof, 1 high wall on the edge, slab cap on top, drain holes optional
Shed: one slope; use for lean-tos and add-ons
Dome/vault: stepped rings of stairs and slabs narrowing; see S9
```
**S7. Overhang the roof 1-2 blocks and put an under-eave row (upside-down stairs `half=top` or a log line) at the underside.** Roof edges that stop at the wall face look cut off.

**S8. Roof colour.** Roof is the secondary or accent colour, one step darker than the walls. Add dormers or small chimneys (2x2) to break long runs.

**S9. Arches.** 3-wide opening (x=1..3) between pillars at x=0 and x=4: at the top of the opening put upside-down stairs in the two upper corners, `set(1,h,0, stairs[facing=west,half=top])` and `set(3,h,0, stairs[facing=east,half=top])` (the hanging part sits on the pillar side), and a block or `slab[type=top]` at `(2,h,0)`. Wider arch (5-wide): the same corner stairs, then `slab[type=top]` or blocks across the middle. Make the arch 1 block taller than the door it frames.

**S10. Circles/discs.** Radius < 3 looks blocky; pick odd diameters. Filled disk row widths top to bottom, each row centred:
`d=5: 3,5,5,5,3` | `d=7: 3,5,7,7,7,5,3` | `d=9: 5,7,9,9,9,9,9,7,5` | `d=11: 5,7,9,11,11,11,11,11,9,7,5`. A ring = that disk minus the disk two sizes smaller (e.g. d=9 minus d=5 centred). Use for domes, dais, round windows and pools.

**S11. Tapering.** Towers, columns, and pillars get thinner or add a capital: base 1 wider than the shaft, capital = stairs flared outward.

**S12. Corners rounded in plan.** Replace the sharp corner block with a stair `[shape=outer_left]` + slabs to soften rooms and machine rooms.

---

## C. Scale for interiors

| Thing | Minimum | Comfortable | Grand |
|---|---|---|---|
| Door | 1w x 2h | 2w x 3h | 3w x 4h (hall: 5w x 5h arch) |
| Corridor | 2w x 3h | 3w x 4h | 5w x 5h |
| Room ceiling | 3 | 4-5 | 7-12 |
| Hall ceiling | 5 | 7 | 10-14 (castle hall 10-12) |
| Walkway beside a machine | 2 | 3 | 4-5 |
| Staircase | 1w | 3w | 5w |
| Seating gap between table rows | 2 | 3 | 4 |
| Window sill height | 1 | 1-2 | 2 |

**C1. Compress and release.** Narrow low corridor (3x4) -> tall wide hall (15x10). The contrast makes the hall feel huge.
**C2. Ceiling height proportional to room width.** Rule: height >= width / 3 for rooms, >= width / 2 for halls. A 15-wide hall wants 8-10 high.
**C3. Machine clearance.** For a machine of size N (7x7x7): keep >= 3 free blocks each side, >= 2 above, ceiling >= N + 4. For wall rooms with a machine against the wall, only the open sides count.
**C4. 3-wide is the unit.** Aisles, paths, bays, doors and stair runs in multiples of 3; spacing of pillars and windows in 4 (3 clear + 1 post).
**C5. Furniture scale.** Chair = 1 block (stairs or trapdoor), table = 1x2 or 1x3 (slab on fences/walls), bed = 2x1, counters = slabs on walls. Avoid furniture bigger than 2x3.
**C6. Vertical zoning.** Floor to 1 = furniture, 1-3 = main wall detail, 3+ = beams/lights/banners/windows. Don't pack all detail on the same row.
**C7. Eye line.** Players look at y=1.6: put detail (signs, labels, small machines) at y=1..2, big lights above y=3.

---

## T. Detailing with small blocks

**T1. Stairs.**
- Upside-down stairs `half=top` under an edge = cornice or corbel.
- Four stairs around a block = capital/pyramid cap; 2x2 of stairs facing out/in = pedestal.
- Stairs flush to a wall facing the room = bench or step; facing away = rain-ledge.
- Shape trick: `outer_left` / `outer_right` for rounded corners.

**T2. Slabs.** `type=top` against ceilings = recessed ceiling lip; `type=bottom` on floors = raised border; slabs on a wall top = cap; double slab = full block of a different texture (use sparingly). Half-height steps: floor of slab `bottom` + door 1 up.

**T3. Walls (cobblestone_wall, stone_brick_wall, etc.).** Thin posts, rails, table legs, chimney pots, lamp posts. A wall with a slab on top = pedestal/column; walls join sideways automatically.

**T4. Fences and fence gates.** Railings, chair backs, table legs, lattice, hanging lantern holders. `fence_gate[open=true]` as a decorative frame.

**T5. Iron bars.** Railings, cage doors, lattice windows, rack fronts, grating. Place in a plane 1 behind a wall for a recessed grille.

**T6. Trapdoors.** `open=true` = vertical panel (shutters, rack doors, vents, lamp shades, wall slats); `open=false,half=top` = thin panel flush with the ceiling of its cell (lowered ceiling, grille); `half=bottom,open=false` = thin plate on the floor of its cell (table top, hatch, rug). Use iron_trapdoor for tech, wood for rooms.
Open trapdoor: the flap lies on the side OPPOSITE `facing`. To get a vertical panel against the east side of a cell use `facing=west`; against the north side use `facing=south`.
```
Rack door on the +z face of a rack (flap against the cell's south side):  set(x,y,z, minecraft:iron_trapdoor[facing=north,half=bottom,open=true])
```

**T7. Buttons.** Tiny 'switch/dial' details on walls; `stone_button`/`polished_blackstone_button[face=wall,facing=north]` in a grid = control panel; a row of buttons above a lever = machine panel.

**T8. Chains.** `minecraft:chain[axis=y]` for hanging lamps (1-5 long), cable drops, roped signs; `[axis=x]` / `[axis=z]` as horizontal cables or bridge rails.

**T9. Lanterns.** `lantern[hanging=true]` under a chain or beam; `soul_lantern` for cold light. Chain + lantern pairs at different lengths for chandeliers.

**T10. Glass panes.** Panes are thinner than blocks (visual depth). Use panes for windows and glass blocks only for big lights/clear walls. Stained panes in a 2-3 colour pattern give stained glass. Pane + iron bars lattice = grid windows.

**T11. Carpets.** Rugs, runners, table cloths, shelves; carpet 'hides' light sources underneath (see L-rules). Carpet is passable at 1/16 height; ok as floor border.

**T12. Banners and heads.** Wall banners add colour + vertical lines, 3 long. Skull/head blocks as small props.

**T13. Pots, cauldrons, composters, barrels, hoppers.** Tables, planters, vats, funnels, kitchen props. A cauldron under a hopper = alchemy tub; a barrel top = round table.

**T14. Item frames/paintings.** Not blocks in a ghost; leave a 1 or 2-wide empty wall panel where one would go.

**T15. Doors as detail.** Open doors in alcoves, double doors (2-wide), trapdoors above doors (transoms).

**T16. Hanging and standing duplicates.** Keep a 2:1 rhythm: two small things then one large thing.

**T17. Props cluster.** Props go in groups of 2-4 in a corner or along a wall; leave the middle of the room clear for movement. A lone prop in the middle looks like debris.

**T18. Cable and pipe styling.** Cables/pipes run in straight lines with 90-degree turns, along wall-ceiling edges or in floor trenches; bundle 2-3 parallel runs with clamps (a different block every 4 blocks). They end into a port visibly (a plate or frame around the port).

---

## L. Lighting

**L1. Hide the source, show the glow.** Choose where the light comes from, then cover the emitter.
```
Under carpet:    set(x,0,z, minecraft:sea_lantern) ; set(x,1,z, minecraft:white_carpet)       light shines through the carpet (floor block is the lamp)
Under glass:     set(x,-1,z, minecraft:sea_lantern) ; set(x,0,z, minecraft:cyan_stained_glass)  glowing floor strip (needs subfloor y=-1)
Cove light:      glowstone/sea_lantern on a ledge, hidden by a slab[type=top] or stairs[half=top] lip in front
Behind panes:    lamp row + stained_glass_pane in front = neon strip / screen
Ceiling recess:  set(x,h+1,z, minecraft:sea_lantern) with trapdoor[half=top,open=false] at (x,h,z) as a grille
Lantern in alcove: lantern in a 1-wide recess in the wall with iron_bars in front
```
The carpet trick only works when the lamp is directly under the carpet (the floor block itself). A solid block between lamp and carpet blocks the glow.

**L2. Light level facts (1.21).** 15: sea_lantern, glowstone, shroomlight, lantern, froglight, redstone_lamp (lit), jack_o_lantern, lit campfire, beacon. 14: torch, end_rod. 12: 4 candles. 10: soul lantern/torch, crying obsidian. 7: enchanting table, glow lichen. 5: amethyst cluster. 3: candle (1), magma. Hostile spawn: block light must be 0, so any lit interior is safe; keep light level >= 8 in work spaces and dim (4-8) in moody areas.

**L3. Rhythm.** Lights at regular spacing (every 4 blocks along corridors; every 6 over open floors); a brighter focal light on the focal point; quieter ambient elsewhere.

**L4. Pools of light and shadow.** Not even floodlight. Alternate lit/unlit zones; put darker corners and bright focal spots. Leave rooms with a floor light 6-8 and a focal 12-15.

**L5. Vertical lighting.** Light the walls, not the floor: sconces/ lanterns on pillars at y=3, ceiling lights, floor-edge strips along walls to light up the wall. Down-lights in a ceiling make flat floor pools.

**L6. Chandeliers.** Chain 3-6 long from a beam/ceiling block, ring of 4-8 lanterns/candles at the end on a trapdoor/slab ring:
```
(centre at x0,z0; ceiling layer at y=h+1)
box(x0,h-2,z0 -> x0,h,z0, minecraft:chain[axis=y])             chain from the ceiling
set(x0,h-3,z0, minecraft:lantern[hanging=true])                  small version
bigger: set(x0,h-3,z0, minecraft:oak_fence); arms set(x0±1,h-3,z0) and set(x0,h-3,z0±1) as fence;
        lanterns set(x0±2,h-3,z0 / x0,h-3,z0±2, lantern[hanging=false]) and chains up from each arm tip
```
Hang chandeliers lower than the surrounding beams, not at ceiling level.

**L7. Floor/stair edge lights.** Under a stair step or slab lip: sea_lantern or glowstone 1 below the edge, hidden by an overhang.

**L8. Light blocks.** `minecraft:light[level=11..15]` for sky-light-like glow in showcase halls (invisible, cannot be seen). Use 2-4, hidden above beams.

**L9. Colored light via glass.** Put a lamp behind stained glass or panes: the glass colour tints the look (not the light). Use for neon lines (magenta, cyan), status rows (lime, red).

**L10. Fire safety in ghosts.** Torches, lava, fire, campfires: fine in ghosts but do not put wool/planks directly touching fire or lava. Use soul variants for cold looks.

**L11. Redstone lamp states.** Use `minecraft:redstone_lamp[lit=true]`; unlit lamps are plain grey. Use `copper_bulb[lit=true]` for a metal bulb; same.

---

## F. Floors (patterns, borders, inlays)

**F1. Always a border.** A 1-block band of a contrasting block along walls frames the room. `box(0,0,0 -> 14,0,0, border)` etc. around the perimeter and inset the field by 1.

**F2. Central inlay.** A medallion/cross/compass in the centre of halls; align with the main axis. Concentric squares: ring 0 = accent, ring 1 = secondary, field = primary.

**F3. Checker.** Alternating two blocks `(x+z)%2` (stone bricks / polished andesite; dark oak / spruce; black / white concrete). Use only in smaller rooms; for large halls use 3x3 or 4x4 checks.

**F4. Stripes/lanes.** A 1-wide or 3-wide strip leading to a door/machine, in a different block. Lane edges with slab/carpet.

**F5. Raised platforms.** Dais 1 step up (slab or stair) for focal points, 2 steps with a 3-wide stair for grand spaces.

**F6. Material per zone.** Different floor per function: stone bricks (halls), planks (living), concrete (tech), terracotta (desert), moss/path (garden).

**F7. Dirt-free interiors.** No grass/dirt inside buildings; use path/podzol/moss/coarse_dirt only in gardens.

**F8. Under-floor detail.** Cable runs: 1 deep trench under glass strips with an outline of copper; looks like conduit. Under-floor lights per L1.

**F9. Worn look.** Mix 10-15% cracked/mossy/other-shade tiles near doors and corners; dirt-stained edges along walls.

**F10. Floor-to-wall transition.** Baseboard: 1 block of slab/stair `half=bottom` along the base of walls; skirting in the trim block.

**Pattern recipe (square 15x15, floor y=0):**
```
box(0,0,0 -> 14,0,14, primary)
box(0,0,0 -> 14,0,0, border); box(0,0,14 -> 14,0,14, border); box(0,0,0 -> 0,0,14, border); box(14,0,0 -> 14,0,14, border)
box(2,0,2 -> 12,0,12, secondary)         inset ring
box(3,0,3 -> 11,0,11, primary)           field
box(6,0,6 -> 8,0,8, accent)              medallion 3x3
set(7,0,7, light_or_special)
```

---

## G. Landscaping and terrain blending (outside / garden)

**G1. Soften the base.** Where the build meets ground: foundation course (D6), then a ring of different blocks (gravel, path, coarse dirt) 1-2 wide, then plants.
**G2. Gradient into terrain.** Stone -> mossy stone -> moss block -> grass; no hard line between a stone plinth and grass.
**G3. Slopes.** Use stairs/slabs on slopes; build terraces (1 block step every 3-4 blocks) with retaining walls.
**G4. Paths.** 2-3 wide, wavy in plan, mixed blocks (path, gravel, coarse dirt, stone slabs) and a 1-block rim of grass or flowers; lanterns on posts every 6-8 blocks.
**G5. Vegetation layers.** Ground (grass, ferns, flowers, moss carpet), mid (bushes: leaves blocks; azalea; sweet berry), canopy (trees). Group in odd numbers.
**G6. Trees.** Trunk 1-2 thick, branches as logs sideways, canopy of 3 overlapping spheres rather than a single ball; hanging vines, leaf litter.
**G7. Water.** Ponds with stepped rims (slabs/stairs), lily pads, 3-4 depth; rivers 3-5 wide with banks of gravel/sand/clay.
**G8. Outdoor rooms.** Courtyards with 3 walls and a view; pergolas (fence posts + slab roof + vines); pavilions with 4 pillars.
**G9. Facade planting.** Flower boxes (trapdoors + flowers), vines on walls, hanging pots at windows, trellises.
**G10. Match biome.** Stone/ice/spruce in cold, sandstone/acacia in dry, jungle/bamboo in wet.

---

## R. Recipes (copy and adapt)

**R1. Pillar with capital (shaft 4 high, floor layer y=0):**
```
box(x,1,z -> x,4,z, minecraft:stripped_spruce_log[axis=y])           shaft
plinth ring (stairs climb toward the shaft):
  set(x,1,z+1, minecraft:stone_brick_stairs[facing=north]); set(x,1,z-1, ...[facing=south])
  set(x+1,1,z, ...[facing=west]);                          set(x-1,1,z, ...[facing=east])
set(x,5,z, minecraft:stone_brick_slab[type=top])                      capital (or 4 upside-down stairs around the top, facing outward)
```
**R2. Wall bay (4 wide, pillars at x=0 and x=4, wall plane z=0, outside +z):**
```
box(0,0,0 -> 4,5,0, minecraft:stone_bricks)                                  base wall
box(0,1,1 -> 0,5,1, pillar_log[axis=y]); box(4,1,1 -> 4,5,1, pillar_log[axis=y])   pillars proud 1
box(1,2,0 -> 3,4,0, air); box(1,2,-1 -> 3,4,-1, minecraft:glass_pane)         3x3 window, glass 1 back
box(1,1,1 -> 3,1,1, minecraft:stone_brick_slab[type=top])                     sill proud 1
box(1,5,1 -> 3,5,1, minecraft:stone_brick_stairs[facing=south,half=top])      lintel/cornice proud 1
```
**R3. Archway 3 wide, 4 tall (door on the z=0 plane, floor layer y=0):**
```
box(0,1,0 -> 0,5,0, pillar); box(4,1,0 -> 4,5,0, pillar)          pillars, one taller than the opening
opening x=1..3, y=1..3 (air)
set(1,4,0, stairs[facing=west,half=top]); set(3,4,0, stairs[facing=east,half=top]); set(2,4,0, block)   crown
```
**R4. Chandelier**: see L6.
**R5. Round-ish pillar 3x3:** `box(x-1,1,z-1 -> x+1,h,z+1, block)` then swap the 4 corner columns (x±1,z±1) at the top end for `slab[type=top]`, and put an upside-down stairs ring (`half=top`, facing outward) one layer under the capital. Keep the 4 face columns full.
**R6. Table 3x1:** legs `set(x,1,z, minecraft:oak_fence)` and `set(x+2,1,z, minecraft:oak_fence)`; top `box(x,2,z -> x+2,2,z, minecraft:oak_slab[type=bottom])`. Add stool seats as `oak_stairs[facing=...]` at z±1. Keep 3 blocks clear around tables and away from doors.
**R7. Bookshelf wall:** `box(0,1,0 -> 6,5,0, minecraft:bookshelf)` with every 3rd column replaced by a log pillar and one `lectern` or `chiseled_bookshelf` accent per row.
**R8. Rack (AE2 style, aisle on +z):** `box(0,1,0 -> 1,3,0, ae2:drive[facing=south])` 2 wide x 3 tall; side frame `minecraft:iron_bars` at x=-1 and x=2, cap `set(0..1,4,0, minecraft:iron_block)`, trapdoor 'door' `minecraft:iron_trapdoor[facing=north,half=bottom,open=true]` on alternate racks. (Drive `facing` is the visible face; the faces of ae2:drive have drive-bay slot textures.)
**R9. Catwalk (runs along x at height y, 3 wide, z=0..2):** floor `box(0,y,0 -> L,y,2, minecraft:smooth_stone_slab[type=bottom])` or iron grate look with `minecraft:iron_bars`/`copper_grate`; rails `box(0,y+1,0 -> L,y+1,0, minecraft:iron_bars)` and same at z=2; supports: `minecraft:chain[axis=y]` hangers or `stone_brick_wall` posts every 4 blocks; a `lantern` on every other post top.
**R10. Window wall (large):** frame 1-wide pillars every 4 and glass panes between 3 high; top beam `box(.., y=4, ..)` log axis x; sill slabs.

---

## M. Common mistakes (check before output)

1. Flat 1-block-thin walls with windows in the same plane. -> D1, D2.
2. Plain rectangular box room with a flat ceiling. -> S1, D10.
3. More than 5 block types, or a random mix. -> P1.
4. Same lightness everywhere (all mid-grey). -> P3.
5. Lights as bare torches or full-brightness emitters in plain view, evenly spaced across the ceiling. -> L1, L4.
6. Door the same size as the player (1x2) in a grand hall; or 1-wide corridors. -> C.
7. Empty room centre (nothing in the middle and nothing on walls). -> T17, S4.
8. Machine against a wall or touching the ceiling. -> multiblocks.md.
9. No floor pattern; floor the same block as the wall. -> F1.
10. Symmetric to the point of sterile (no break). -> S4.
11. Windows in a perfect grid with no rhythm change. -> S5.
12. Roof flush with walls; no overhang; same colour as walls. -> S7, S8.
13. Furniture lined up along the wall like soldiers. -> T17.
14. Ignoring the ghost block limit: prefer boxes to singles; repeat modules with loops, not 800 `set` calls.
15. Using ids from memory (mod blocks) not listed in the KB. -> Use only listed ids, else fall back to vanilla.
16. AE2 cables/terminals as ghost blocks (they are parts, not blocks). -> multiblocks.md.
17. Stairs/trapdoors facing the wrong way: stairs `facing` = climb direction; check with a 3-block test row mentally; flipped = `half=top`.
18. Lights adjacent to the machine face so the texture is washed out. -> aim light at the machine from above/the side, 2+ blocks away.
19. Unreachable rooms or sealed rooms (no doors). -> rooms.json connects.
20. Trees as single leaf balls; gardens as flat grass. -> G5, G6.

---

## Q. Quick self-check before you output

- [ ] Palette: 3-5 primary blocks + roles (primary/secondary/accent/trim/glass/light/floor).
- [ ] Every wall has pillars/recesses/trim (>=3 depth planes).
- [ ] At least 1 shape break (alcove, bay, tower, step) per room.
- [ ] Door sizes and corridor widths from C.
- [ ] Ceiling height from C2.
- [ ] A focal point with clear sight line.
- [ ] Lights hidden, in rhythm, and there is a pool of light at the focal point.
- [ ] Floor border + inlay.
- [ ] Props in clusters of 2-4, not lone.
- [ ] Every id is on the allowed list (themes.json) or plain vanilla.
