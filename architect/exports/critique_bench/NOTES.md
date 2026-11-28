# Critique bench (step 5 + ring)

Live on rig (client `runClient`, mc-mcp tunnel), builds at y=120, `--freecam`, xray off, solid, noon/clear. Each run:
`architect.py --design --critique 1 --freecam --save-shots exports/critique_bench`. Shots: `<run>_r0_*` = the build
before the critic, `<run>_r1_*` = after the critic's corrected spec was recomposed. Logs in `logs/`.
Specs: `designs/cb_*-<ts>.json` (design) and `-r1.json` (critic).

| run | designer | design $ | critic $ | total $ | flaws r1 | ring? |
|---|---|---|---|---|---|---|
| station | Sonnet 5.5 | 0.0305 | 0.0426 | 0.0732 | 5 | yes: ring `labs` (band 11, gap 0) around round core r8, 4 doorways |
| factory | Sonnet 5.5 | 0.0373 | 0.0482 | 0.0855 | 4 | n/a |
| station_haiku | Haiku 5.5 | 0.0031 | 0.0432 | 0.0463 | 5 | yes: ring `labs` (band 10, gap 0) |

Bench total: $0.205 (budget 0.60). Critic ~15 s per round, ~$0.043-0.048 (3 screenshots in).

## Flaws the critic found (round 1)

**station (Sonnet)**
1. Core balcony skipped, "no spot" (wall hidden by the ring) -> moved to level 4, side s. Still skipped after (no spot): not fixed.
2. Core dome solid orange (orange trim role) -> removed the override. FIXED: dome now grey/blue, orange only as stripe.
3. Landing pad on hangar small -> hangar 21 -> 23 wide (only enlarged). Pad still there.
4. Platform feature put on the core -> moved to the ring. (Platform shrank 8322 -> 4032 blocks.)
5. Glass labs plain -> blade_sign on east side. Skipped by the composer (no spot): not fixed.

**factory (Sonnet)**
1. Spire floating above the clock tower -> tower roof hip_steep -> spire. Spire tip still floats in r1 (known open item).
2. Hall porch skipped (tower in front) -> moved to workshop s. Skipped again ("something else in front").
3. Pipe rack moved to furnace east wall. Placed.
4. Tower not dominant enough -> sixth floor, 34 -> 40 high. FIXED: clearer landmark.

**station_haiku**
1. Core porch skipped -> porch on ring s. Skipped again (something in front of the doorway).
2. Bridge onto ring unsupported -> glass_labs gap 3 -> 0, bridge removed. FIXED: wing now hugs the ring.
3. Pad hall roof too small -> widened 16 -> 18. Pad still skipped (roof deck too small).
4. Orange stripe barely visible -> accent_floor 0 on ring and glass_labs. Orange now shows on the ring.
5. Dark deepslate-looking dome clashes with white -> white concrete roof role. Dome still grey in r1 (not fixed).

## Did the station use a ring?

Yes, both Sonnet and Haiku: a real ring of labs (2 floors, 14-15 high, 4 doorways into the core) around a round core
tower (29-34 high, dome + spire). This is the shape the composer could not make before. Shots `station_r0_se.png`,
`station_haiku_r0_se.png`.

## What did not work / open

- Critic fixes land about half the time. It reasons from the report's skip notes but cannot see the composer's
  geometry rules: the same features (balcony, porch, blade_sign, landing_pad) are skipped again after a move.
  A "retry skipped features" pass inside the composer (try other sides / volumes) would help more than another model round.
- Critic text sometimes contradicts the spec (e.g. "tower 6 floors" claims, a flaw about a platform on the core).
- Spire on a tall hip/spire roof still floats (composer bug, not a critique matter).
- Landing pad on a ring band needs band >= ~13: with band 10-11 it never fits; the pad should go on a flat-roofed volume.
- One round per run only (as asked); a second round was not tried.
