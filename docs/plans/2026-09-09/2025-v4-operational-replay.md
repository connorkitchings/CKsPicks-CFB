# 2025 V4 Week-by-Week Operational Replay

- **Status:** Approved
- **Created:** 2026-09-09
- **Planner:** opencode session (plan mode investigation)
- **Approval source:** User selected "Week-by-week operational replay" and answered
  labeling/coverage decisions on 2026-09-09, then authorized execution.
- **Scope note:** Current-model (V4) track only. Not the data-first transformation
  program and not the separate 2026 rebuild plan.

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

- None yet.
