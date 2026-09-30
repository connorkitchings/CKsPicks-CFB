# V5 intended-update Preview rehearsal — 2026-09-29

**Status:** Preview rehearsal passed with refreshed Week 5 `p2`; production release packet remains open. This is evidence for Task 6 of [the approved contract](v5-intended-update-2026-production-repair.md), not a production authorization.

## Initial p1 Preview set (superseded for Week 5 by p2 below)

| Week | Original Preview run | Replacement run | Games | Replacement state |
| --- | --- | --- | ---: | --- |
| 0 | `2026w0-cb2252a0w0v5` | `2026w0-v5repair-20260929-p1` | 8 | scored replay |
| 1 | `2026w1-v5replay-w0w3` | `2026w1-v5repair-20260929-p1` | 43 | scored replay |
| 2 | `2026w2-v5replay-w0w3` | `2026w2-v5repair-20260929-p1` | 49 | scored replay |
| 3 | `2026w3-v5replay-w0w3` | `2026w3-v5repair-20260929-p1` | 57 | scored replay |
| 4 | `2026w4-v5replay-w4` | `2026w4-v5repair-20260929-p1` | 58 | scored replay |
| 5 | `2026w5-5d436e58c072` | `2026w5-v5repair-20260929-p1` | 56 | frozen live, no grades |

All six replacement runs use model `v5-intended-update-2026-v1`, approved bundle SHA `30c4f1eb0ef5b3c1e30b2a877b4553923c3b5ff68832eea0282e37e625b13531`, and rating manifest SHA `e80ae3473d88d0c458325c19343e7dae6447924d9abad29b15089bc19cacd26b`. Preview holds 680 replacement pregame and 690 current snapshots. The initial p1 Week 5 run has 56 predictions and 56 spread/total quotes. Its serving, independent verifier, and standard run packet SHA-256 values are respectively `104729ac352e5dc5735efdba519b890e34cdabcd344b8b425e5f6a5016adad86`, `4edd933b5cf32c2eb1d794a5c7853d609800d7c8cc7af71a0b1ded38d0ae058b`, and `32918f91c84a5cb63e291f704bec6fb970c25fd90a285e9d5d0ea7d252181a11`. Its Preview freeze was recorded at `2026-09-29T20:17:45.049581Z`, before first kickoff `2026-10-02T00:00:00Z`.

The batch selector switched Weeks 0–5 in one transaction, recomputed `system_stats`, rolled all six back in one transaction, and reactivated all six in one transaction. Readback after reactivation matched every replacement run ID and the Week 5 `current_week.active_run_id`. Selected Weeks 0–4 contain 215 predictions, 199 spread and 159 total grades, all grade quote links present. Season statistics are spread **93–103–3** and total **82–77–0**, with profit units **−18.4537** and **−2.4538**. Week 5 has zero grades.

A read-only production comparison paired all 215 completed game keys. The original production selections show spread **94–105–3** and total **87–78–0**. The repaired run changes all 215 spread and total forecasts; mean absolute forecast shifts are 4.823 margin points and 0.850 total points. Those scores are retrospective and do not establish prospective performance. The Preview original runs have no `prediction_grades`, so rollback there correctly restores its old zero-stat fixture; production's nonzero old baseline is the relevant comparison.

Local web readback against Preview showed the selected Week 5 successor on the predictions page, Post-Week 4 replacement ratings, and the replacement 215-game record on the performance page. The performance page initially served a build-time original record; it was changed to dynamic rendering and to exclude unfinished Week 5 from its completed-game count. The rebuilt page read back **215 selected games**, spread **93–103–3**, total **82–77–0**.

## Release gates still open

- The selected Preview Week 5 `p1` candidate uses a September 27 market capture. A fresh read-only CFBD check at `2026-09-29T20:27:09Z` found 56/56 scheduled games with both targets, but 50/56 matching DraftKings game quotes differed from that old capture. `p1` is therefore **ineligible as the final production Week 5 packet**.
- New Preview source capture `74ba9bc899f845d290f8cf6ec3824e3f` was recorded at `2026-09-29T20:28:55Z` under pipeline `v5repair-w5-market-20260929-p2`. Its Silver refs are `market_quotes` version `2608fc49f03dc6e46a5b4a87` (112 quotes, 56 games; content SHA `bd028650598ff08664f0d3e66216cc0666e8f5f137facc36d3c4a8636139e939`) and `market_snapshots` version `22c97e0aae0debc2904278c3` (56 games; content SHA `a8f16a87a811a6017bd004ebf66ce6af0c07d161dd4eeefad75ff9954fa38eec`). Committed code `446c8805dc474b0628c667549142be04c1fb6b87` published the `p2` forecast, serving SHA `719bb93e75e088a47262f39742769da10231b7b689d1d1a1a2d4c100990ab251`, independent verifier SHA `63e491135aeda6915bf985c3e88f172d077dd913612051c538d5ea9845894303`, and standard run packet SHA `d74262fe5a51d7510bcce80ab82f7f116730ac00d3765242c005d56aaf551c0f` to Preview R2.
- Preview authorized and published `2026w5-v5repair-20260929-p2` with 56 predictions, 56 spread and 56 total quote selections, and zero grades. The exact six-week batch (Weeks 0–4 `p1`, Week 5 `p2`) selected atomically, rolled back to all original Preview runs, and reactivated atomically. Week 5 froze in Preview at `2026-09-29T20:43:53.376950Z`, before first kickoff. Revalidated selected run IDs, rating SHA, completed-week grade counts, season statistics, current-week pointer, and local Preview-backed ratings/predictions/performance pages. Scores remained 93–103–3 spread and 82–77–0 total; Week 5 remained ungraded.
- Refresh/recheck markets again immediately before a production release and final freeze. If the freeze boundary is missed, move the live release to the next unstarted slate.
- Re-read production selections, finals, schedule, and first kickoff. Preview's original run IDs differ from the production rollback IDs; construct the production packet from fresh production readback.
- Prepare the production R2 artifact graph and the exact production authorization and batch selection packets with refreshed artifact hashes and an immediate rollback packet. Present those packets for the contract's separate release decision. Production migration 0018 is present, but a read-only check found zero successor production authorizations and all six original runs still selected; no successor production publication or selection has been applied.

## Validation

- 75 focused Python tests, 38 web publication tests, TypeScript typecheck, contracts validation, Ruff format/lint, and Next.js production build passed.
- Documentation build passed with existing cross-directory link warnings; strict mode remains red on 10 such warnings.
- Preview batch select, rollback, and reactivation readbacks passed. `git diff --check` passed.
