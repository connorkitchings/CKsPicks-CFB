# Monday kickoff-time refresh

- **Status:** In Progress
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Owner decisions 2026-11-12 (target Monday 2026-11-16 gated on a passing Preview rehearsal, otherwise Monday 2026-11-23; stop and alert if the refreshed schedule adds, cancels or moves a game); exact-path authorization for implementation is the next gate
- **Implementation log:** Pending
- **Commit policy:** Commit with implementation

## Goal and acceptance

The site shows "Time TBD" for 14 of 67 Week 11 games because Sunday's close captured the schedule before kickoff times were announced, and nothing re-fetches the schedule afterward. The database holds `start_date` at midnight Eastern (for example `2026-11-14T05:00:00Z`) for those games, which is the College Football Data (CFBD) placeholder for "time not announced"; CFBD also sends `start_time_tbd`, which Bronze stores.

Outcome: the Monday `market-refresh` run refreshes the schedule, so placeholder games receive real kickoff times in a new release, with predictions, ratings, grades and completed weeks unchanged.

Acceptance:

- The Monday refresh runs when the active release has placeholder games and fresh CFBD data shows real times for at least some of them, even if the week is fully lined; it still skips when the first kickoff has passed or nothing improved.
- A refresh that adds, cancels or moves a game (different game IDs, week or teams) stops the run with the game list.
- Only `start_date` may differ between the old and new schedule; the new release passes parity and `season_verification_v2`.
- A Preview rehearsal against the current Week 11 release gives the 14 placeholder games real times using one CFBD request, with the Odds quotes matching those games.

## Baseline and constraints

- `decide_market_refresh` (about line 177) and `market_refresh` (about line 789) in `scripts/ops/weekly_automation.py` re-capture betting lines only; `derive_manifest` (`scripts/pipeline/build_market_revision.py:63-109`) copies the `schedule` and `venue_games` pins unchanged. The run skips when the week is fully lined (67/67).
- Odds API matching requires the stored kickoff within 5 minutes (`src/cks_picks_cfb/data/the_odds_api.py:121,133`), so placeholder games likely get no quotes; the near-kickoff capture (`scripts/ops/near_kickoff_slot.py:111`) would skip them too.
- V5 does not use kickoff time as a feature, only for cutoff ordering and eligibility (`forecast/live.py:94,133,143`, `season/prepare.py:58,63,115`). A later real time changes no prediction; a game moving earlier fails closed on the existing cutoff check. Release rows are insert-only, so a new release with new `start_date` values is allowed.
- The web `isTimeTbd` (`web/src/lib/time-et.ts:82`) is the reference rule; no Python helper exists yet.
- Out of scope: V5 or any model input, the Sunday close path, the near-kickoff capture design, the site "Time TBD" display, absorbing added or cancelled games.
- Timing: build and rehearse on Preview. Push to `origin/dev` on Saturday 2026-11-14, outside the Sunday 17:00 to 19:30 UTC and Monday windows, only if tests and the Preview rehearsal pass. Otherwise land after the release and enable for 2026-11-23. A `weekly_automation.py` change applies from `dev` immediately; a workflow or cron edit needs the `dev` to `main` release.
- Do not touch Production before the Preview rehearsal passes.

## Ordered changes

1. **Placeholder detection.** Add `time_tbd` to the `Game` dataclass (`weekly_automation.py:101-105`), filled in `default_deps().games` (lines 320-342) from `start_time_tbd`, falling back to a zone-aware midnight-Eastern rule (daylight and standard time). Test: detector across both offsets; the flag overrides.
2. **Decision.** Extend `decide_market_refresh` per the acceptance rules; the reason names the counts. Test: decision table (placeholders and improved times run; none skip; first kickoff passed skip; placeholders all still TBD at provider skip).
3. **Schedule-refresh command.** Compose the existing steps (`_fetch_source_step` line 80 with `ingest_season.py --entities games`, `_week_policy_from_ingestion_step` line 891, `_silver_from_ingestion_step` line 791, `verify_completed_week_stability` lines 1854-1871) into one controller command in `src/cks_picks_cfb/ops/__main__.py`, called from `market_refresh` before line capture.
4. **Changed-game check.** Compare old and new schedule: same game IDs, weeks and teams, only `start_date` differs; otherwise fail closed with the game list.
5. **Manifest.** `derive_manifest` takes an optional scoped replacement of `schedule` and `venue_games` together (same Silver `games` version); every other pin stays forbidden to change. Test: any other change is rejected.
6. **Parity.** In market-refresh mode (`check_release_parity.py:561-606`) allow `start_date` to differ on upcoming and later-week `games` rows only when the manifest's schedule pin changed. Predictions, ratings, grades and completed weeks stay strict. Test: accepted with a changed pin; rejected without; prediction or grade differences rejected.
7. **History gate.** `verify_completed_week_stability.py:60-69` compares weeks up to N-2 against the previous manifest, and Silver columns such as `attendance` or `excitement_index` may fill in between Sunday and Monday. Narrow the Monday comparison to the columns the season code reads, only if the Preview run confirms the need.
8. **Docs.** Update `docs/ops/weekly_runbook.md` (line 270 says the Monday refresh fetches "No schedule"; add the new step and the stop behavior), `docs/status.md`, and correct the statements that the data has no time-TBD flag (`docs/status.md:59`, `session_logs/2026-10-25/01-final-site-review.md`).

## Validation

- Focused tests: `tests/test_weekly_automation.py`, `tests/test_build_market_revision.py`, `tests/test_check_release_parity.py`, plus a new test for the placeholder detector; then `make check`. No web change, so `make web-e2e` is not needed.
- Preview rehearsal outside the weekly windows: run the Monday market refresh against the current Week 11 Preview release; confirm the 14 placeholder games get real times (one CFBD request), the new release passes parity and `season_verification_v2`, predictions, ratings and grades are unchanged, and Odds quotes now match those games; read back `start_date` values with the Preview `psql` check.
- `git diff --check` and `uv run mkdocs build --quiet`.

## Handoff/amendments

- Resume gate: explicit authorization naming this path, then implementation by a worker in the worktree; the orchestrator verifies and pushes.
- Production activation follows the normal automatic gates on the Monday run.
- Implementation status 2026-11-13 (committed locally on branch `worktree-connor-monday-kickoff-time-refresh`, not pushed to `dev`): items 1 to 8 are implemented with the metadata amendment below; item 7 is implemented as an opt-in `--allow-metadata-corrections` flag on the stop gate, passed only by `refresh-schedule`. Focused tests and `make check` pass.
- Partial Preview rehearsal 2026-11-13 (owner-approved): the full controller could not run because Week 11's first kickoff had passed (the decision skips by design, and `--force` does not override it). Instead `refresh-schedule` ran alone on Preview for Week 11 against `revision_manifest_w11_v2.json`, one CFBD request; all steps succeeded and the stop gate printed `Completed weeks 0..9 match the previous certified revision`. Read-back of the new Silver `games` version: the game set is unchanged, Week 11 placeholder games went from 14 to 0, and 44 games across later weeks received real kickoff times. Nothing was released, pushed or touched in Production.
- Not yet rehearsed: the full controller path (parity, `season_verification_v2`, Odds quote matching, a week before its first kickoff). Planned for Monday 2026-11-16 on Preview with `skip_production`; it needs the code on `dev`, so the push decision is the owner's after Sunday's close.
- Known limits: the builder's eligibility re-check uses the previous manifest's retained quotes and does not cover the retrospective CFBD fallback lines (parity still catches any moved grade); the completed-week stop gate (`verify_completed_week_stability.py`, shared with the Sunday close) compares every non-excluded `games` column for weeks 0..N-2 and stays strict for the Sunday close. Decided 2026-11-13 (option B): the Monday `refresh-schedule` step alone passes `--allow-metadata-corrections`, which ignores `kickoff_utc`, `start_time_tbd`, `venue`, `venue_id`, `attendance`, `excitement_index`, `highlights` and `notes`; scores, teams, week, `neutral_site`, pregame Elo, the game set and `game_outcomes` stay strict.
- Amendments:
  - **2026-11-13, owner-approved: correct game metadata in any week.** Reason: the first version stopped on any completed-week kickoff change, and parity kept earlier weeks strict. The owner's rule is that matchup metadata (time, location, teams) must be fixable whenever found, while matchup data and ratings stay protected. Kickoff time feeds grading (`season/grading.py:194-196` counts a quote only if captured strictly before kickoff) and the cutoff checks, and `neutral_site` is a model input (`ratings_lab/site_context.py`, `features/situational.py`), so the fields split by effect:
    - Display-only (venue name, city, attendance, broadcast): may change in any week with no stop.
    - Integrity-relevant (kickoff time): may change in any week. The run re-grades completed weeks and stops for the owner if any grade, eligibility or cutoff check moves because of a corrected kickoff; it never changes silently.
    - Model-relevant (`neutral_site`, home or away team, week, game set): still a stop; a fix is an explicit repair showing the model impact.
    - Previous approach: only upcoming and later-week `start_date` could change, and a completed-week kickoff change stopped the run. Revised: items 4 and 6 above follow this split. Parity allows `start_date` and the display columns to differ in all weeks when the schedule pin changed; predictions, ratings and grades stay strict. Impact: `check_game_set_unchanged`, parity and a new grade/eligibility re-check change; the Sunday close path is untouched.
