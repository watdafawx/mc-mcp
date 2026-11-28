# Motif bench (step 4, motif library)

Rendered in the mc-mcp dev client on rig (`runClient -PquickPlay=test`), method copied from `exports/design_bench/NOTES.md`:
pieces at y=120 against the sky, freecam via `ghost_camera`, ghosts solid, HUD off, **xray OFF**, clouds off (`video_set cloudStatus OFF`, not saved).
Sonnet 5.5 designer, default texture pass. Logs: `log_motifs.txt`, `log_factory.txt`, `log_lotus.txt`, `log_station.txt`.
Positions: bench_motifs2 at x=0, factory x=150, lotus x=300, station x=450. Specs: `designs/bench4/*.json`.
Cost: factory $0.0326 + lotus $0.0326 + station $0.0295 = **$0.0947** (motifs spec = $0). Screenshots are 854x480, so
detail is limited; every score below is read from those images.

## A. The 12 motifs (`bench_motifs2.json`; `motifs_iso.png` shows the whole piece)

| motif | score | file |
|---|---|---|
| landing_pad | 8 | motif_landing_pad.png |
| crane | 7 | motif_crane.png |
| pagoda | 7 | motif_pagoda.png |
| water_tank | 7 | motif_water_tank.png |
| porch | 6 | motif_porch.png |
| balcony | 6 | motif_balcony.png |
| timber_frame | 6 | motif_timber_frame.png |
| blade_sign | 5 | motif_blade_sign.png |
| smokestack | 5 | motif_smokestack.png |
| clock | 5 | motif_clock.png, motif_clock_close.png |
| pipe_rack | 4 | motif_pipe_rack.png |
| gear | 3 | motif_gear.png, motif_gear_close.png |

- **landing_pad 8**: round grey pad, white H, orange ring with yellow edge lights; reads instantly as a helipad from above
  (motif_landing_pad). No floating bits. Nit: ring is a ragged octagon.
- **crane 7**: yellow mast, jib with dotted bars, black counterweight, hook line; reads as a tower crane (motif_crane, motifs_iso).
  Wrong: the mast is yellow bands with air between them (chains/bars only), so it looks like floating yellow boxes on a wire;
  the jib is a dotted line of single blocks. Counterweight sits slightly off the mast axis.
- **pagoda 7**: three tiers of deepslate-tile roofs on brick drums, lanterns on the corners, stone finial (motif_pagoda). Reads as
  a pagoda. **Wrong: floating bits.** The upturned copper eave tips at each roof corner are single blocks detached diagonally
  from the roof (clear in motif_pagoda and lotus_top).
- **water_tank 7**: wooden barrel on four legs, iron bands, domed cap, rod; reads as a rooftop water tank (motif_water_tank).
  Small, thin legs; nothing wrong structurally.
- **porch 6**: copper-slab canopy hung on chains over the door, door steps (motif_porch). Reads as an awning, not a porch: no
  posts, canopy is wider than the door and covers the two flanking windows; the door is a 1-wide dark slot.
- **balcony 6**: copper slab with fence railing and lanterns under it, in front of a door (motif_balcony). Reads fine.
  Wrong: 1 block deep, railing thin, one lantern pair.
- **timber_frame 6**: mangrove beams (verticals + one rail) over brick (motif_timber_frame). Reads half-timber. Wrong: beams
  run over window glass so the windows are cut into strips; no diagonal braces, which is what makes timber framing readable.
- **blade_sign 5**: copper frame with a glowing orange blob hung on chains, perpendicular to the wall (motif_blade_sign). Reads
  as a hanging lamp, not a sign: no readable shape, no bracket arm from the wall.
- **smokestack 5**: brick shaft with a two-step taper and flared cap (motif_smokestack). Wrong: only about 8-10 blocks tall, it
  stops near the annex roof and looks like a fat chimney stub; it sits right against the tower wall. In factory_iso_nw the two
  stacks overlap at the base into one blob.
- **clock 5**: round face in white/black checker with black cross hands and an orange centre (motif_clock). Reads like a
  skull/mask more than a clock: no hour marks, hands too thick, face dominates the tower wall. No clipping.
  **The composer skipped it in the factory** ("no blank wall").
- **pipe_rack 4**: copper pipe stubs up the piers with white-cross lamp boxes on top (motif_pipe_rack). Reads as drainpipes and
  lamps, not a rack: no horizontal run, no brackets, nothing connects the verticals.
- **gear 3**: a ragged copper outline around a 5x5 diamond of barrels, fused with the cornice and floor band above the windows
  (motif_gear, motif_gear_close; also factory_street, lotus_street). Not recognisable as a gear: no teeth ring, no circle.
  Clips over window sills and pier tops.
- No purple or missing textures in the 12 pieces. Glass renders noisy (renderer artefact, not design).

## B. Designed builds vs the previous bench (design_bench: factory 5, lotus 4, station 4)

### factory: "red-brick Victorian factory complex, clock tower, smoke stacks": **6/10** (was 5)
Octagon tower 9x9 h24 with spire, sawtooth machine hall 25x17, workshop 19x13, boiler 15x15; wall2 + pillar both bricks.
8667 blocks, 2 doorways. Shots: factory_iso_se, factory_iso_nw, factory_street, factory_top.
Better: it is finally **red-brick** (brick on pier and infill, factory_street, iso_se); sawtooth hall with glass strips reads as
a north-light factory (factory_top, iso_nw); tower with green spire is a landmark; two stacks present; no oversized platform.
Still wrong:
- **No clock**: composer skipped it ("no blank wall", log_factory). The brief's clock tower has no clock (factory_iso_se).
- **Gear is a copper splat** across the workshop's south facade over windows (factory_street).
- **Door/porch missing**: porch skipped ("something else is in front of that doorway"); the entrance is a tiny dark slit under
  the gear (factory_street).
- **Twin stacks fuse at the base** into one fat brick blob beside the tower (factory_iso_nw).
- Dark deepslate roof and base still read blackish.
vs "classic brick factory": silhouette and roof right; missing arched windows and a clock.

### lotus: "tall red timber refinery tower, stacked pagoda roofs, side workshops, crane, steampunk": **6/10** (was 4)
Octagon tower 15x15 h36, hall, lab, forge; 10809 blocks, 3 doorways. Shots: lotus_iso_se, lotus_iso_nw, lotus_street, lotus_top.
Better: **a real 3-tier pagoda** crowns the tower (lotus_iso_se, iso_nw); the crane has mast, jib, counterweight and hook
(lotus_iso_nw, lotus_street); porch canopy + railing at the tower door (lotus_street). Still wrong:
- **Colour is still magenta/maroon**, not red timber (all four shots). Crimson planks read violet.
- **Floating eave tips** hover around the pagoda corners (lotus_top: single orange squares in the air).
- **Gear splat** on the lab facade (lotus_street, right).
- Lower workshops are flat boxes with no tiered eaves, so "stacked pagoda roofs" is only the tower crown.
- Tower shaft is a plain tall crimson drum, no tiers or balconies between floors; reads like a lighthouse (lotus_iso_nw).
vs Red Lotus refinery: tiers and crane now there; colour and facade richness missing.

### station: "white research station, orange stripe, ring lab around core tower, glass labs, landing pad": **5/10** (was 4)
Octagon core h32, L-shaped ring 34x30, glasslab, hall, platform; 21870 blocks, 2 doorways.
Shots: station_iso_se, station_iso_nw, station_street, station_top.
Better: **landing pad exists** (H + orange ring on the west hall; station_top, station_iso_nw); the orange stripe is now a
continuous band under every cornice (station_street, station_iso_nw) instead of spots; platform smaller; white palette clean.
Still wrong:
- **Still a neoclassical government building**: piers, capitals, cornices everywhere, plus a clock on the core's south face
  (a clock on a space station, station_iso_se). No pods, struts or curved glass.
- **No ring around a core**: the ring is an L block south of the core and the core is a separate octagon at the north end
  (station_top). The brief's central idea is still missing.
- **Glass labs are ordinary pier + window boxes** (station_street right).
- **Floating red tips**: 2-3 single red blocks hover above the spire and tower roof (station_iso_se, station_iso_nw).
- Tan plank-looking roof equipment strips on every flat roof (station_top, station_iso_se).
vs Sausbuilds white station: palette and stripe on the way; form is not.

## C. Top 5 fixes, ranked (each tied to a shot)
1. **Rewrite `gear`**: draw a real cog (ring of teeth on a circle, hub, 7-11 blocks) on a blank bay only, never over windows or
   the floor band; if there is no blank bay, skip like clock does. (motif_gear, factory_street, lotus_street: the splat hits all
   three builds.)
2. **Fix the red/timber palette**: crimson planks render magenta. Use red_nether_bricks / spruce + dark_oak red mix or
   terracotta for "red timber", and tag the brief's colour role so it dominates. (lotus_iso_se, lotus_street)
3. **Remove floating bits**: pagoda eave tips and spire/antenna tip blocks must touch the roof. Snap each tip to the roof corner
   (diagonal stair/slab) and drop the isolated red tip on spires. (motif_pagoda, lotus_top, station_iso_se)
4. **Stop the composer skipping landmark features**: factory had no clock and no porch because "no blank wall". Reserve a wall
   panel for clock/porch before placing windows, or widen the tower, and keep clocks off sci-fi kits.
   (factory_iso_se, factory_street, station_iso_se)
5. **Station form: real ring around a core, glass labs, no pilasters**: add a `ring` shape with an open court and put the core
   in it; the sci-fi kit gets strut/fin trim and curtain-wall glass instead of piers. (station_top, station_street)

Runners-up: smokestack taller and spaced apart (motif_smokestack, factory_iso_nw); clock face with hour ticks and thin hands
(motif_clock); pipe_rack as a horizontal run with brackets (motif_pipe_rack); blade_sign with a bracket arm and flat plate
(motif_blade_sign); timber_frame with diagonal braces that avoid glass (motif_timber_frame).
