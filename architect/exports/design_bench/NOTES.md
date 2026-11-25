# Design bench (step 3, build-as-program)

Rendered in the mc-mcp dev client on rig (`runClient -PquickPlay=test`), pieces at y=120 against the sky, freecam via
`ghost_camera`, ghosts solid + **xray off** (see issue 1), HUD off, clouds off for the top shots (`video_set cloudStatus OFF`,
not saved). Sonnet 5.5 designer, `ARCHITECT_TEXTURE` default. Per build: `<b>_iso_se.png`, `<b>_iso_nw.png`, `<b>_street.png`
(low, main entrance), `<b>_top.png`. Printed logs: `log_<b>.txt`. Specs: `architect/designs/bench3/*.json`.
Builds sit at x=0 (factory), 150 (lotus), 300 (station), 450 (handspec, `designs/bench_factory.json`, no API call).
Cost: factory $0.0323, lotus $0.0337, station $0.0284, handspec $0 = **$0.0944**. ~12 s per design.

## Harness finding (not a design bug, but it breaks the standard view)
`factory_iso_se_xray.png`, `factory_top_xray.png`: with `ghost_show xray=true` (what `view()` in architect.py sets) the
**platform ghost draws over the buildings** from any angle above the platform (platform = last ghost id, drawn without depth test).
The buildings vanish under a blackstone/copper grid. Only the street-level shot survives. With xray off the depth order is right.
Also: the freecam top shot needs the camera within ~0.55x footprint above the roof; higher and sections stop drawing
(station_top showed only the core). Clouds (y~192) block top shots above tall builds.

## 1. factory — "red-brick Victorian factory complex, clock tower, smoke stacks" — **5/10**
Concept line: red-brick Victorian factory in the steampunk kit; octagon clock tower w/ spire roof as landmark, flanked by a
sawtooth machine hall and a lower boiler house with twin stacks, office + workshop. Wall2 bricks, pillar stone_bricks, base
polished_blackstone_bricks, trim cut_copper, roof deepslate_tiles. Hall 27x21, boiler 17x15, tower octagon 11 (h32), office, workshop;
16664 blocks, 3 doorways, no fixes needed. $0.0323.
Reads well:
- Tower is a real landmark (45 tall vs 16 hall), copper bands, tall slit windows, stepped green spire cap (factory_iso_se, _iso_nw).
- Sawtooth hall roof with glass strips reads as a north-light factory; twin stacks with banding on the boiler (factory_iso_nw).
- Silhouette stepping tower > hall > boiler > office is good.
Wrong:
- **Not red.** Stone-brick/blackstone piers + dark deepslate-tile roof + blackstone platform dominate; brick only fills the
  infill. Overall colour is grey-black with orange trim, not red brick (factory_street). Reference is brick-red masses.
- **Tower attached on the hall's south side covers the hall's south entrance** (`hall` entrances s,w; tower sits on that wall).
  The real hall door is hidden; the street shot's door is the tower's (factory_street).
- **Green "scribble" pipes on the hall north wall** (oxidised copper strips) read as graffiti, not pipework (factory_iso_nw, _xray).
  Copper gear on the tower south face is a small orange box at the foot, not a clock (factory_street). **No clock face exists.**
- **Platform is a 72x41 black/copper checker slab** twice the building footprint; most of the image is empty grid
  (factory_iso_se). Looks like a game board, not a yard. A stray beam pair pokes out past the platform's SE edge (factory_top).
- Hall, boiler and office share one window/pier system, so 4 of 5 volumes look like the same box (factory_iso_se).
- Spire roof of tower: green steps + thin rod, no clock/flag; rod looks like floating antenna.

## 2. lotus — "tall red timber refinery tower, stacked pagoda roofs, side workshops, crane, steampunk" — **4/10**
Concept line: one tall red-timber tower stacked on a wide hall, steep hip roof + spire, furnace (sawtooth + chimneys), lab wing,
crane block. crimson_planks wall2, stripped_crimson_stem pillar, dark_oak wall, copper trim. Hall 25x19 (flat), tower 15x15
h34 (hip_steep, 5 floors), furnace 19x15, lab 15x13, crane 9x9. 16330 blocks, 2 doorways, 3 fixes (tower d 13->15, lab/crane floor h). $0.0337.
Reads well:
- Strong vertical landmark; stacked on the hall it looks like a tower rising from a podium (lotus_iso_nw). Slim piers + sill bands
  give it a nice rhythm.
- Copper hip roof reads, hall/furnace flat/sawtooth difference is clear.
Wrong:
- **No pagoda.** One hip_steep roof on the tower; "stacked pagoda roofs" is a single pyramid. No eave overhang, no tiered
  roofs on the volumes below. Biggest miss vs a Red Lotus reference (lotus_iso_se).
- **Colour is magenta/purple**, not red timber (crimson stem + planks render deep pink-violet). Platform too (lotus_iso_se, _top).
- **"Crane" is a 9x9 storage box with a gable roof** at the far east end; no jib/hook. Weak, and barely visible in any shot.
- **Spire head floats**: chunky copper/black cylinder ~8 blocks above the roof on a 1-px rod (lotus_iso_se, _iso_nw). Reads as
  detached. (Blocks are contiguous in the data; the rod is iron-bars-thin so it looks cut.)
- **Giant copper gears clip over windows and pilasters** on hall s and lab s: a 15-block orange lattice pasted on the facade
  covers glass and breaks the pier rhythm (lotus_street). Green pipe bundle on the furnace is the same blob look.
- Door: hall s entrance shows no clear door; porch/steps absent (lotus_street).
- Top view is a stack of orange squares; the stacked tower on the hall leaves little hall roof visible (lotus_top).

## 3. station — "white research station, orange stripe, ring lab around core tower, glass labs, landing pad" — **4/10**
Concept line: white station on a stepped platform; octagon core tower with crown roof + antenna, wrapped by a round ring lab,
glass lab west, machine hall + annex east. kit station_white, accent orange_concrete, glow sea_lantern, pillar quartz_pillar.
Ring r=16 (33x33, h16), core 13x13 h36 (6 floors), glass_lab 19x15, machine 23x17, annex 15x11. 21581 blocks, 2 doorways, 3 fixes. $0.0284.
Reads well:
- Clean white palette, cylinder ring with colonnade piers has a calm, grand look (station_iso_se, station_street).
- Tower landmark is clear; entrance gets a full-height door bay (station_street).
- Stepped white platform plinth looks tidy.
Wrong:
- **It looks like a neoclassical courthouse, not a space station.** Piers/capitals/cornices everywhere (depth pass tuned for
  gothic); no pods, no struts, no curved glass, nothing sci-fi (station_street).
- **Ring is a solid drum with the core stacked on it, not a ring around a core.** No courtyard, no open centre (station_top shows
  concentric rings = roof steps only). The brief's central idea is missing.
- **Orange stripe is 3 small bands** on window sills, not a continuous belt; reads as spots (station_iso_se). Reference stripe
  is a long continuous band.
- **No landing pad**: "platform" feature = the base slab; no marked pad, no H, no lights.
- **Glass labs are not glass**: normal pier+window facade, same as the rest (station_iso_nw).
- Spire head floats ~8 blocks above the crown on a thin rod, plus a red tip (station_iso_se, _nw).
- Odd tan strips on every flat roof (roof equipment rows) look like planks, repeated on all 3 roofs (station_iso_nw).
- Orange/green chimney on the machine block is off-theme (station_iso_se).

## 4. handspec (saved `bench_factory.json`, no API) — **5/10**
Long 41x21 sawtooth hall, boiler gable with twin stacks, rect tower 11x11 h26 with mansard + spire feature, office hip. 11513 blocks.
Compared with the Sonnet factory: simpler, more readable brick facade (infill brick + stone-brick piers look right in
handspec_street), clear sawtooth roof from above (handspec_top), stacks tall. But the tower is plain, spire head floats the
same way (handspec_iso_se), gear again a messy lattice on the hall (handspec_street), tower attached on the hall south side
blocks nothing here (hall door sits east of the tower). So Sonnet's version (clock-tower octagon, better stepping, stronger
landmark) wins on silhouette, loses on colour (grey vs red).

## Top 5 composer / prompt fixes (ranked)
1. **Colour fidelity: wall mass must carry the theme colour.** Today `wall2` only fills infill between piers; piers (stone_bricks)
   and base/roof (blackstone, deepslate tiles) dominate, so "red brick" and "red timber" come out grey-black / magenta
   (factory_street, lotus_street, lotus_iso_se). Make the composer enforce ≥55% of visible facade = the brief's colour role, add a
   brick-red / timber-red palette (red_nether_bricks / spruce+crimson mix, not crimson stem), and let the prompt say which role
   is the dominant colour so the model can pick pier = brick too.
2. **Decor goes on free wall panels only, never over windows/piers.** Gear and pipe features clip over windows and wreck rhythm
   (lotus_street, handspec_street, factory_iso_nw green scribble). Snap gears to blank wall bays, cap radius to the bay, size
   ≤ 4; render pipes as a thin run along a floor line, not a 5x8 blob; give the tower a real clock face (3x3 + hands) when the
   brief says clock.
3. **Spire / crane must be a connected, proportioned part.** Spire head floats on a 1-px rod (lotus_iso_se, station_iso_se,
   handspec_iso_se). Make the shaft ≥3 wide or a stepped taper from the roof, and build a real crane (mast + jib + hook), not a
   box with a gable. Add a `pagoda` stack (tiered eave roofs) so "stacked pagoda roofs" gets 3-4 overhanging tiers (lotus_iso_nw).
4. **Platform / base slab: shrink and make it a yard.** 72x41 black/copper grid under a 40x30 build wastes the shot and, worse,
   hides all buildings under xray (factory_iso_se_xray). Footprint + 3-5 blocks, one material, plus path stones to doors; and
   fix the harness draw order (platform id first, or exclude it from xray) so `view()` stops covering buildings.
5. **Per-volume identity and a theme-specific wrapper.** Hall/boiler/office share one pier+window system (factory_iso_se); the
   station gets neoclassical piers for a space theme (station_street) and the ring is a drum with the core on top, not a ring
   around a core (station_top). Add per-volume window systems (arched, circular, glass curtain), a `ring` shape (outer r, inner r,
   open court), and for sci-fi themes switch the depth pass to strut/fin trim instead of pilasters; make the orange stripe a
   continuous band on `accent_floor`. Also place attached volumes so they never cover another volume's entrance (factory tower on
   hall south).
