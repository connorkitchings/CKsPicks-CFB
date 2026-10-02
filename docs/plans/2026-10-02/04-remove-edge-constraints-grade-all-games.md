# Remove Edge Constraints and Grade All Games

- **Status:** Implemented
- **Created:** 2026-10-02
- **Planner:** Sol (plan-session)
- **Approval source:** User review and authorization on 2026-10-02 (Week 5 audit verified; Preview-first rehearsal + pre-mutation snapshots + Week 5 close gate added)
- **Implementation log:** `session_logs/2026-10-02/08-remove-edge-constraints-implementation.md`
- **Commit policy:** Commit with implementation after validation; user executes git operations.

## Goal

Eliminate the sub-threshold "No Bet" and ungraded behavior across the college football forecasting platform. Every FBS game that has a model forecast and a market line will:
1. Display a model pick and lean (`home`/`away` for spreads, `over`/`under` for totals) based strictly on model margin/total versus the market line.
2. Receive a certified grade (`win`, `loss`, `push`) upon completion.
3. Include all games in season and weekly records without edge cutoffs.

Observable success criteria:
1. All 215 games in Weeks 0–4 display both a spread lean and total lean (except for 1 unlined total in Week 3).
2. All completed games with market lines receive certified grades on both targets:
   - Spread season record: **100–112–3** (47.2%, 212 decided across 215 games).
   - Total season record: **112–102–0** (52.3%, 214 decided across 214 lined games).
3. The Performance tab (`system_stats` table) matches the updated full-slate records.
4. Future slates (beginning with live Week 5) generate leans and grades for all lined games.

## Current State & Frozen Week 5 Audit

- On 2026-09-26, contract `02-unified-no-bet-threshold.md` introduced thresholds:
  - Spreads: `spread_edge_threshold: 1.0` (sub-1.0 edges marked "No Bet", published as `null` lean, ungraded).
  - Totals: `total_lean_threshold: 1.0` and `total_edge_threshold: 1.5` (sub-1.0 marked "No Bet"; $[1.0, 1.5)$ showed lean but ungraded).
- Current database contents (`site_week_selections` for Weeks 0–4):
  - 16 spread games have `spread_lean = null` and no grade in `prediction_grades` (official record: 93–103–3).
  - 56 total games have no grade in `prediction_grades` (55 lined games + 1 unlined game; official record: 82–77–0).
- **Week 5 Frozen Run Audit (`2026w5-v5repair-20260929-p2`):**
  - Read-only query against `predictions`:
    - `total_rows: 56`, `null_spread: 7`, `null_total: 8`.
  - Read-only query against `prediction_market_selections`:
    - Spreads: `away: 13`, `home: 43` (56/56 assigned, **0 "No Bet"**).
    - Totals: `over: 42`, `under: 14` (56/56 assigned, **0 "No Bet"**).
  - **Resolution / Decision:** The web serving layer (`getGamesForWeek` in `web/src/lib/queries.ts`) overlays `prediction_market_selections` on `predictions`, meaning **Week 5 already renders 56/56 spreads and 56/56 totals with a model lean on the public site**.
  - **Immutability Guarantee & Week 5 Close Gate:**
    - To strictly preserve frozen immutability, **no mutation will be made to the frozen Week 5 prediction records**.
    - **Grading Path Resolution:** `score_to_db.py:264-270` takes its grading side from the `spread_lean` / `total_lean` columns and skips rows where side is null. Since frozen Week 5 predictions contain 7 null spread leans and 8 null total leans, close-week must not simply skip them.
    - **Requirement:** After certified finals, the close flow must produce all 56 spread grades and 56 total grades (minus any unlined). Terra traces whether close-week re-derives leans under threshold 0.0 from selections; if the standard operational scorer consumes frozen null leans and skips rows, `backfill_v5_unconstrained_grades.py` will be extended to grade Week 5 post-close (grades table only in Neon; frozen `predictions` artifact stays 100% untouched).

## Proposed Approach

1. **Config Harmonization:** Update active weekly bet configs (`conf/weekly_bets/v5_intended_update_2026.yaml`, `v5_replay_2026.yaml`, `v5_preview_2026.yaml`) to set:
   - `spread_edge_threshold: 0.0`
   - `total_edge_threshold: 0.0`
   - `total_lean_threshold: 0.0`
2. **Serving & Producer Logic:**
   - In `src/cks_picks_cfb/inference/v5_serving.py` and `scripts/pipeline/build_v5_intended_update_serving.py`, remove the filtering rule that forces sub-1.0/sub-1.5 targets to `"No Bet"`.
   - Any game with `model != market` receives its mathematical direction (`home`/`away`, `over`/`under`) and is fully gradable.
3. **Dedicated Backfill Script with Preview-First Gating:**
   - Implement `scripts/pipeline/backfill_v5_unconstrained_grades.py` (patterned after the tested `backfill_replay_grades.py`).
   - CLI flags: `--dry-run`, `--environment preview|production`, `--confirm-production`, `--snapshot-dir`.
   - **Step 1 (Preview Rehearsal):** Run on Preview Neon database (`PREVIEW_DATABASE_URL`). Verify 16 spread grades and 55 total grades inserted. Verify `system_stats` recomputed to 100–112–3 and 112–102–0.
   - **Step 2 (Pre-Mutation Snapshot):** Before running on production, export pre-mutation rows of `prediction_grades`, `predictions`, and `system_stats` for Weeks 0–4 to `artifacts/backups/2026-10-02/pre_unconstrained_grades_snapshot.json`.
   - **Step 3 (Production Execution):** Run with `--environment production --confirm-production`.
4. **Documentation & Tests:**
   - Update `docs/status.md` scoreboard to document the unconstrained retrospective replay baseline (`100–112–3` spread, `112–102–0` total).
   - Update `docs/modeling/v5_status.md` line 71 to reflect unconstrained grading.
   - Align web test assertions.

## Scope

### Included
- Configuration files in `conf/weekly_bets/`.
- Pipeline serving and scoring scripts (`scripts/pipeline/build_v5_intended_update_serving.py`, `backfill_v5_unconstrained_grades.py`).
- Python inference package (`src/cks_picks_cfb/inference/v5_serving.py`).
- Pre-mutation snapshots and Preview rehearsal.
- Neon database updates for Weeks 0–4 predictions, market selections, grades, and system stats.
- Documentation update in `docs/status.md` and `docs/modeling/v5_status.md`.
- Web application verification and test alignment in `web/` and `tests/`.

### Excluded
- Frozen Week 5 predictions artifact (kept immutable; already has 56/56 quote selections).
- V4 historical frozen artifacts prior to 2026 (lineage remains sealed).
- Touching team stats or matchup data layers (`web/src/app/matchup/**`, etc.).
- Ratings model math (possession ratings and Ridge bridge remain completely unchanged).

## Affected Components and Contracts

- `conf/weekly_bets/v5_intended_update_2026.yaml`
- `conf/weekly_bets/v5_replay_2026.yaml`
- `conf/weekly_bets/v5_preview_2026.yaml`
- `scripts/pipeline/build_v5_intended_update_serving.py`
- `scripts/pipeline/backfill_v5_unconstrained_grades.py` (new)
- `src/cks_picks_cfb/inference/v5_serving.py`
- `docs/status.md`
- `docs/modeling/v5_status.md`

## Implementation Tasks

### Task 1 — Configs and Pipeline Serving Logic
**Files:**
- `conf/weekly_bets/v5_intended_update_2026.yaml`
- `conf/weekly_bets/v5_replay_2026.yaml`
- `conf/weekly_bets/v5_preview_2026.yaml`
- `scripts/pipeline/build_v5_intended_update_serving.py`
- `src/cks_picks_cfb/inference/v5_serving.py`

**Changes:**
- Set `spread_edge_threshold: 0.0`, `total_edge_threshold: 0.0`, and `total_lean_threshold: 0.0`.
- Remove the `scored.loc[..., "Total Bet Result"] = "No Bet"` and `Spread Bet = "No Bet"` clamping in `build_v5_intended_update_serving.py`.

**Validation:**
- Unit tests in `tests/test_weekly_inference.py` passing with threshold 0.0.

### Task 2 — Exact Backfill Script (`backfill_v5_unconstrained_grades.py`)
**Files:**
- `scripts/pipeline/backfill_v5_unconstrained_grades.py`

**Changes:**
- Create dedicated script that:
  1. Scans `predictions` and `prediction_market_selections` for Weeks 0–4 of 2026 runs (`2026w{0..4}-v5repair-20260929-p1`).
  2. Resolves line and lean for every game with `edge > 0`.
  3. Evaluates final score from `game_results` to grade as `win`, `loss`, or `push`.
  4. Supports `--dry-run` to preview insertions and tally reconciliation.
  5. Supports `--snapshot-dir` to write pre-mutation JSON dumps of `prediction_grades` and `predictions` before executing DB mutations.
  6. Inserts missing grades via `UPSERT_GRADE_SQL` (does not overwrite existing valid grades).
  7. Updates `predictions.spread_lean` / `predictions.total_lean` and `prediction_market_selections.side` where previously marked null/No Bet.
  8. Refreshes `system_stats` table in Neon via `recompute_stats`.

**Validation:**
- Dry-run verification reports exactly 16 spread grades and 55 total grades to insert, reaching 100–112–3 and 112–102–0.

### Task 3 — Preview Rehearsal, Snapshot, and Production Execution
**Files:**
- Database execution via `backfill_v5_unconstrained_grades.py`.

**Changes:**
- **Step 1 (Preview Rehearsal):** Run against `PREVIEW_DATABASE_URL`:
  `python3 scripts/pipeline/backfill_v5_unconstrained_grades.py --environment preview`
  Verify Preview readback shows 212 decided spreads and 214 decided totals.
- **Step 2 (Pre-Mutation Dump):** Export snapshot of production state to `artifacts/backups/2026-10-02/pre_unconstrained_grades_snapshot.json`.
- **Step 3 (Production Run):**
  `python3 scripts/pipeline/backfill_v5_unconstrained_grades.py --environment production --confirm-production`

**Validation:**
- Read-only SQL query verifies 0 ungraded spreads and 1 ungraded total (Houston @ Texas Tech) in production.
- `system_stats` in production verifies 100–112–3 and 112–102–0.

### Task 4 — Web Alignment, Documentation, and Tests
**Files:**
- `web/src/lib/slate.test.ts`
- `web/e2e/publication.spec.ts`
- `docs/status.md`
- `docs/modeling/v5_status.md`

**Changes:**
- Update any test assertions that expected "4–3–1" or specific subset counts on Week 4.
- Update `docs/status.md` with the new scoreboard:
  - Spread: `100–112–3` (47.2%)
  - Total: `112–102–0` (52.3%)
- Update `docs/modeling/v5_status.md` line 71 to reflect unconstrained grading.

**Validation:**
- `npm --prefix web run test:publication` (all tests pass).
- `npm --prefix web run typecheck` & `npm --prefix web run lint`.
- Browser inspection of `/results` and `/performance`.

## Testing Strategy
- Unit tests: verify `deriveSpreadView`, `deriveTotalView`, and `leanFor` with small positive edges.
- Data platform verification: SQL verification that `SELECT count(*) FROM prediction_grades WHERE season = 2026` equals $215 + 214 = 429$ grades.
- Web regression: Playwright publication suite ensuring cards and record regions render accurately.

## Risks and Edge Cases
- **Zero-Edge Ties:** In the rare case that `model == market` to the exact decimal, `lean` is null and `grade` is null (push). In continuous ratings, this occurs in 0 out of 215 games.
- **Unlined Games:** Houston @ Texas Tech (Week 3) never had a total market line posted before kickoff. It correctly remains without a total line, total lean, or total grade.
- **Audit Lineage:** Retrospective replay status is clearly marked in `docs/status.md` and on the site; Week 5 remains the first prospective live slate.

## Definition of Done
- [x] Configs set to 0.0 thresholds.
- [x] Pipeline serving builder generates unconstrained leans and grades.
- [x] `backfill_v5_unconstrained_grades.py` rehearsed cleanly on Preview.
- [x] Pre-mutation snapshot taken before production run.
- [x] All 16 spread grades and 55 total grades upserted into Neon production.
- [x] `system_stats` updated in Neon with new season totals (100–112–3, 112–102–0).
- [x] Week 5 close gate: after certified finals, the close must produce 56 spread grades and 56 total grades (minus any unlined). Terra traces whether close-week re-derives leans under threshold 0.0; if the scorer consumes frozen null leans and skips rows, extend `backfill_v5_unconstrained_grades.py` to Week 5 post-close (grades only — predictions stays untouched). Stop if close-week cannot produce full-slate grades without touching frozen predictions.
- [x] Web app renders all games with leans and grades cleanly.
- [x] Full quality gates pass (`test:publication`, `typecheck`, `lint`, `contracts-check`).
- [x] `docs/status.md` and `docs/modeling/v5_status.md` updated and session log recorded.
- [x] Plan status updated to `Implemented`.
