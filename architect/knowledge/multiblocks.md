# Showing off mod multiblocks (ATM10: AE2 19.2.18, ExtendedAE 2.2.43, AdvancedAE 1.6.12)

Rules marked **[jar]** were read from the mods' own guide files inside the jars (`assets/<mod>/ae2guide/...`). **[unverified]** = from memory or inferred; confirm in game.

## 0. Ghost caveats (read first)

- **AE2 cables, buses, terminals, monitors-on-cable, panels, level emitters, etc. are PARTS placed on `ae2:cable_bus`, not blocks.** A ghost cannot contain them. Do not put `ae2:*_terminal`, `ae2:*_glass_cable`, `ae2:*_covered_cable`, `ae2:*_bus` in a ghost.
  `ae2:cable_bus` exists as a block id (blockstate verified) but an empty one is invisible/non-functional **[unverified]**. Do not use it.
- Real blocks you CAN ghost: `ae2:controller`, `ae2:crafting_unit`, `ae2:{1k,4k,16k,64k,256k}_crafting_storage`, `ae2:crafting_accelerator`, `ae2:crafting_monitor[facing=..]`, `ae2:molecular_assembler`, `ae2:pattern_provider`, `ae2:interface`, `ae2:drive[facing=..,spin=0..3]`, `ae2:inscriber`, `ae2:charger`, `ae2:io_port`, `ae2:energy_cell[fullness=0..4]`, `ae2:dense_energy_cell`, `ae2:creative_energy_cell`, `ae2:vibration_chamber`, `ae2:spatial_pylon`, `ae2:spatial_io_port`, `ae2:quantum_ring`, `ae2:quantum_link`, `ae2:wireless_access_point[facing=..]`, `ae2:spatial_anchor`, `ae2:sky_stone_tank`, `ae2:sky_stone_chest`, `ae2:chest`, `ae2:condenser`, `ae2:cell_workbench`, `ae2:light_detector`, decor: `ae2:quartz_block`, `ae2:quartz_pillar[axis=y]`, `ae2:chiseled_quartz_block`, `ae2:quartz_bricks`, `ae2:cut_quartz_block`, `ae2:smooth_quartz_block`, `ae2:fluix_block`, `ae2:sky_stone_block`, `ae2:smooth_sky_stone_block`, `ae2:sky_stone_brick`, `ae2:sky_stone_small_brick`, `ae2:quartz_glass`, `ae2:quartz_vibrant_glass`, `ae2:quartz_fixture[facing=..,odd=false]`, `ae2:matrix_frame`, plus the stairs/slabs/walls (`ae2:fluix_stairs`, `ae2:quartz_slab`, ...).
- Formed-state: multiblock blocks look "unformed" in a ghost; once the player builds the real thing they auto-form. Do not set `formed=true` in ghost states unless asked.
- Cable stand-ins (visual only): a 1-wide line of `minecraft:light_blue_stained_glass_pane` or `minecraft:cyan_stained_glass_pane` (reads as a glass cable), `minecraft:end_rod[facing=..]` (thin conduit), `minecraft:chain[axis=x|z]` (hanging loom), `minecraft:iron_bars` bundles, `ae2:fluix_slab`/`minecraft:purple_stained_glass` for covered cable. Put a note in the ghost description that real cables must be placed by the player along those lines. Keep the same colour for the same network.

## 1. Machine rules

### 1.1 AE2 Controller **[jar: ae2guide/items-blocks-machines/controller.md]**
- Blocks: `ae2:controller`. Any number up to the size limit; all must be connected (touching) or the stray ones turn red.
- Bounding box must be within **7x7x7**.
- Each controller block may have neighbours on BOTH opposite sides in at most **one axis**. (A block that has neighbours on both sides in two or three axes disables itself and turns red.)
- One controller network per ME network. 32 channels per face. 6 AE/t per controller block, 8000 AE stored per block; needs energy (cells) plus a cable connection.
- Auto-orientation: the block's `type` (block, column_x/y/z, inside_a/b) and `state` (offline/online/conflicted) update themselves. Place plain `ae2:controller`.
- **Valid pretty shapes** (derived from the rule; interior of shapes with 3 axes full is invalid):
  - Wireframe cube frame up to 7x7x7: 8 corners + 12 edges, 68 blocks for the full 7-cube. Hollow interior 5x5x5. (corner = 1 neighbour per axis, edge block = both neighbours in 1 axis. valid)
  - Straight lines/columns, L shapes, rectangular rings in one plane, 2-thick slabs/plates, stepped staircases of controllers.
  - **Invalid**: filled 3x3 squares or cubes, solid walls 3+ thick, plus-shaped crosses, hollow cube with solid faces (face centres have two full axes).
- Showcase idea: 7x7x7 cube frame on a pedestal with a beacon-like glow core floating in the middle (`minecraft:sea_lantern` or `ae2:energy_cell[fullness=4]` chain-suspended), cables entering from below.

### 1.2 Crafting CPU **[jar: crafting_cpu_multiblock.md]**
- Solid **rectangular prism, no gaps**. At least one crafting storage block (a single `ae2:1k_crafting_storage` is a valid CPU). Parts: `ae2:crafting_unit` (filler), `ae2:{1k,4k,16k,64k,256k}_crafting_storage`, `ae2:crafting_accelerator` (co-processor), `ae2:crafting_monitor` (face display).
- Max edge length is not in the guide **[unverified; AE2 default is 16]**.
- Pretty build: 3x3x5 or 5x5x5 block, monitors on one face as an eye row, accelerators on corners/edge columns visible from outside, storage in the interior; a different `crafting_unit` frame colour is not possible (one texture), so frame it with a surrounding ring/dais instead.

### 1.3 AdvancedAE Quantum Computer **[jar: advanced_ae ae2guide/aae_intro/quantum_computer.md + structure/quantum_computer_multiblock.snbt]**
- External size up to **7x7x7** (server config can change it; the item tooltips show the limit).
- **No empty spaces inside.** Gaps are filled with `advanced_ae:quantum_unit` (no benefit, only filler).
- **Exactly one** `advanced_ae:quantum_core`.
- At most one `advanced_ae:data_entangler` and at most one `advanced_ae:quantum_multi_threader`.
- **Every block of the outer layer must be `advanced_ae:quantum_structure`.** **No quantum_structure on the inside.** Inside may contain: core, `advanced_ae:quantum_unit`, `advanced_ae:quantum_storage_128`, `advanced_ae:quantum_storage_256`, `advanced_ae:quantum_accelerator`, the entangler and the multi-threader.
- The core alone (1 block) already works standalone; power via its up/down connector faces **[jar]**.
- Smallest sensible multiblock: 3x3x3 (26 structure + 1 core inside) **[inferred from the outer-layer rule]**.
- The 7x7x7 guide structure: 218 structure blocks on the shell (7^3 - 5^3 = 343 - 125 = 218) and 125 interior blocks.
- Showcase: since only the shell is visible, put the visual drama around it: pedestal, ring of `advanced_ae:quantum_alloy_block` stairs/slabs/walls (`advanced_ae:quantum_alloy_stairs`, `advanced_ae:quantum_alloy_slab`, `advanced_ae:quantum_alloy_wall`), `minecraft:end_rod` pillars, and `minecraft:purple_stained_glass` light panels behind the dais. A glass-walled hall with the machine floating 1 block above a dark floor (4 slab corner supports) reads great.

### 1.4 ExtendedAE Assembler Matrix **[jar: extendedae ae2guide/epp_intro/assembler_matrix.md]**
- A **rectangular prism with every edge length between 3 and 7** (so 3x3x3 up to 7x7x7, each axis independent).
- **Edges (the 12 edges incl. the 8 corners) = `extendedae:assembler_matrix_frame`.**
- **Faces (the 6 face interiors) = `extendedae:assembler_matrix_wall` or `extendedae:assembler_matrix_glass`.**
- **Interior = `extendedae:assembler_matrix_pattern` / `extendedae:assembler_matrix_crafter` / `extendedae:assembler_matrix_speed`.** Completely filled, no hollow.
- Needs at least 1 pattern core and 1 crafter core. A pattern core gives 36 pattern slots; a crafter core runs 8 jobs; 5 speed cores saturate speed (more is wasted).
- Frame state: `extendedae:assembler_matrix_frame[shape=block]` for the 8 corners, `[shape=column_x]`/`column_y`/`column_z` for edges along that axis (from the guide structure). The lines on the frame turn blue when formed and powered.
- Showcase: 5x5x5 with 2 glass faces to see the cores; or an elongated 7x3x5 slab shape; put it on a dais with the frame edges glowing at the base. Place pattern providers (`ae2:pattern_provider`) or `extendedae:ex_pattern_provider` nearby as feeders.

### 1.5 AE2 Quantum Network Bridge **[jar: quantum_bridge.md]**
- 1 `ae2:quantum_link` surrounded by 8 `ae2:quantum_ring` in a 3x3 flat ring (any orientation). Only the 4 rings adjacent to the link accept cables; the 4 corner rings do not.
- Needs two such bridges (one per side), both chunk-loaded **[jar]**. Showcase: two 3x3 gates facing each other across a hall, a glass floor between them.

### 1.6 AE2 Spatial IO **[jar: spatial-io.md]**
- `ae2:spatial_io_port` adjacent to a wireframe of `ae2:spatial_pylon` blocks that outline the volume to swap (only edges). Great as a "cage" showcase around a platform. Entities inside are carried along.

### 1.7 Other AE2/AAE/EAE standalone blocks
`advanced_ae:reaction_chamber`, `advanced_ae:quantum_crafter`, `advanced_ae:adv_pattern_provider`, `advanced_ae:small_adv_pattern_provider`, `extendedae:ex_drive`, `extendedae:ex_io_port`, `extendedae:ex_molecular_assembler`, `extendedae:ex_pattern_provider`, `extendedae:ex_interface`, `extendedae:oversize_interface`, `extendedae:ingredient_buffer`, `extendedae:caner`, `extendedae:circuit_cutter`, `extendedae:crystal_assembler`, `extendedae:wireless_hub`, `extendedae:machine_frame`, `extendedae:silicon_block`, `extendedae:entro_block`. Use them like AE2 machines: in bays, framed.

### 1.8 ExpandedAE (ATM10 mod id `expandedae`) **[jar: expandedae-2.1.4 ae2guide + blockstates + en_us]**
Not the same mod as ExtendedAE (`extendedae`). It extends the AE2 crafting CPU and adds bigger providers.
- **Crafting CPU parts** (all have `formed=true|false`, same rules as 1.2: solid rectangular prism, no gaps, at least one storage):
  `expandedae:exp_crafting_unit` (filler), co-processors `expandedae:exp_crafting_accelerator_{2,4,8,16,32,64,128,256,512}` (threads),
  big storage `expandedae:exp_crafting_accelerator_{1k,2k,4k,8k,16k,32k,64k,128k,256k,512k,1m}`. Mix freely with AE2 / MEGA CPU parts.
- `expandedae:exp_pattern_provider` (72 patterns, block; facing like ae2:pattern_provider), `expandedae:exp_io_port` (facing, spin, powered like ae2 io port).
- Showcase: a "supercomputer" CPU block of 5x5x5+ with accelerator tiers in visible stripes; exp pattern providers as a wall around assemblers.

### 1.9 MEGA Cells (`megacells`) **[jar: megacells-4.11.0 en_us]**
- CPU parts: `megacells:mega_crafting_unit`, `megacells:mega_crafting_accelerator`, `megacells:mega_crafting_monitor`,
  `megacells:{1m,4m,16m,64m,256m}_crafting_storage`. Same CPU rules as 1.2 (MEGA parts form their own CPU block; keep one CPU one family to be safe **[unverified whether families mix]**).
- `megacells:mega_pattern_provider`, `megacells:mega_interface`, `megacells:mega_energy_cell` (dense energy cell),
  decor blocks `megacells:sky_steel_block`, `megacells:sky_bronze_block`, `megacells:sky_osmium_block` (great dark-metal trim for AE rooms).

### 1.10 Big-base layout (many branches)
A full AE2 base reads best as a **hub and spokes**: a central controller hall (controller multiblock as centrepiece), with corridors
(3-5 wide, 4-5 high, cable trays in the ceiling or floor) branching to wings: storage (drive rows, ExtendedAE ex_drive, cell
workbench), autocrafting (CPU blocks: AE2, ExpandedAE, MEGA; assembler matrix; pattern provider walls), AdvancedAE quantum
computer lab, processing/IO (io ports, interfaces), and a quantum bridge/spatial gate. Each wing is its own ghost id under the area
prefix (`base/hub`, `base/storage`, `base/craft`, ...). Corridors are their own ghosts too. Keep a consistent floor y.

## 2. Room proportions around a 7x7x7 machine (the golden template)

Let M = machine edge (7). Floor layer y=0, interior from y=1.

```
interior footprint : (M + 10) wide x (M + 14) deep  ->  17 x 21        (3-5 blocks free on each side, 9 in front)
dais step 1 (y=1)  : 11 x 11   (machine + 2 ring)       slab or full block, contrasting
dais step 2 (y=2)  :  9 x  9   (machine + 1 ring)
machine            : y=3..9, centred on the dais; x=5..11, z=5..11 in the interior 0..16 x 0..20
ceiling clear      : 14       (machine top 9, + 4 gap, + 1 fascia)   -> ceiling layer y=15
entrance           : centre of the front (south) wall, 5 wide x 5 tall arch, z=20 side
viewing distance   : 9 blocks from the threshold to the machine's front face
side clear         : 5 to each side wall (pillars sit here)
back clear         : 5 behind the machine (feature wall)
```
Why these numbers: >= 3 free blocks each side lets a player walk round it; 1.3x machine height (about 9) lets the whole thing fit in view at a normal FOV; ceiling at machine height +4 gives air above it without becoming a cavern.

**Minimum acceptable**: 15 x 15 x (M+5). Anything tighter hides the machine.

### Framing (all symmetric about the entry axis)
- **Four corner pillars** at (2,2), (14,2), (2,14), (14,14): shafts to y=12, dark capitals, slim, 1 block thick + buttress stubs. They do not block the front view (front pillars are slim).
- **Ring beam** at y=12 connecting them (log/quartz beam), chandelier/light ring hung inside at y=11.
- **Back wall feature**: a tall arched niche 9 wide x 11 tall in the back wall behind the machine, in a contrasting block, lit from the sides (backlight = silhouette).
- **Side galleries**: balcony 3 wide (x=0..2 and x=14..16) at y=7 on both side walls (see rooms.json balcony), rail at y=8; the corner pillars at x=2 / x=14 rise through the gallery as railing posts. The machine's centre line is at y=6, so the gallery looks at its middle.
- **Floor**: concentric inlay centred on the machine: ring 1 = accent, ring 2 = secondary; radial lines to the four doors; 1-block border.
- **Sight lines**: from the door centre, the machine fills the arch; from the galleries, you see the top. Do not put anything in the axis between the door and machine except low floor detail and one low plinth or banner pair at the sides.

### Lighting a showcase
- Key light: 4 hidden up-lights in step 1 (sea_lantern under a slab lip `minecraft:smooth_quartz_slab[type=top]` or under `minecraft:tinted_glass`) so the machine face is washed from below.
- Fill: 2 lanterns/sconces per side wall at y=4.
- Top: oculus/skylight above, `minecraft:end_rod` ring or 4 `minecraft:light[level=12]` hidden on the beam.
- Never place a lamp touching the machine; keep >= 2 block air gap so the textures stay readable.
- Keep the rest of the room 20-30% dimmer than the machine area (use fewer lights on the walls, none at the floor corners).

## 3. Cable and conduit aesthetics

- **One bundle, one route.** Bring cables in from a single side in a floor trench or overhead tray, and fan out only at the machine. Do not wrap the machine in cables.
- **Floor trench**: 1-wide x 1-deep channel with a cover of `minecraft:tinted_glass` or `minecraft:cyan_stained_glass` (shows a glow strip), edges in a trim block; cable stand-in (light-blue glass pane) inside. Hatches every 4 blocks use `minecraft:copper_grate`.
- **Overhead tray**: 1-wide beam 1 below the ceiling in `minecraft:iron_bars` over `minecraft:chain[axis=y]` hangers every 4 blocks; the cable stand-in rides on top. Fully straight runs with 90-degree corners (corner posts in the trim block).
- **Terminations**: each cable ends at a plate: a 1-block frame (trim block) around the port with a lamp above. Never a bare line into a face.
- **Colour code**: one colour per network function (cyan = storage, magenta = crafting, lime = power). Use the same glass colour for the stand-in lines and for 2-3 lamp accents.
- **Create conduit look**: `create:fluid_pipe`, `create:shaft[axis=x]`, `create:brass_bars`, `create:metal_bracket`, 1 block off the wall with a bracket every 3.
- **AE2 look**: real `ae2:quartz_fixture` on ceilings, `ae2:fluix_block` slabs as cable-tray lids; `ae2:quartz_glass` windows.
- Cable length: keep to a run of 2-8 blocks visible; longer runs get a junction block (small 3x3 hub with a lamp).

## 4. Pedestals and plinths

- **Square dais, 2 steps**: stairs on the outer ring `[facing=toward machine,half=bottom]` for the steps, slabs/blocks for the top; border of a contrasting block.
- **Octagon**: for a 9-wide dais cut corners 2x2: bevel with `stairs[shape=outer_*]`. Good for showcase halls.
- **Lowered ring**: sink a 1-deep ring (moat of water or glass-covered light) around the dais; bridges at the 4 approaches.
- **Float**: raise the machine 1-2 blocks over a lit gap (4 corner posts of wall/end_rod). Requires the ghost to keep air under the machine; `minecraft:end_rod` pillars at the 4 corners as supports.
- **Plaque**: a banner pair, sign, lectern, or `supplementaries:pedestal`/`supplementaries:globe`-style prop at the base, centred on the front.
- **Pedestal blocks** per theme: server room `minecraft:polished_deepslate`; quantum lab `minecraft:polished_blackstone` with `advanced_ae:quantum_alloy_block` trim; crafting hall `minecraft:polished_blackstone_bricks` + `ae2:fluix_block` ring; steampunk `create:brass_casing` + dark oak.

## 5. Machine bays, racks and rows (for non-7x7x7 AE2 gear)

- **Bay**: 3 wide x 3 tall x 2 deep alcove, pillar between bays, lintel across, one lamp above. Machine blocks (molecular_assembler, inscriber, charger, interface, pattern_provider) fill the back centre cell; the other cells are decor (hoppers, cauldron, barrels).
- **Drive wall**: 4 wide x 3 high of `ae2:drive[facing=<aisle>,spin=0]`, framed with a 1-block `ae2:quartz_pillar[axis=y]` post at the ends and `minecraft:iron_bars` rails.
- **Pattern provider row**: a long line of `ae2:pattern_provider` along a wall at y=1, with a thin lamp strip above and nothing in front for 2 blocks.
- **Interface cluster**: 2x2 `ae2:interface` blocks with item-frame space above (leave a 1x1 empty wall block) and a lamp row.
- **Energy**: `ae2:energy_cell[fullness=4]` / `ae2:dense_energy_cell[fullness=4]` in a symmetric row of 3 or 5 next to the controller; wiring bridge = a short chain line.
- **Crafting monitors**: put `ae2:crafting_monitor[facing=...]` on the face of a crafting CPU you want visible; centre them on that face.

## 6. Ghost recipe: Assembler Matrix 5x5x5 with a glass face (local coords, x=0..4, y=0..4, z=0..4)

```
palette: F=extendedae:assembler_matrix_frame  W=extendedae:assembler_matrix_wall  G=extendedae:assembler_matrix_glass
         P=extendedae:assembler_matrix_pattern  C=extendedae:assembler_matrix_crafter  S=extendedae:assembler_matrix_speed
interior (x=1..3,y=1..3,z=1..3): 27 blocks, fully filled; >=1 P and >=1 C, at most 5 S (more is wasted), the rest P/C. Example: 9 P, 9 C, 5 S, 4 C.
faces: box(1,1,0 -> 3,3,0, G)  glass on the front face (z=0); the other 5 faces W
edges: 12 frame lines with shape: x-direction edges [shape=column_x], y-direction [shape=column_y], z-direction [shape=column_z], corners [shape=block]
```

## 7. Ghost recipe: Quantum Computer 7x7x7 (outer shell + interior)

```
shell:    all 218 blocks on the outer layer = advanced_ae:quantum_structure
interior: box(1,1,1 -> 5,5,5, advanced_ae:quantum_unit)    fill 125 blocks
          then set(3,3,3, advanced_ae:quantum_core)
          then set(3,2,3, advanced_ae:data_entangler) once, set(3,4,3, advanced_ae:quantum_multi_threader) once
          then 2-8 x advanced_ae:quantum_accelerator and advanced_ae:quantum_storage_256 in place of units
```
(Order matters in the ghost: fill, then overwrite.)

## 8. Ghost recipe: AE2 controller wireframe cube 7x7x7

```
edges only, coordinates 0..6: 12 lines of 7 blocks. Example for the 4 vertical edges:
  box(0,0,0 -> 0,6,0, ae2:controller)  box(6,0,0 -> 6,6,0, ae2:controller)
  box(0,0,6 -> 0,6,6, ae2:controller)  box(6,0,6 -> 6,6,6, ae2:controller)
bottom + top rings: box(0,0,0 -> 6,0,0) box(0,0,6 -> 6,0,6) box(0,0,0 -> 0,0,6) box(6,0,0 -> 6,0,6) and the same at y=6
interior: empty or a floating focal block (glass cage).
```
Total 68 controller blocks, within 7x7x7, every block has both-sided neighbours on at most one axis: valid. Power: an energy cell and a cable must reach one block.
