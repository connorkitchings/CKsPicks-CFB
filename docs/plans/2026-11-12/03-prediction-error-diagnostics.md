# Prediction-error diagnostics, 2021 to 2025 (read-only)

- **Status:** In Progress (implemented on a branch; needs review, commit and pull request into `dev`; site class, conference and a totals-bias diagnostic added by the 2026-11-12 amendment; only the true partial-quarantine re-estimation could not be computed, see the log)
- **Created:** 2026-11-12
- **Planner:** Sol
- **Approval source:** Owner approved implementation 2026-11-12, after [contract 02](02-offseason-research-protocol.md) was approved.
- **Implementation log:** [`session_logs/2026-11-12/02-prediction-error-diagnostics-impl.md`](../../../session_logs/2026-11-12/02-prediction-error-diagnostics-impl.md)
- **Commit policy:** Commit on `dev` with implementation; one pull request into `dev`.

## Goal and acceptance

Section A of the [offseason backlog](../../planning/offseason-2027-backlog.md): find where V5's prediction error is before proposing ideas. Output: one report, `docs/modeling/prediction_error_diagnostics_2021_2025.md`, plus the script that regenerates it. No model, data or release change.

Acceptance:

1. The report reproduces the known 2025 V5 MAEs (margin 14.1596, total 13.3558) before any slice is trusted; a mismatch stops the work.
2. It reports MAE, RMSE and bias, plus interval coverage, for margin and total **separately**, sliced by week of season, rating-gap size, totals regime (low, mid, high), conference group, and home versus neutral site; it also reports the Weeks 0 to 4 prior cost (error by week against the later-season level) and the sensitivity of narrow matchups to the partial-quarantine policy (finding of the [V5 ratings audit](../../modeling/v5_offense_defense_ratings_audit_2026.md)).
3. No slice uses a betting outcome (against-the-spread or over/under result). Slices are by prediction error only.
4. 2026 appears nowhere in the development view. A separate monitoring section for 2026 is added only after the 2026-12-13 final close, and it states that nothing in it feeds model choices.

## Baseline and constraints

- Source: `frozen_v5_predictions(corpus)` in `src/cks_picks_cfb/ratings_lab/evaluation.py:426` (7,318 rows, 2022 to 2025, pinned in the ratings-lab corpus), and the bridge's rolling-origin errors for 2021 via `common_bridge_predictions`. Use `scorecard` for pooled metrics; put new slicing in a new module rather than editing the lab.
- Constraints: read-only on all data; no provider calls. The corpus must load without research bucket credentials (local-output exception), or the work stops and asks for the bucket.
- Out of scope: candidate models, thresholds, any 2026 residual, betting-result slices.
- Risk: slices with few games give noisy MAE; each table shows game counts and the report marks cells under 100 games.

## Ordered changes

1. **Reproduction check.** Load the corpus, compute 2025 pooled MAE per target, compare with 14.1596 and 13.3558. Acceptance: matches to four decimals, otherwise stop.
2. **Slice module and script.** `scripts/research/run_prediction_error_diagnostics.py` plus a pure slicing module under `src/cks_picks_cfb/ratings_lab/`. Tests on synthetic frames: slice counts sum to the total, empty slices are omitted, bias sign is correct.
3. **Report.** Generate the tables, then write findings as plain observations with no candidate fixes. Link the report from `docs/modeling/` navigation and the backlog.

## Validation

`make check`, `git diff --check`, `uv run mkdocs build --strict`. Rerunning the script reproduces the report byte for byte. The reproduction check (task 1) is the gate.

## Handoff/amendments

Implementation finding (2026-11-12): the persisted local corpus has no venue or conference data (`home_host` is 1 and `venue_unknown` is true for all games) and holds only frozen ratings. Frozen V5 equals the v5-common bridge row for row in 2022 to 2025, so slices use the v5-common rows (which add intervals and 2021). A true partial-quarantine re-estimation remains not computable; a descriptive exposure proxy is given instead.

**Amendment 2026-11-12 (owner approved three additions).**

- Reason: the first implementation could not report site class or conference (not in the corpus), and the headline finding (total bias about -2.4 points in every season) needed a decomposition before any idea is proposed.
- Previous approach: venue and conference marked not computable; no totals decomposition.
- Revised approach: (A) join the pinned `fbs_involved_games` dataset (neutral flag, venue id) by season and `game_id`, classify home venue, neutral site, non-home venue not flagged neutral, and venue unknown; (B) slice by the home team's conference in that season (grouped Power, Group of 5, FBS independent, other; plus each conference) and by conference versus non-conference game; (C) a read-only totals over-prediction section: bias by slice, home versus away points, level versus slope, a rolling-origin recentering shown as a diagnostic only, margin-total error correlation, and the share of MAE recentering explains. Data came from one read-only read of the Preview data lake through the corpus's pinned references, then cached in the local lab output; nothing was written to any bucket and no provider was called.
- Impact: report, script and tests extended (`site_context.py`, `total_bias.py`); still development view 2021 to 2025 only, no betting slices, no model or release change, byte-for-byte reproducible with `--check`.

Resume gate: contract 02 approved. Next action: task 1. Material changes return to Sol; record amendments here with reason, previous approach, revised approach and impact.
