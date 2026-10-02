# Authentic Team Stats: Play-by-Play Pipeline, Neon Table, Gated Matchup Read

- **Status:** Approved
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User approved the plan in-session on 2026-10-01 ("it looks good"), with these scope choices: stats pipeline only (page redesign is a later contract), source = our own play-by-play, pre-game snapshot semantics, matchup pages hidden until ready.
- **Implementation log (2026-10-02):** Phase 5 ran on Preview, then on production by the user the same day (see Amendment 1). Remaining: release `dev` to `main`, then enable the flag.
- **Earlier log:** Phases 0-4 are on `dev` (stats layer, migration 0020, `publish_team_stats.py`, web read layer behind the gate, fixture e2e). Only Phase 5 (real data, user-run) remains. Note: unknown matchup ids render the not-found page with status 200 because the root `loading.tsx` streams; the page is `noindex`.
- **Commit policy:** One commit per phase on `dev`. Merge `dev` into `main` only after the Phase 5 spot-check.
- **Supersedes:** the former `02-authentic-matchup-stats-pipeline-and-presentation.md` (this file replaces it with corrected facts) and the intent of `03-advanced-stats-matchup-breakdown.md` (its synthetic stats were removed).

## Goal
Show authentic, football-accurate team stats and national ranks on `/matchup/[gameId]`, computed from the repository's own play-by-play, stored in Neon, and served only for published weeks. Zero simulated or hash-derived values anywhere.

## Current state (verified 2026-10-01)
- Neon has no team-stats table. The matchup page reads `games`, the week queries and `v5_rating_snapshots` (`web/src/lib/matchup.ts`). The "Advanced Matchup Stats" block is a placeholder.
- Dead code left from the synthetic era: `web/src/lib/matchup-math.ts` and its test, `TeamProfilePillars.tsx`, `MatchupKeyTakeaways.tsx`; `UnitMatchupTable.tsx` is unused but reusable.
- Authentic measurements exist in `src/cks_picks_cfb/ratings/observations.py` (`build_measurement_observations`): `epa_per_play`, `success_rate`, `explosive_rate_20`, `turnover_rate`, `points_per_scoring_opportunity` (true PPSO, reconciled with the score stream), `average_start_field_position`. Garbage-time plays are excluded (`garbage == 0`). Inputs are Silver `byplay`, `drives`, `games`.
- **Do not exist yet:** pass/rush EPA split, early-down EPA, scoring-opportunity rate. 3rd/4th-down conversion exists only in the older `features/aggregations/team_game.py` lineage (different filters), so it is recomputed here from `byplay`.
- Corrections to the superseded draft: the next migration number is **0020** (0019 is `game_venues`); `migrate_db.py` applies `contracts/migrations/*.sql` and has no per-migration Python entry; there is no `canonical_team_name()` (team names come from the Silver games table as written by CFBD); the measurement code lives in `ratings/observations.py`, not `data_first_phase3_v2.py`; the table needs grants.
- `/matchup/[gameId]` is publicly reachable and indexable by guessable id (nothing links to it, no `noindex`, no gate). Errors return a 200 "not found" card.

## Decisions
1. **Snapshot key:** `(season, as_of_week, team)` = stats from games completed **before week N's slate**; every game in week N uses that snapshot. Leak-free and identical to what the picks knew. A team's earlier same-week game is not included (documented on the page later).
2. **Opponent filter:** FBS-vs-FBS games only. Raw values (not opponent-adjusted); V5 ratings remain the adjusted view.
3. **Plays:** same filter as `observations.py` (drive plays, garbage time excluded). Share the helper; do not write a second definition.
4. **Metrics, offense and defense each:** pass EPA/play, rush EPA/play, early-down (1st/2nd) EPA/play, success rate, explosive rate (20+ yards), scoring-opportunity rate (CFBD drive flag `had_scoring_opportunity`, used as given), points per scoring opportunity (true PPSO), average start field position, 3rd/4th-down conversion %. Turnover rate is stored too.
5. **Ranks are computed and stored by the publisher** (single source of truth) with direction handled there: higher is better for offense; lower is better for defense EPA, success, explosive, scoring-opportunity rate, PPSO and conversion %. Start field position direction is documented in the code and tested.
6. **Honest sample sizes:** metric columns are nullable; the row stores `games`, `plays`, `drives` and `cohort_size`. Ranks are null below a minimum games threshold (default 1; tunable constant) so early weeks show a dash, never fake precision.
7. **Serving gate:** the web reads stats only for weeks passing `isPublishedWeek`. The table holds no model fields.
8. **Exposure:** `/matchup/*` gets `noindex` and an env flag `CFB_MATCHUP_ENABLED` (default off; on in `CFB_UI_TEST_MODE`), returning a real 404 when off (pattern: `web/src/lib/proto-gate.ts`). Card deep links stay absent until the user approves.

## Phases

### Phase 0: Contract and docs
This file; mark the old draft superseded; update `docs/status.md` and `docs/plans/index.md`.

### Phase 1: Python measurement layer (pure, tested)
`src/cks_picks_cfb/data/team_stats.py`: `build_team_season_stats(byplay, drives, games, *, season, as_of_week) -> DataFrame`, reusing the play/drive helpers from `ratings/observations.py` (extract shared helpers rather than copy). Tests in `tests/test_team_stats.py`: ratio-of-sums aggregation, defense rank direction, garbage-time exclusion, FCS-opponent exclusion, week cutoff leak test (week N excludes week N games), small-sample nulls, ties, bye weeks, no division by zero.

### Phase 2: Schema
Long format (decided during Phase 1): one row per `(season, as_of_week, team, role, metric)` with `value`, `n`, `games`, `rank`, `cohort_size`; adding a metric needs no migration.
`contracts/migrations/0020_team_season_stats.sql` (append-only, idempotent; `GRANT SELECT TO cks_web`, `GRANT SELECT, INSERT, UPDATE TO cks_pipeline`); sync `contracts/schema.sql`, `contracts/schema.ts` and the byte-identical `web/src/lib/schema.ts`; migration test in `tests/test_migration_integration.py` (one file, because DB-reset tests must not run in parallel); `uv run python contracts/validation.py`.

### Phase 3: Publisher
`scripts/pipeline/publish_team_stats.py` (`--season`, `--as-of-week`, `--environment preview|production`, `--dry-run`), modeled on `publish_game_venues.py`: reads validated Silver datasets via `catalog.dataset_versions` + `read_dataset`, calls Phase 1, upserts in one transaction, idempotent, never touches runs or predictions. Dry run prints columns, coverage, null counts and sample teams. Add a step to `docs/ops/weekly_pipeline.md`.

### Phase 4: Web read layer and gate
`getTeamSeasonStats(season, week)` in `web/src/lib/queries.ts` with the `to_regclass` guard; `matchup.ts` builds offense-vs-defense rows with null safety; remove the dead code listed above; wire `UnitMatchupTable` into the page behind the flag; `noindex`, flag gate, real 404; remove the "Blitzkrieg V5" fallback name in market mode. Unit tests in `test:publication`; fixture-backed e2e under `CFB_UI_TEST_MODE=1`.

### Phase 5: User-run data steps (credentials required, not run from the cloud)
1. Dry run: `PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py --season 2026 --as-of-week 5 --environment preview --dry-run`; confirm Silver column names and coverage.
2. Apply 0020 to Preview (`migrate_db.py --database-env PREVIEW_DATABASE_URL`), publish weeks 0-5, spot-check a few teams against CFBD numbers.
3. Repeat for production via `scripts/ops/with_production_pipeline_env.sh`.

## Amendment 1 (2026-10-02): first real-data run

Approved in-session ("amend 10, implement here"; production deferred; Silver reaches production by **catalog promotion**).

Findings from the first Preview dry run, and the fixes:
1. **`early_down_epa` and `conv_rate_3rd_4th` were null for all 138 teams.** Silver `byplay` has `yards_to_first` (not `distance`) and per-down `thirddown_conversion`/`fourthdown_conversion` flags. Fixed: conversion uses the flags when present, else `yards_to_first` (goal-to-go 0/null falls back to `yards_to_goal`); return touchdowns and turnovers never count as conversions. A build with neither distance nor flags now fails loudly instead of emitting nulls.
2. **Pass/rush** uses Silver's `dropback`/`rush_attempt` flags (regex only as a fallback).
3. **Guards:** regular season only (`season_type`); every eligible game must have byplay and drives rows; score-stream errors surface as `TeamStatsContractError`.
4. **Provenance:** `team_season_stats.source_versions` (JSONB) records the Silver versions behind each row. Migration 0020 was edited in place: it had not been applied to any database (verified on Preview and production, both at 0018).
5. **Publisher:** `--weeks 1-5`, version pins, one transaction, prints the chosen Silver refs.
6. **Production inputs:** production's catalog has no 2026 `byplay`/`drives`. Preview and production share one R2 bucket, so `scripts/pipeline/promote_silver_versions.py` registers the existing immutable versions (plus parents and source captures) after re-verifying manifests and content hashes. Different buckets are refused. Production dry run: 6 new versions, 11 captures, all verified; nothing written.
7. **Validation:** `scripts/pipeline/verify_team_stats.py` compares with CFBD advanced stats. CFBD includes FCS games, so the gate (Spearman >= 0.85 on EPA/play and success rate) applies to like-for-like teams (CFBD play count within 5% of ours); on that subset rho is 0.96-0.99 for weeks 3-5. The all-teams rho is lower in weeks 3-4 for the same reason (0.77-0.88) and is informational.
8. **Web:** matchup ratings are as of kickoff (`getRatingsAsOf`); rank badge tiers are relative to the ranked pool; ratings stored under nine legacy team names resolve through `TEAM_LOGO_MAP`; the `to_regclass` guards read the Neon result shape (see the decision log; the old guards always reported a missing table).
9. The Phase 5 migration command was wrong (`--database-env PREVIEW_DATABASE_URL`, the pipeline role). Correct: `zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/migrate_db.py --database-env DATABASE_URL`.

Known limits: 133 team-games (about 31%) fail the shared V5 score-stream reconciliation, so their points-per-scoring-opportunity is null (same rule as V5; `n` shows the sample). Weeks are matched by week number, not kickoff time.

## Out of scope
Page redesign in the Picks/Results style; win probability and score projections (need a calibration contract); restoring card deep links; opponent adjustment; contract 04's refactor (keep logic in `src/` so import paths stay compatible).

## Definition of Done
- [ ] Phases 1-4 merged to `dev` with all checks green (pytest `-W error`, ruff, contracts validation, mkdocs strict, web lint/typecheck/unit/e2e/build).
- [ ] Leak test proves week N stats exclude week N games.
- [ ] `/matchup/*` returns 404 and `noindex` when the flag is off.
- [ ] No synthetic or hash-derived stat anywhere (`grep` guard recorded in the session log).
- [x] Phase 5 on Preview: migration applied, weeks 1-5 published (10,460 rows), CFBD check recorded in Amendment 1.
- [x] Production (user-run 2026-10-02): Silver promoted (6 versions, 11 captures), 0019/0020 applied with the owner credential, weeks 1-5 published (10,460 rows, one `source_versions` set matching Preview), grants `cks_web` SELECT and `cks_pipeline` INSERT/SELECT/UPDATE; verified read-only.
- [ ] Release `dev` to `main` and enable `CFB_MATCHUP_ENABLED=1`; then mark Implemented.

## Risks and rollback
- **Silver column names differ:** the dry run catches it; adjust constants, not the design.
- **Early-week noise:** nullable metrics, sample-size columns and null ranks.
- **Migration collision:** use 0020; re-check the next free number before applying.
- **Rollback:** drop `team_season_stats` (the web falls back to no stats); revert the commits; the flag keeps pages closed.
