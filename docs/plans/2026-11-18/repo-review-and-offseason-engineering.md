# Repository Architecture Review and Risk-Stratified Engineering Plan

- **Status:** Approved (Phase A1 documentation reconciliation and Phase A2 read-only holdout replay split approved 2026-11-18; Phase B code, database and web architecture packages deferred until after the 2026-12-13 final regular-season close)
- **Created:** 2026-11-18
- **Planner:** Sol
- **Approval source:** Owner approved Phase A1, Phase A2 and full technical documentation of all findings in chat on 2026-11-18, with explicit constraints: (1) no Neon storage/database changes in-season, and (2) isolate the live `dev` weekly pipeline from large-scale code and data-architecture changes during Weeks 13–15.
- **Implementation log:** `session_logs/2026-11-18/01-repo-review-and-offseason-engineering-plan.md` (planning and A1/A2 persistence); future implementation logs per offseason package.
- **Commit policy:** Separate planning and documentation commit on local `dev`; no push without owner instruction.

## Goal and acceptance

Record the complete findings of the 2026-11-18 repository-wide technical review across **Neon storage and release lifecycle**, **Python season preparation (`prepare`) performance**, **PostgreSQL/Drizzle web query execution**, **2026 holdout replay lineage**, **offseason V6 modeling readiness**, and **CI/Makefile operational guardrails**, and stratify execution by **blast radius on the live weekly pipeline (`weekly-season-update.yml`)**.

Acceptance for the in-season phase (Phase A, now through 2026-12-13):

1. **Authority & branch sync (Phase A1):** [Current Status](../../status.md), [Implementation Contracts](../index.md) and the shipped November contract headers reflect PR #39 (`a7d03f2d` on `main`, deploying Stratum CFB v2.0.0, Monday kickoff-time refresh, weekly automation catch-up, near-kickoff line capture workflow, regular-season end state, and the 404 theme fix). Zero executable code is modified.
2. **Risk-isolated 2026 holdout replay readiness (Phase A2):** [2026 holdout replay readiness](../2026-11-12/05-holdout-replay-readiness.md) is split so that **only** the read-only git-pin recovery check (Task 1) and standalone read-only holdout export script (Task 3) are authorized in-season, while Task 2 (modifying `refresh_score_exceptions.py` and `weekly_automation.py` for per-manifest exception filenames) and [Data architecture Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md) are explicitly deferred until after the 2026-12-13 final close.

Acceptance for the offseason engineering packages (Phase B, after 2026-12-13):

3. Every backend, database and web optimization documented below must pass its declared **Shadow Parity Gate** (100% byte-identical `serving-projections.json` SHA-256 for Python season engine changes; 100% identical loader JSON snapshots plus `EXPLAIN (ANALYZE, BUFFERS)` verification for web query changes; export receipt plus 25/25 trigger-enabled verification for Neon release pruning) in an isolated worktree before merging to `dev`.

## Baseline and constraints

- **Inspected baseline:** `dev` (`origin/dev`) at `aae08563`; `origin/main` at `a7d03f2d` (`Merge pull request #39 from connorkitchings/dev`, merging `1036c7e1`). Week 12 is active on Production and Preview (`0a435fd6f2499457f26d7deb`, 66 of 66 games predicted and lined).
- **In-season risk constraint:** `weekly-season-update.yml` checks out `ref: dev` and automatically activates Production when its gates pass. Only three closes remain in the 2026 regular season (Sun 2026-11-22 Week 12→13, Sun 2026-11-29 Week 13→14, and Sun 2026-12-13 Week 15 final close). Any in-season edit to `scripts/ops/weekly_automation.py`, `scripts/pipeline/`, `src/cks_picks_cfb/season/`, or `src/cks_picks_cfb/forecast/` carries live rollover risk and is deferred to post-2026-12-13 unless required by an emergency stop.
- **Neon constraint:** Owner decision 2026-11-18: no Neon pruning, compaction or schema changes during the remaining 3–4 weeks of the 2026 season.

---

## Technical audit findings

### 1. Neon storage lifecycle and per-row provenance bloat

- **Evidence:** In `session_logs/2026-11-15/04-preview-release-prune.md` and [Current Status](../../status.md), the Week 12 close failed four times with `psycopg.errors.DiskFull` (1,024 MB Neon Free project limit) until 13 superseded Preview releases were manually deleted and compacted via a smallest-first `VACUUM (FULL, ANALYZE)` cascade. Project storage is currently **1,084 MB** (Production 629 MB across 8 releases + Preview 455 MB across 5 releases), growing ~75–85 MB per release per branch.
- **Table concentration:** Across 4 compacted Preview releases (236.0 MB of release table/index space), **192.8 MB (81.7%)** sits in four tables:
  - `season_release_team_season_stats`: **78.0 MB** (~19.5 MB / release)
  - `season_release_team_game_measurements`: **42.1 MB** (~10.5 MB / release)
  - `season_release_team_possession_stats`: **39.7 MB** (~10.0 MB / release)
  - `season_release_team_rating_components`: **33.0 MB** (~8.25 MB / release)
- **Redundant per-row JSONB provenance (`src/cks_picks_cfb/season/projection_football.py:450`):**
  - `_team_season_stats` assigns `frame["source_versions"] = [dict(versions)] * len(frame)` on every row of `team_season_stats`. At Week 12 (`12 weeks × 138 teams × 2 roles × 11 metrics = 36,432 rows`), that repeats the identical 420-byte JSONB object (`byplay`, `drives`, `games`, `game_outcomes`, `teams` SHA-256 hashes) 36,432 times per release (~15.3 MB of raw JSONB plus heap/index overhead per release).
  - Neither `web/` (`web/src/lib/queries.ts:632-644`, `web/src/lib/chart-queries.ts:251-256`) nor `src/cks_picks_cfb/season/verification.py` reads `team_season_stats.source_versions`, and `season_releases.revision_manifest_sha256` already pins those five input hashes at the release level.
  - `team_game_measurements` and `team_possession_stats` similarly repeat `source_versions`, `measurement_manifest_sha256`, and `rating_manifest_sha256` on every row even though `matchup_data_publications` records them once per release.
- **Why ad-hoc SQL deletion failed 3 times on 2026-11-15:**
  1. All 25 `season_release*` tables carry `BEFORE INSERT OR UPDATE OR DELETE` immutability triggers (`reject_season_projection_mutation` and `validate_season_release_transition` in `contracts/schema.sql:1615-1806`).
  2. The 16 `MATCH SIMPLE DEFERRABLE INITIALLY DEFERRED` foreign keys (`contracts/schema.sql:1867-1914`) queue pending FK trigger checks on `DELETE` that block `ALTER TABLE ... ENABLE TRIGGER` in the same transaction unless `SET CONSTRAINTS ALL IMMEDIATE` runs first.
  3. Standard `VACUUM` does not reduce physical `pg_database_size`; only a smallest-table-first `VACUUM (FULL, ANALYZE)` cascade (checking free headroom before each table rewrite) reclaims physical disk space to Neon.

### 2. Python season engine (`run_season.py prepare`) $O(W \cdot N)$ computation bottlenecks

- **Evidence:** `run_season.py prepare` took **388 seconds** during the Week 11 close ([Current Status](../../status.md)). While safely under the 2,400-second automation timeout (6× headroom), code inspection identified three pure-computation redundancies:
  1. **~460,000 inner-loop pandas DataFrame scans in `src/cks_picks_cfb/forecast/offsets.py:118-243` (called 13–16 times per `prepare` at `src/cks_picks_cfb/season/prepare.py:107-113`):**
     - On *every* week `w` in `0..active_week`, `prepare.py:107` calls `build_offsets` over the entire 10-season historical corpus (`inputs.historical_population` ~8,936 games + 2026 completed games = ~9,600 games; `inputs.historical_events` ~86,937 scoring events + 2026 events) and discards 99% of the output at line 113 (`offsets = offsets[offsets.season.eq(2026) & offsets.week.eq(week)]`).
     - Inside `team_game_non_offense` (`offsets.py:118-135`), a Python `itertuples()` loop over ~9,600 games × 2 sides = ~19,200 iterations executes a full DataFrame boolean mask `selected[selected["season"].eq(key[0]) & selected["game_id"].eq(key[1]) & ~selected["team"].isin(...)]` on every iteration.
     - Inside `build_offsets` (`offsets.py:194-235`), another `itertuples()` loop over ~9,600 games executes `team_games[team_games["season"].eq(int(season)) & team_games["game_id"].eq(game_id) & team_games["usable"]]` on every game.
     - Across 16 weeks, that totals **~460,000 full DataFrame boolean scans inside Python loops** for a calculation whose 2015–2025 history is invariant across weeks.
  2. **Double execution of `build_measurements` during `close-week` (`scripts/pipeline/refresh_score_exceptions.py:246` and `src/cks_picks_cfb/season/inputs.py:280-320`):**
     - During `close-week` (`scripts/ops/weekly_automation.py:825-840`), `refresh_score_exceptions.py` runs `build_measurements(byplay=...)` across all completed weeks (`0..done`) without reading or writing `measurement-cache`.
     - Next, `weekly_automation.py:835` commits `[manifest, EXCEPTIONS_FILE]`, changing git `HEAD` (`code_sha`), and calls `run_season.py prepare`.
     - Because `inputs.py:287` includes `"code_sha": code_sha` in `cache_identity`, any git commit (even a manifest-only commit) invalidates `measurement-cache` and forces `prepare` to run `build_measurements` across all completed weeks a second time.
  3. **Cumulative play-by-play rescanning in `_team_season_stats` (`src/cks_picks_cfb/season/projection_football.py:433`):**
     - Loops `for week in range(1, active_week + 1):` and calls `build_team_season_stats` (`src/cks_picks_cfb/data/team_stats.py:222`), re-running `true_drive_points()`, `derive_is_drive_play()`, and `scrimmage_play_mask()` on all cumulative plays `active_week` times ($O(W^2)$ play scans; scoped for offseason consolidation in the [Data Architecture Blueprint](../../planning/data_architecture_blueprint.md)).

### 3. Web and PostgreSQL CTE materialization traps (`web/src/lib/`)

- **Evidence (expanding [Web read performance](../2026-10-29/01-web-read-performance.md)):**
  1. **PostgreSQL double-referenced CTE materialization (`web/src/lib/season-release-query.ts:60-82`):**
     - `seasonReleaseDb` attaches 19–23 `WITH <table_name> AS (SELECT ... FROM season_release_<table_name> WHERE release_id = $1)` CTEs to every Drizzle query (~10 KB of SQL text and 19–23 bind parameters per HTTP query).
     - In PostgreSQL 12+, a CTE referenced once is folded into the outer query so predicates push down into the `(release_id, ...)` primary key index. **When a CTE is referenced 2+ times**, PostgreSQL materializes the entire unfiltered CTE for that release into a Tuplestore before filtering:
       - `queryTeamSeasonStats` and `queryTeamPossessionStats` (`web/src/lib/queries.ts:624-728`) invoke `tiedExistsSql` (`web/src/lib/tie-sql.ts:12-18`), referencing `team_season_stats` / `team_possession_stats` in both the outer `FROM` and the correlated `EXISTS (SELECT 1 FROM team_season_stats s2 ...)`. PostgreSQL materializes all ~36,432 rows across all 12 weeks just to return 44 rows for 2 teams on a matchup page.
       - `getCurrentRatings` (`web/src/lib/v5.ts:64-88`) references `v5_rating_snapshots` twice (`FROM v5_rating_snapshots` and `SELECT MAX(cutoff_utc) FROM v5_rating_snapshots`), materializing all ~3,500 snapshots.
       - `loadGamesForWeek`, `loadMarketGamesForWeek`, `loadBiggestEdgesRecord`, and `selectPerformanceRows` (`web/src/lib/queries.ts:822-835, 952-969, 1141-1147`; `web/src/lib/v5.ts:452-459`) run two correlated scalar subqueries per row against `prediction_grades` instead of the `LEFT JOIN` alias pattern already used in `getV5PerformanceDetail` (`web/src/lib/v5.ts:694-695`).
  2. **Eager full-season chart loading on `/stats` (`web/src/app/stats/page.tsx:190-198`):**
     - `load()` unconditionally fetches `getTeamGameStats(season)` (~1,500 rows) and `getTeamGameYardage(season)` (~1,500 rows) inside `Promise.all(...)` on *every* `/stats` request, even when rendering tabs (`adjusted`, `possession`, `downs`, `finishing-drives`, `resume-quality`, `rating-trajectory`, `market-board`) that do not use them.

### 4. CI and Makefile operational guardrails

- **Automation pushes bypass CI ([Current Status](../../status.md)):** `.github/workflows/weekly-season-update.yml` pushes manifest and exception commits to `dev` using `GITHUB_TOKEN`, which suppresses `on: push` workflow runs of `ci.yml`.
- **Unguarded legacy Make targets (`Makefile:205-230`):** While `make weekly`, `publish-week`, `freeze-week`, `close-week`, and `migrate-db` refuse execution, legacy targets `make team-stats`, `make matchup-data`, `make prepare-week`, and `make promote-silver` remain callable without a refusal guard.

---

## Ordered changes

### Phase A: In-season zero-blast-radius work (authorized 2026-11-18)

1. **Task A1: Branch and documentation authority sync (post-PR #39).**
   - Update [Current Status](../../status.md), [Implementation Contracts](../index.md) and the status headers of contracts shipped in PR #39 (`a7d03f2d` on `main`): [Final site corrections](../2026-11-16/final-site-corrections.md), [Site redesign](../2026-11-15/site-redesign-and-analytical-usability.md), [Monday kickoff-time refresh](../2026-11-12/06-monday-kickoff-time-refresh.md), [Score-attribution investigation](../2026-11-12/04-score-attribution-investigation.md), [Prediction-error diagnostics](../2026-11-12/03-prediction-error-diagnostics.md), [Near-kickoff line capture](../2026-11-12/01-near-kickoff-line-capture.md), and [Regular-season end state](../2026-11-11/regular-season-end-state.md).
   - Acceptance: `uv run mkdocs build --strict` and `git diff --check` pass; zero code files modified.
2. **Task A2: Split [2026 holdout replay readiness](../2026-11-12/05-holdout-replay-readiness.md) to isolate the live weekly controller.**
   - Amend `05-holdout-replay-readiness.md` so Tasks 1 and 3 (read-only git-pin recovery verification and standalone `scripts/research/export_2026_holdout.py`) are approved for in-season execution with zero edits to live pipeline files, while Task 2 (modifying `refresh_score_exceptions.py` and `weekly_automation.py` for per-manifest exception filenames) is deferred to post-2026-12-13 alongside [Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md).
3. **Task A3: Record Phase B findings in existing draft contracts and the 2027 offseason backlog.**
   - Update [Web read performance](../2026-10-29/01-web-read-performance.md), [Data architecture Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md), and [Offseason 2027 backlog](../../planning/offseason-2027-backlog.md) with the findings and shadow-verification gates above.

### Phase B: Offseason engineering packages (deferred until after 2026-12-13)

Each package below is executed in its own isolated worktree after the 2026-12-13 final close under its own Terra task:

1. **Package B1: `prepare` runtime optimization (`offsets.py` pre-indexing + content-addressed `measurement-cache`).**
   - Pre-index `teams_by_game` and `usable_by_game` in `src/cks_picks_cfb/forecast/offsets.py` to eliminate ~460,000 inner-loop pandas DataFrame boolean filters per `prepare` run.
   - Key `measurement-cache` in `src/cks_picks_cfb/season/inputs.py` and `scripts/pipeline/refresh_score_exceptions.py` on the 5 pinned input dataset hashes (`schedule`, `finals`, `byplay`, `drives`, `reconciliation`), `through_week`, `play_identity`, and a SHA-256 of the measurement module source files (rather than git `HEAD`), so `prepare` reuses the measurement frames computed by `refresh_score_exceptions.py` across the manifest commit.
   - **Shadow Parity Gate:** Run `run_season.py prepare` on a certified 2026 revision manifest before and after in an isolated worktree; require **100% byte-identical SHA-256** on `serving-projections.json` and every output parquet file.
2. **Package B2: Stage 1a operational safeguards & per-manifest score exceptions.**
   - Execute [Data architecture Stage 1a](../2026-10-28/01-data-architecture-operational-safeguards.md) and Task 2 of [2026 holdout replay readiness](../2026-11-12/05-holdout-replay-readiness.md) after the 2026-12-13 final close, plus add the in-workflow post-commit verification step to `.github/workflows/weekly-season-update.yml` and refusal guards to legacy `Makefile` targets (`team-stats`, `matchup-data`, `prepare-week`, `promote-silver`).
3. **Package B3: Web query & PostgreSQL CTE materialization optimization.**
   - Execute the amended [Web read performance](../2026-10-29/01-web-read-performance.md) contract (replacing double-referenced CTE subqueries in `tie-sql.ts`, `getCurrentRatings`, and `prediction_grades` lookups; lazy-loading `getTeamGameStats` and `getTeamGameYardage` on `/stats`; single-game matchup loader; effective ISR on `/matchup/[gameId]`).
   - **Shadow Parity Gate:** Compare serialized JSON outputs of all affected loaders against Preview DB before and after (zero diff allowed) and record `EXPLAIN (ANALYZE, BUFFERS)` query plans confirming elimination of full-release CTE Tuplestore scans.
4. **Package B4: Neon release retention CLI (`prune_season_releases.py`) & projection provenance slimming.**
   - Build `scripts/ops/prune_season_releases.py` (`make season-prune`) codifying the two-phase trigger-safe delete (`SET CONSTRAINTS ALL IMMEDIATE`, scoped trigger disable/delete/enable with 25/25 trigger assertions, mandatory JSON export receipt, rollback-target protection) and smallest-first headroom-checked `VACUUM (FULL, ANALYZE)` cascade.
   - In the next offseason projection set, drop or empty per-row `source_versions` JSONB duplication on `team_season_stats`, `team_game_measurements`, and `team_possession_stats` (~35–45% storage reduction per release).

## Validation

For this planning and Phase A documentation persistence session:

- `git diff --check`
- `uv run mkdocs build --strict`
- `make contracts-check`
- `make quality-check`

## Handoff/amendments

- **Phase A1 and A3** are completed in this session (documentation only).
- **Phase A2 (Tasks 1 and 3 of `docs/plans/2026-11-12/05-holdout-replay-readiness.md`)** is ready for a fresh Terra implementation session using the copy-ready prompt below:

```text
Use the repository-local implement-plan skill and implement Phase 1 (Tasks 1 and 3 only: read-only git-pin recovery check and standalone read-only holdout export script) of the approved contract at:

docs/plans/2026-11-12/05-holdout-replay-readiness.md

Treat it as authoritative. Do not edit scripts/ops/weekly_automation.py, scripts/pipeline/refresh_score_exceptions.py, or scripts/pipeline/build_season_revision.py (Task 2 is deferred until after 2026-12-13). Preserve its architectural decisions, run its validation, and stop for any material conflict. This request explicitly authorizes Phase 1 implementation.
```
