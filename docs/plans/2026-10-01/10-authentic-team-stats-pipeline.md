# Authentic Team Stats: Play-by-Play Pipeline, Neon Table, Gated Matchup Read

- **Status:** Approved
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User approved the plan in-session on 2026-10-01 ("it looks good"), with these scope choices: stats pipeline only (page redesign is a later contract), source = our own play-by-play, pre-game snapshot semantics, matchup pages hidden until ready.
- **Implementation log:** Pending (cloud session builds and tests; the real data run is the user's, see Phase 5).
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

## Out of scope
Page redesign in the Picks/Results style; win probability and score projections (need a calibration contract); restoring card deep links; opponent adjustment; contract 04's refactor (keep logic in `src/` so import paths stay compatible).

## Definition of Done
- [ ] Phases 1-4 merged to `dev` with all checks green (pytest `-W error`, ruff, contracts validation, mkdocs strict, web lint/typecheck/unit/e2e/build).
- [ ] Leak test proves week N stats exclude week N games.
- [ ] `/matchup/*` returns 404 and `noindex` when the flag is off.
- [ ] No synthetic or hash-derived stat anywhere (`grep` guard recorded in the session log).
- [ ] Phase 5 spot-check recorded; `docs/status.md` updated; contract marked Implemented.

## Risks and rollback
- **Silver column names differ:** the dry run catches it; adjust constants, not the design.
- **Early-week noise:** nullable metrics, sample-size columns and null ranks.
- **Migration collision:** use 0020; re-check the next free number before applying.
- **Rollback:** drop `team_season_stats` (the web falls back to no stats); revert the commits; the flag keeps pages closed.
