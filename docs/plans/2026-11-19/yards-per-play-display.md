# Yards per play display

- **Status:** Approved (owner decision 2026-11-19)
- **Created:** 2026-11-19
- **Approval source:** Owner decision of 2026-11-19 (chat): do both the display and the predictive diagnostic, display first. The display is context only.
- **Implementation log:** `session_logs/2026-11-19/02-ypp-display-planning.md` (planning only; implementation not started in that session).
- **Related:** [Adjusted YPP predictive diagnostic](adjusted-ypp-predictive-diagnostic.md) (Draft, runs after the 2026-12-13 final close).
- **Commit policy:** Local changes on `dev`; no push without owner instruction.

## Context

Pick Six+ ranks Indiana #5 in opponent-adjusted yards per play, while the V5 offense rating ranks them #39. V5 never used yards: the offense rating's one input is opponent-adjusted points per possession (a 4-pass iterative adjustment) plus a shrinking 2025 prior. Yards per play (YPP) was a V4 feature (removed 2026-10-22) and has never appeared in the V5 matchup or team stats tables.

Indiana is a real outlier, not a calculation artifact. Scratch opponent-adjusted YPP ranks them #12 (#10 with garbage time included). Other measures: adjusted EPA per play #21, pass PPA #5, explosive rate #13, scoring opportunities per drive #17; but #84 in points per scoring opportunity, #83 in rush PPA, #60 in success rate, and red-zone success of 36% against an FBS average of 43%. Raw points per possession is 2.38 (#41) and adjusted is 2.41 (#47). Across teams, the rank correlation between adjusted YPP and the V5 offense rating is 0.86. Whether YPP predicts future scoring better than points per possession has not been tested.

The scratch calculation ranked 129 teams against 138 in the release, most likely a team-name join issue; the pipeline uses the release's team set.

**Owner decision:** do both, display first. The display is context only. V5 stays frozen for the 2026 record, and YPP does not enter ratings or forecasts.

## Pipeline

1. `charts/adjusted_epa.py`: extract a shared helper that does the venue fit and `adjust_possession_history` from rows of `(team, opponent, site, role, numerator, denominator)` and returns raw, neutral and adjusted values keyed by `(team, role)`. The output of `adjusted_epa_window` must stay byte-identical, with an equality test.
2. `data/team_stats.py`:
   - `ypp`: mean `yards_gained` over `scrimmage_play_mask` plays (for the defense, yards allowed).
   - `adj_ypp`: venue-neutral, opponent-adjusted value from the helper, using the same eligible plays and FBS-vs-FBS games. `FIRST_ADJUSTED_WEEK = 3`; earlier weeks are null and carry no rank.
   - `n` is the play count. `games` matches the other metrics, which keeps the `season_verification_v2` `_stats_games` check passing.
   - `METRICS` gains `"ypp": (True, False)` and `"adj_ypp": (True, False)`.
3. `metrics/registry.py`: `MetricDef` entries for both metrics (`test_metric_registry` requires them).
4. No schema or migration change. `season_release_team_season_stats` is long-format with an unconstrained text `metric` column, and `projection_football._team_season_stats` picks the rows up automatically.

## Web

- Add a `"yds"` format (two decimals).
- Add rows `ypp` ("Yards/play") and `adj_ypp` ("Adj. yards/play") to the `possession` section of `web/src/lib/team-stats.ts`, after PPA/play. A comment states that adjusted YPP is display only.
- Update the fixtures and tests.

## Tests (behavior)

- `ypp` equals the filtered mean yards (kicking plays, garbage time and penalties excluded).
- Defense `ypp` equals yards allowed.
- `adj_ypp` is null before week 3.
- An offense that faces only strong defenses gets an adjusted value above its raw value.
- Rank direction is correct for both metrics.
- Equality test for the refactored adjusted-EPA output.

## Docs

- `docs/modeling/measurement_catalog.md` entry for each metric, stating that neither is a V5 input.
- `CHANGELOG.md` entry (Unreleased).

## Rollout and timing

- Work in the worktree `.worktrees/connorkitchings-ypp-display`, merge into local `dev`, run `make check` and `make web-e2e`, and push `dev` only after the owner says ready, per the AGENTS.md push rules.
- New rows first appear in the next close-week release. Close-week parity compares only predictions, grades and rating snapshots (`_check_close_week` in `scripts/pipeline/check_release_parity.py`), so added rows do not trip it.
- The Monday market refresh compares against that close release, which already has the rows. A market refresh built on the new code before a close would flag "new in the candidate" rows, so the code must not reach `main` between a close and its Monday refresh unless the owner accepts that.
- Scheduled runs execute from `main`, so a `dev` to `main` release PR is needed. Target merging before the Sunday 2026-11-22 close, outside 17:00-19:30 UTC.
- Until that close runs, the two rows show "—".

## Verification

- Targeted pytest: `test_team_stats`, `test_metric_registry`, `test_charts_module`, `test_season_projection_charts`, `test_season_projection_football`.
- Dry build: `scripts/pipeline/publish_team_stats.py --dry-run --as-of-week 12 --environment preview`. Confirm Indiana `adj_ypp` ranks near 10-12 (the scratch calculation had no venue term).
- `make check`, then `make web-e2e` with a screenshot under `CFB_UI_TEST_MODE=1`.
- After the next close release, check `/api/health` and spot-check Indiana's matchup page.

## Not in scope

- Any use of YPP in ratings, the bridge, forecasts or the 2026 record.
- Any change to V5.
