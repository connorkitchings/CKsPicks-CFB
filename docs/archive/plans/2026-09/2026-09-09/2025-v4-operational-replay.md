# 2025 V4 Week-by-Week Operational Replay

- **Status:** Implemented 2026-09-10
- **Created:** 2026-09-09
- **Planner:** opencode session (plan mode investigation)
- **Approval source:** User selected "Week-by-week operational replay" and answered
  labeling/coverage decisions on 2026-09-09, authorized execution ("go"),
  approved the pre-write code commit, and approved production promotion.
- **Scope note:** Current-model (V4) track only. Not the data-first transformation
  program and not the separate 2026 rebuild plan.
- **Result:** 16 weeks replayed in Preview and Production; 762 games
  (incl. Army-Navy week 16); honest model_id
  `v4-locked-test-replay-20260909b`; final YTD spread **380-366-16**,
  total **340-292-5** (bets-only grading; below-threshold No-Bet games
  ungraded, per operational convention).

## Goal

Replace the ad-hoc 2025 backfill currently in Neon with a genuine week-by-week
operational replay of the **selection-time V4 model** (trained 2021-2024) using
authentic pre-kickoff provider lines, executed through the real pipeline
(`generate → publish → freeze → score`) so every run has immutable artifacts,
correct provenance, and honest labeling.

## Verified Current State

- Published 2025 runs `v4-2025-w1..w15` (761 games) are `scored` under a
  mislabeled `model_id` (`week0-2026-v4-strict-20260818-r2`); their recorded
  artifact URIs do not exist in R2 and `code_sha` is null.
- The `-r2` production bundle declares `training_years=[2021..2025]` and trained
  on the v5 frame `fe55e758` — in-sample for 2025, unusable for replay.
- The selection-time bundle prefix
  `artifacts/preview/models/week0-2026-v4-strict-20260818/` is incomplete
  (8/14 route files, no manifest).
- Certified out-of-sample predictions exist in
  `rating_v4_historical_predictions` version `f4ec062c7f931f125ce6be99`
  (761 games, weeks 1-15, excludes Army-Navy) and serve as the parity benchmark.
- The v5 feature frame `fe55e758` covers 2021-2026 with per-game point-in-time
  features; 2025 has 762 games including week 16.
- Bronze `raw/betting_lines/year=2025/` has 16 week partitions; Silver
  `market_quotes` has no 2025 partitions.
- `replay_season.py` implements the weekly loop but resolves catalog refs
  as-of each cutoff, which fails for 2025 (nothing registered before 2026);
  the replay therefore needs explicit immutable refs.
- `refit_game_ordinal_bundle.py --feature-ref-uri --routing-report-uri
  --bundle-id` can rebuild a bundle from frozen selection lineage.

## Confirmed Decisions

1. **Scope:** week-by-week operational replay (not an integrity patch of the
   backfill, not the 2026 rebuild, not transformation).
2. **Labeling:** new honest `model_id`
   (`v4-selection-2021-2024-replay-20260909`), `system_name:
   "Trench Warfare V4"`.
3. **Army-Navy (week 16):** include iff a provider line exists in Bronze;
   otherwise exclude and document.

## Implementation Phases

### Phase 0 — Pin the lineage (read-only verification)

- Confirm 2025 provider-line coverage per week/game from Bronze (esp. week 16
  Army-Navy); record games lacking lines (they stay unlined, fail-closed).
- Confirm a 2025 Silver `games` dataset (or equivalent immutable schedule ref)
  exists for the `games` entity.
- Confirm frozen selection refs are readable: selection feature ref
  (`model-ready-strict-selection-20260817.json`, version `e6ebb94b...`),
  selection report (design SHA `ae34ddc7...`), v5 frame `fe55e758`.
- **Acceptance:** coverage report; week-16 include/exclude resolved.

### Phase 1 — Rebuild the selection-time bundle

- Run `refit_game_ordinal_bundle.py` with the frozen selection feature ref and
  routing report, `--bundle-id v4-selection-2021-2024-replay-20260909`,
  ENV=preview.
- **Acceptance:** manifest declares `training_years=[2021..2024]`; all routes
  load via `load_model_bundle_v3`; parity check — batch-predict the certified
  v5 2025 rows and match `rating_v4_historical_predictions` within tolerance
  (report max |delta| per route; any route mismatch → stop and investigate).

### Phase 2 — Code changes (committed before artifact writes)

- `snapshot_week_inputs.py`: accept `point_in_time_matchups_v5` as
  `--prepared-gold-ref-uri` (shared with the 2026-fix plan).
- New config `conf/weekly_bets/v4_2025_replay.yaml` (replay bundle,
  `year: 2025`, honest ids).
- New orchestrator `scripts/pipeline/replay_season_v4.py` modeled on
  `replay_season.py`: per week — explicit refs for games/betting_lines/gold
  (no catalog as-of), `as_of` = 1s before first kickoff, then
  `generate_weekly_bets` → `publish_to_db` → `freeze_week` (waiver:
  historical replay) → `score_weekly_bets` → `score_to_db`, all against
  `PREVIEW_DATABASE_URL`.
- Gold inputs: per-week immutable slices of certified v5 (parent-linked to
  `fe55e758`). Market: immutable per-week market datasets materialized from
  Bronze CFBD lines with provider-line semantics.
- Tests for the new/changed seams; Ruff + focused pytest.

### Phase 3 — Execute replay in Preview

- Run weeks 1-16 (week 16 per Phase 0 finding). Ensure the Army-Navy result
  exists in `game_results` if included.
- **Acceptance:** every run `scored` with real R2 artifacts at recorded URIs;
  coverage 761-762 games; prediction parity vs certified artifact; grades
  recomputed on authentic lines; win rates near locked-test levels (leans may
  shift slightly with authentic lines — predictions must not).

### Phase 4 — Production promotion (explicit user approval gate)

- Mark backfill runs `v4-2025-w1..w15` `superseded` (the web's
  `getRunForWeek` picks the latest frozen/scored run per week, so replay runs
  take over automatically; legacy `TW-V2-2025` runs remain untouched).
- Update `games.model_id` for 2025 to the replay bundle id; recompute 2025
  `system_stats`; verify local web render of `?season=2025` weeks 1-16.

### Phase 5 — Documentation

- Session log, plan lifecycle update, runbook note on historical replay
  semantics.

## Constraints and Risks

- Preserve the dirty worktree (session 04/05 web + docs changes are a separate
  pending commit; this plan assumes they land).
- No modification of certified artifacts, the `-r2` bundle, 2026 runs, or the
  shared v5 frame version — new immutable versions only.
- Main risk: rebuilt routes failing parity with the certified artifact;
  mitigation is the Phase 1 gate before any pipeline runs.
- Cost: mostly Phase 3 compute (16 weeks of inference + grading).

## Amendments

### Amendment 1 — Exact frozen baseline/blend semantics (Phase 1)

**Reason:** The first rebuilt bundle (`v4-selection-2021-2024-replay-20260909`)
used the production-style prior-Ridge approximation for baseline/blend routes
and failed the parity gate on baseline routes (mean |delta| 10-12) with small
blend deviations (~0.1-0.4). Investigation showed the frozen V4 design reads
frame columns: baseline routes return the temporal OOF `baseline_*_prediction`
columns, blends return frozen weights of `preseason_*_prediction` /
`current_*_prediction` components.

**Revised approach:** Added `--baseline-source frame_columns` to
`refit_game_ordinal_bundle.py`, emitting exact pass-through/component-blend
linear models over the frozen OOF columns with manifest annotations
(`route_semantics`, `source_columns`). Required no production inference
changes. The final bundle `v4-locked-test-replay-20260909b` passed parity
with max |delta| 7.1e-15 (float epsilon) across all 1,522 certified
game-target rows.

### Amendment 2 — Gold input is the certified frame directly (Phase 2)

Per-week slices of the v5 frame were unnecessary: `prepare_inference_features`
filters by season/week, so each run's input ref is the certified v5 frame
`fe55e758` itself.

### Amendment 3 — Market quotes lineage (Phase 2)

`publish_to_db` requires quote-level lineage when runs reference market
snapshots. The orchestrator additionally registers a `market_quotes` dataset
(`32db239e...`) from the same Bronze captures and includes it in input refs
as entity `betting_lines_quotes`, matching `snapshot_week_inputs` conventions.

### Amendment 4 — Backfill runs left in place (Phase 4)

The `prediction_runs.state` check constraint allows only
(preview, published, frozen, scored) — no `superseded` state exists, and
adding one was out of scope. The backfill runs (`v4-2025-w1..w15`) remain
`scored`; the web's latest-frozen/scored-run resolution shows the replay runs
(verified for all 16 weeks). The production `current_week` singleton was
snapshotted before promotion and restored to the live 2026/2 run afterward.

## Implementation Record

- **Bundle:** `v4-locked-test-replay-20260909b`, manifest SHA
  `f1bb1f0a6d48001230ae6fc55034994c9777009427753c4451f67f33edbeade4`,
  `training_years=[2021..2024]`, `baseline_source=frame_columns`.
- **Loader opt-in:** `load_model_bundle_v3(..., allow_locked_test_window=True)`
  threaded from `conf/weekly_bets/v4_2025_replay.yaml`; production defaults
  unchanged.
- **Market datasets:** `market_snapshots` version `e4061aab...`
  (consensus_then_median_v1; weeks 15-16 `captured_at` backfilled from Bronze
  manifest write_time), `market_quotes` version `32db239e...`.
- **Runs:** `v4replay-2025-w1..w16` in Preview and Production, each
  generate → publish → freeze (waiver: historical replay) → score →
  score_to_db. Preview ≡ production predictions verified.
- **Army-Navy (401762521):** routed `established`, predicted Navy +3.32 /
  total 55.25 vs line Navy -6 / 37.75; graded spread win (Army covered),
  total loss.
- **Totals grading note:** replay grades only bet games (8 week-1 totals with
  |edge| < 1.5 are No-Bet and ungraded), consistent with live 2026 runs; the
  prior backfill graded every game including No-Bets.
- **Removed scaffolding:** four orphan files from a failed week-1 attempt
  (never published, zero consumers) were deleted before the clean rerun:
  `replay-2025-v4-w1/input_refs.json` and the w1 predictions
  `manifest.json`/`point_in_time_features.csv`/`predictions.csv`.

### Amendment 5 — Comprehensive totals grading (2026-09-10)

**Reason:** The operational scorer writes grades only for above-threshold bets,
leaving 125 totals ungraded (all below the 1.5 edge threshold; e.g. 2025 week 2
Texas vs San Jose State had a total edge of 0.71). The retrospective season
record was therefore incomplete.

**Approach:** New `scripts/pipeline/backfill_replay_grades.py` grades every
replay prediction carrying a frozen line, a lean, and a final score using the
identical frozen-line rule (`frozen_line_v2`), never overwriting existing
grades, then refreshes `system_stats`. Applied to Preview then Production.
Final 2025 record: spread **380-366-16**, total **398-359-5**. Weeks 1-15
totals match the prior backfill exactly; the one delta is Army-Navy's total
loss. Live 2026 bets-only semantics intentionally unchanged.
