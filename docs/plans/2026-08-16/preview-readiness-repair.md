# Preview Readiness Repair

- **Status:** Implemented (2026-08-16)
- **Created:** 2026-08-16
- **Planner:** Sol
- **Approval source:** User approved in session on 2026-08-16 (including the
  scope answers: v2 active + private v3 rehearsal; attempt talent re-capture
  with fallback).
- **Implementation log:** `session_logs/2026-08-16/01-preview-readiness-repair.md`
- **Commit policy:** Separate plan commit; implementation commits remain
  user-controlled.

## Goal

Unblock the Preview operational state so the weekly pipeline
(`readiness` → `publish-week` → `freeze-week`) runs end-to-end on the
`preview-2026` Neon branch, restore a valid active Week 0 preview run, and
produce a private v2-v3 comparison CSV. Production, public fail-closed
`market` mode, promotion gates, and Pick'em submission remain untouched.

## Current State

- `preview-2026` Neon branch has migrations `0002`–`0005` applied only.
- The committed hardened pipeline requires migration `0006` (definition SHA
  and lease columns on `ops.pipeline_runs` / `ops.pipeline_steps`) and `0007`
  (`game_1`, `game_2`, `game_3`, `established` regime values).
- Verified failure: `make readiness` dies with
  `psycopg.errors.UndefinedColumn: column "definition_sha" does not exist`.
- `current_week` is the seeded empty singleton (`0|0|`, no `active_run_id`);
  `prediction_runs`, `market_snapshots`, and `market_quotes` are empty.
- Preflight alone passes with the expected `prior_only_fallback` WARN (2 rows
  requiring the frozen model imputer; display-only). Catalog is hydrated with
  77 `dataset_versions` covering all required Silver/Gold refs.
- The 2026-08-14 preseason snapshot in preview R2 covers 4 of 5 required
  sources; `talent` is missing (CFBD feed empty, external).
- Two weekly configs exist: `v2_preview_2026.yaml` (active/public-facing) and
  `v3_preview_games_ordinal_2026.yaml` (private comparison, 8-route
  games-ordinal bundle).

## Proposed Approach

1. Apply migrations `0006` + `0007` to `preview-2026` through the preview
   wrapper so the lease-fenced state machine can run.
2. Validate the schema (contracts check, migration integration tests, Ruff).
3. Attempt the preseason `talent` re-capture; if CFBD is still empty, keep the
   documented `prior_only_fallback` path and record the external blocker.
4. Rerun the full `readiness` gate (preflight + contracts + model-ready
   audit) against the v2 preview config.
5. Publish and freeze a fresh active v2 Week 0 preview run, setting
   `current_week.active_run_id`.
6. Run a private v3 rehearsal (prediction generation with the v3 bundle and
   the 2026-08-16 snapshot refs, no DB activation) and emit the v2-v3
   comparison CSV for the user's activation decision.

## Scope

### Included

- Applying existing migrations `0006` and `0007` to the preview-2026 branch.
- Re-capturing preseason `talent` (non-destructive; fallback preserved).
- Running preview readiness, publish, freeze, and the private v3 rehearsal.
- Documentation updates and session logs.

### Excluded

- Production migrations, publication, or deployment.
- Changing the public `market`-mode web configuration or enabling
  `predictions` mode.
- Promoting routes to high confidence.
- Pick'em submission (`CFBD_PREDICTION_TOKEN` still required).
- Paid The Odds API backfill requests.
- Any commit or push (user-controlled).

## Affected Components and Contracts

- `preview-2026` Neon schema (migrations `0006` + `0007`).
- Preview weekly operational state (`current_week`, `prediction_runs`,
  `market_snapshots`, `market_quotes`).
- Preview R2 preseason snapshot (optional `talent` source).
- Private comparison artifact under `artifacts/preview/`.

## Implementation Tasks

### Task 1 — Apply migrations to preview-2026

**Changes:**
- Run `zsh scripts/ops/with_preview_env.sh make migrate-db`.
- Verify `schema_migrations` shows `0002`–`0007`, lease/`definition_sha`
  columns exist on `ops.pipeline_runs` / `ops.pipeline_steps`, and the
  `predictions_regime_check` constraint accepts `game_1/2/3/established`.

**Acceptance criteria:**
- `make readiness` no longer fails on `definition_sha`.

### Task 2 — Validate schema

**Changes:**
- `make contracts-check`.
- `uv run pytest -q tests/test_migration_integration.py` (fresh + synthetic
  pre-hardening upgrade paths).
- `uv run ruff check .` on changed files; `git diff --check`.

**Acceptance criteria:**
- All validation passes.

### Task 3 — Attempt preseason talent re-capture

**Changes:**
- `PYTHONPATH=.:src uv run python scripts/data/ingest_preseason.py
  --year 2026 --as-of 2026-08-16 --sources talent`.
- If CFBD returns data, confirm `snapshot_is_complete`; otherwise retain the
  `prior_only_fallback` path already configured in the v2 config and record
  the external blocker.

**Acceptance criteria:**
- The preseason snapshot is either complete or explicitly documented as
  display-only fallback (unchanged behavior).

### Task 4 — Rerun readiness

**Changes:**
- `zsh scripts/ops/with_preview_env.sh make readiness YEAR=2026 WEEK=0
  AS_OF=<current ISO> ENV=preview CONFIG=conf/weekly_bets/v2_preview_2026.yaml`.

**Acceptance criteria:**
- All three steps (preflight, contracts, model-ready audit) pass.

### Task 5 — Publish and freeze active v2 run

**Changes:**
- `zsh scripts/ops/with_preview_env.sh make publish-week YEAR=2026 WEEK=0
  AS_OF=<current ISO> ENV=preview CONFIG=conf/weekly_bets/v2_preview_2026.yaml`.
- `zsh scripts/ops/with_preview_env.sh make freeze-week YEAR=2026 WEEK=0
  ENV=preview`.
- Verify `current_week.active_run_id`, 8 distinct predictions with spread and
  total, populated market snapshots/quotes, and the durable R2 prediction
  artifact.

**Acceptance criteria:**
- A frozen preview run is the active run and is queryable.

### Task 6 — Private v3 rehearsal and comparison

**Changes:**
- Generate v3 predictions with
  `conf/weekly_bets/v3_preview_games_ordinal_2026.yaml` against the 2026-08-16
  input snapshot refs, uploading the artifact without DB activation.
- Run `scripts/pipeline/compare_preview_model_bundles.py` to emit
  `artifacts/preview/comparisons/v2_vs_v3_week0_<date>.csv`.
- Present the deltas for the user's activation decision.

**Acceptance criteria:**
- Comparison CSV produced; no v3 run activated in the database.

### Task 7 — Verify and document

**Changes:**
- Verify row-level invariants and artifact paths.
- Update `docs/ops/weekly_pipeline.md` if the repair reveals an operational
  gap.
- Create `session_logs/2026-08-16/01-preview-readiness-repair.md`.
- Mark the plan `Implemented`.

**Acceptance criteria:**
- Full-cycle verification recorded; plan status reflects completion.

## Testing Strategy

- Migration integration tests (fresh and upgrade paths).
- Contracts validation.
- Preview preflight + model-ready audit.
- DB row-level invariant queries.
- Ruff, MkDocs, `git diff --check`.

## Risks and Edge Cases

- Migrations are checksummed; a changed checksum fails loudly.
- The lease-fenced state machine requires the 0006 columns; do not run
  `publish-week` before the migration is verified.
- Preseason `talent` may remain empty (external); fallback keeps Week 0
  display-only with imputer rows.
- `artifacts/preview/` is user-owned and must remain unmodified/unstaged.
- No production side effects.

## Definition of Done

- [x] Migrations `0002`–`0007` applied to preview-2026 and verified.
- [x] Schema validation passes.
- [x] Readiness passes all steps.
- [x] Active v2 Week 0 preview run published and frozen with
  `current_week.active_run_id` set.
- [x] Private v3 rehearsal + comparison CSV produced.
- [x] Full-cycle verification and session log complete.
- [x] Plan status updated to `Implemented`.

## Amendments

None.
