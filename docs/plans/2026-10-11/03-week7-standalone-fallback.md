# Week 7 standalone fallback (frozen Week 7 on corrected ratings through Week 6)

- **Status:** Draft, awaiting owner approval. It adds no authority of its own; it releases nothing until the owner gives it an exact release decision.
- **Created:** 2026-10-12
- **Governed by:** the [Week 7 cutover run sheet](../2026-10-10/01-week7-cutover-run-sheet.md), the [gate waiver contract](02-week7-cutover-gate-waiver-and-readiness.md) and repair Amendment 14.

## When this applies

The run sheet's pivot gate is Tuesday 2026-10-13 14:00Z. If the Preview rehearsal, including the owner-login rollback proof and readback, is not fully verified by then, the Week 0–6 corrected-replay cutover is barred. Week 7 is then served on its own: a frozen Week 7 run whose ratings come from the corrected chain through Week 6, with Weeks 0–6 left as currently selected.

If the Weeks 0–6 corrected replay set or its audit receipt is the part that failed, the fallback must not claim the corrected record. The Week 7 run is then labelled by what it actually rests on (see "Ratings input" below).

## Why Week 7 cannot be skipped

The Week 8 Advance-Mode selection requires Week 7 to be selected with a freeze receipt, so a Week 7 run must exist and be selected even in the fallback. Freezing Week 7 before its 23:00Z first kickoff (deadline 22:00Z) is the same requirement as in the main path. Week 6 is never frozen.

## Ratings input

Choose exactly one, decided before building and recorded:

1. **Corrected ratings through Week 6, published.** Requires the successor lock, intended-update build, verification and `publish_v5_intended_update_ratings.py` to have completed and verified. Week 7 forecasts then use those ratings.
2. **Currently selected post-Week-5 corrected manifest (`c83b1423…`) plus the Week 6 display run's evidence.** Used only if option 1 did not complete; the Week 7 run must state that Week 6 results are not in its ratings, and the pivot is then a larger quality compromise that needs its own explicit owner decision.

## Sequence (all Preview first; every Preview write and every Production write is its own go-ahead)

1. Team stats as-of 7: `publish_team_stats.py --as-of-week 7` (dry run, then apply), `verify_team_stats.py`.
2. Fresh Week 7 market capture, reconciled against all 59 FBS games separately for spread and total. Record the capture time, missing game IDs and next refresh time (`AGENTS.md` rule 6).
3. Pending run: `build_corrected_live_lock.py --week 7`, `build_v5_intended_update_forecasts.py`, `build_v5_corrected_live_serving.py` (no `--display-only`), `verify_v5_corrected_live_serving.py`, `package_v5_corrected_live_run.py`.
4. Selection: the Advance-Mode v2 packet cannot keep Weeks 0–6 "protected and unchanged" (the protected map may not overlap the slate and runs cannot be reused), so the fallback uses the older single-week route: `publish_to_db` then `select_public_run` for the Week 7 run, leaving Weeks 0–6 selections as they are (`current_week` 6→7). The exact commands and guards must be confirmed against the code before this step is approved.
5. `freeze_week.py --year 2026 --week 7` with the exact decision reference, before 22:00Z.
6. Matchup publish and verify for the selected state; `current_week` 6→7 readback.
7. Rollback proof under the owner login in Preview before any Production apply, as in the main path.
8. Update `docs/status.md` from actual results.

## What the fallback does not do

- It does not replace Weeks 0–6 with corrected replays, so the Performance record stays on the currently selected runs and Week 6's record stays the display-run grades (spread 35-19-1, total 23-32-0 on 55 games).
- It does not clear the waived integrity items (EPA replacement, quality follow-ups, scoring and descendant recertification, the 2025 matchup candidate).
- The cross-lineage banner on Weeks 0–5 matchup pages persists until a later corrected-replay cutover.

## Release decision

If the pivot gate trips, the owner issues a separate exact release decision naming: the ratings input option, the Week 7 run ID, the packet hashes and the freeze decision reference. Nothing here is pre-authorized.

## Follow-up after the fallback

The corrected Weeks 0–6 replay cutover remains an open obligation. It must run as an Advance-Mode selection from the post-fallback state, which changes the before-state in the packet design.
