# A/B costs (arms named here only; not on the sheets)

| brief | arm | API cost | model time | wall time | ghost blocks | errors |
|---|---|---|---|---|---|---|
| factory | old-haiku | $0.0104 | 57s (14 in/10976 out tok) | 65s | 4236 | none |
| factory | old-sonnet | $0.0759 | 17s (10 in/1974 out tok) | 21s | 5227 | none |
| factory | new-sonnet | $0.0339 | 12s spec call | 16s | 11088 | none |
| factory | new-haiku | $0.0038 | 27s spec call | 30s | 7260 | none |
| lotus | old-haiku | $0.0142 | 96s (16 in/17404 out tok) | 102s | 2402 | none |
| lotus | old-sonnet | $0.0352 | 16s (8 in/1700 out tok) | 19s | 4026 | none |
| lotus | new-sonnet | $0.0360 | 15s spec call | 18s | 12077 | none |
| lotus | new-haiku | $0.0033 | 21s spec call | 24s | 8692 | none |
| station | old-haiku | $0.0097 | 64s (16 in/12028 out tok) | 69s | 6300 | none |
| station | old-sonnet | $0.0566 | 26s (12 in/2845 out tok) | 30s | 14934 | none |
| station | new-sonnet | $0.0336 | 15s spec call | 19s | 22796 | none |
| station | new-haiku | $0.0032 | 23s spec call | 25s | 14466 | none |

Totals: old-haiku $0.0343, old-sonnet $0.1677, new-sonnet $0.1035, new-haiku $0.0103; all $0.3158.

Notes:
- old-sonnet cost is the printed Sonnet-priced figure. `--max-cost` 0.5 (old-haiku), 1.0 (old-sonnet): never reached.
- Old arms run with `--freecam` (client-side camera, no spectator/tp). New arms (`--design`) have no view loop.
- Block count = sum of the build's ghost blocks as listed by `ghost_list` (after texture pass).
- Positions: arm columns at x = 0 (old-haiku), 200 (old-sonnet), 400 (new-sonnet), 600 (new-haiku); briefs at z = 0 / 250 / 500.
- Shots: iso SE/NW + street (south face), camera distance from bounding-sphere fit, same rule for every arm; time frozen at noon, weather clear, clouds off, xray off, solid ghosts, HUD off. Game's pause-on-lost-focus was disabled mid-run (one pause menu had covered some earlier shots); all shots were retaken after that and after freezing the day cycle.
