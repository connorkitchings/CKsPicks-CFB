# Session: Preview Readiness Repair — Implementation

## TL;DR
- **Worked On:** Executed the approved Preview readiness repair contract
  end-to-end: applied migrations `0006` + `0007` to `preview-2026`, validated,
  reran readiness, published + froze the active v2 Week 0 preview run, and ran
  a private v3 rehearsal with a v2-v3 comparison CSV.
- **Outcome:** Preview operational state is unblocked. Active run
  `2026w0-a0edb9e72cb1` is frozen with 8/8 games predicted and lined;
  `current_week.active_run_id` set. Comparison shows 2 spread-lean and 7
  total-lean changes v2→v3 (0 high-confidence eligible either way).
- **Plan Contract:** `docs/plans/2026-08-16/preview-readiness-repair.md`
  (status now `Implemented`)
- **Approval / Status:** User approved scope (v2 active + private v3
  rehearsal; attempt talent re-capture with fallback).
- **Blockers:** External — CFBD `talent` feed returned 0 records on re-capture;
  `prior_only_fallback` retained (display-only, 2 imputer rows).
  `CFBD_PREDICTION_TOKEN` not configured (Pick'em submission out of scope).

**tags:** ["pipeline", "preview", "migrations", "readiness", "week0", "games-ordinal"]

## Context and Decisions
- `preview-2026` tables were owned by `neondb_owner`, but migrations run as
  `cks_preview_migrator`. Fixed via temporary `GRANT cks_preview_migrator TO
  neondb_owner` → `ALTER TABLE ... OWNER TO cks_preview_migrator` for all
  catalog/ops/public tables + 3 sequences → `REVOKE`
  (`/var/folders/.../opencode/transfer_ownership.sql`).
- The private v3 rehearsal used the active run's immutable input refs
  (`artifacts/preview/pipeline-runs/a0edb9e72cb14ccbb12bedb8545a33e3/input_refs.json`),
  uploaded the artifact under run_id `2026w0-private-v3-rehearsal`, and did
  NOT activate in the DB (no `prediction_runs` row for it).
- v3 predictions produced sklearn divide-by-zero/overflow warnings in one
  linear route, but all 8 outputs are finite; recorded for follow-up.

## Work Completed
1. Applied migrations `0006` + `0007` to `preview-2026` (after ownership
   transfer); verified `schema_migrations` = `0002`–`0007`, lease and
   `definition_sha` columns on `ops.pipeline_runs`/`ops.pipeline_steps`, and
   `predictions_regime_check` accepts `game_1/2/3/established`.
2. Validation passed: `make contracts-check`; `tests/test_migration_integration.py`
   (2 passed, temp postgres:16-alpine, container removed); `uv run ruff check .`;
   `git diff --check`; `uv run mkdocs build --quiet`.
3. Talent re-capture: `ingest_preseason.py --sources talent` → 0 rows; external
   blocker recorded; `prior_only_fallback` retained.
4. Readiness passed all 3 steps (pipeline_run_id `adb97cec28ef4057b1331e7047e0109e`;
   audit `passed=true`, ref `point_in_time_matchups` version `74ffdbbff759459734a73e30`).
5. Published v2 run `2026w0-a0edb9e72cb1` (pipeline `a0edb9e72cb14ccbb12bedb8545a33e3`):
   8/8 spread lines, 8/8 totals, 0 high-confidence; `market_snapshots` = 8;
   durable R2 artifact + input/market refs under
   `artifacts/preview/pipeline-runs/a0edb9e72cb14ccbb12bedb8545a33e3/`.
6. Froze the run (pipeline `ef8b07519b0a4f0f8f2b2e94e5c96337`): state=`frozen`,
   8 expected/predicted/lined; `current_week` = `(2026, 0, 2026w0-a0edb9e72cb1)`.
7. Private v3 rehearsal generated 8 predictions
   (`artifacts/preview/predictions/year=2026/week=0/run_id=2026w0-private-v3-rehearsal/`),
   no DB activation. Comparison emitted to
   `artifacts/preview/comparisons/v2_vs_v3_week0_20260816.csv`.

### v2-v3 Week 0 comparison summary
- Spread lean changes: 2 (NC State @ Virginia, New Mexico State @ Florida State)
- Total lean changes: 7 (all but NC State @ Virginia)
- Spread deltas range −4.62 to +6.87; total deltas −16.33 to +7.95
- 0 high-confidence-eligible in either bundle
- v3 spread route label: `game_1` (all 8 games, week 0)

## Files Modified
- `docs/plans/2026-08-16/preview-readiness-repair.md` - Status → `Implemented`;
  DoD checkboxes marked.
- `session_logs/2026-08-16/01-preview-readiness-repair.md` - Added
  implementation record (this section).
- (untracked, user-owned) `artifacts/preview/` - v3 rehearsal run + comparison CSV.

## Validation
- [x] `zsh scripts/ops/with_preview_env.sh make migrate-db` → schema_migrations 0002–0007
- [x] `make contracts-check`
- [x] `uv run pytest -q tests/test_migration_integration.py` (2 passed)
- [x] `uv run ruff check .`
- [x] `uv run mkdocs build --quiet`
- [x] `git diff --check`
- [x] Readiness (preflight/contracts/audit_data) all succeeded
- [x] DB row-level: predictions 8, market_snapshots 8, run frozen, active_run_id set
- [x] v3 rehearsal: no `prediction_runs` row → private confirmed

## Amendments and Blockers
- None (contract executed as written). External blockers: CFBD `talent` empty;
  `CFBD_PREDICTION_TOKEN` unset.

## Handoff Notes
- **Resume at:** User activation decision on the v2 vs v3 comparison CSV
  (`artifacts/preview/comparisons/v2_vs_v3_week0_20260816.csv`). If v3 is
  chosen, an activation plan is required (private → promote routes → publish).
- **Watch out for:** v3 linear-route sklearn overflow warnings (investigate
  prior to any v3 activation); `market_quotes`/`market_snapshot_quotes` are
  intentionally empty (quotes live in immutable R2 refs); production remains
  untouched.

**tags:** ["pipeline", "preview", "migrations", "readiness", "week0", "games-ordinal"]
