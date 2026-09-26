# V5 Best-Quote Replacement: Production Release

- **Status:** Implemented (2026-09-26)
- **Created:** 2026-09-26
- **Planner:** Sol (plan-session)
- **Approval source:** User approved scope and execution on 2026-09-26 ("Write contract + execute now"): all five weeks, no live production rollback drill, decision ref `v5-bestquote-replacement-review-2026-09-26`.
- **Release decision (Step 4):** User approved all five weeks ("proceed with all", 2026-09-26).
- **Execution record:** Session log `session_logs/2026-09-26/02-v5-bestquote-production-release.md`. Authorization IDs `v5-bestquote-2026w{0..4}-{c48bf913,bc021cfb,05bba834,9074cec0,ce9c7bc0}`. W0–3 published/scored/selected with 281 grades (15/80/87/99); W4 published/selected 58/58, unscored (0 certified finals). Public health confirmed the W4 replacement active; V4 and original replay runs untouched.
- **Parent contract:** `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md` (In Progress; Task 6 production half).
- **Implementation log:** `session_logs/2026-09-26/02-v5-bestquote-production-release.md`
- **Commit policy:** Production mutations (Steps 1, 5, 6) are authorized by this contract. The user executes all git operations. Step 4 is a hard stop: no production Neon selection/grade mutation without the explicit Step 4 release decision.

## Goal

Replace the public 2026 Weeks 0–4 market lines with best executable
pre-kickoff quotes (`model_side_best_quote_v1`) via new, immutable,
separately authorized replay runs. V4 runs and the original V5 replay runs
stay frozen/scored as audit records and rollback targets. Week 4 is
published and selected but unscored (0 certified finals); its scoring waits
at its own finals gate.

Observable success criteria:

1. Every replaced week selects a distinct replacement run whose forecasts
   are byte-identical to the currently selected run and whose every served
   line is a real market tick bound to a frozen quote.
2. Grades exist only for above-threshold targets (all spreads; totals at
   edge ≥ 1.5) and settle at the exact selected quote and price.
3. No existing artifact, prediction row, grade, or prior authorization is
   modified; every production authorization is an explicit new row.
4. The public site serves the replacements only after a verified production
   readback, and restoration to the original runs is a single recorded
   selection per week.

## Current State

- The Preview rehearsal is complete (Amendment 3 of the parent contract):
  replacement batch `2026w{0..4}-v5replay-bestquote-20260926-r2` verified —
  refs bound to the graded V4 corpora, forecasts identical to the selected
  runs, selections bound to frozen quotes, threshold-aware grades, serving
  selection and rollback drill proven on Preview.
- Production: migration 0015 latest, `v5_release_policy` id=1 seeded, five
  original replay authorizations, selections on the original replay runs,
  V4 frozen/scored. The `-r2` manifests carry inline `input_dataset_refs`
  (snapshot + quote datasets), so production publish persists
  quotes/snapshots/selections directly.
- Production W4 certified finals: 0.
- Admin credential for production migration/authorization: the
  `neondb_owner` URL (`DATABASE_URL_UNPOOLED`); pipeline mutations use the
  restricted `cks_prod_pipeline` role via
  `scripts/ops/with_production_pipeline_env.sh`.

## Implementation Tasks

### Step 1 — Apply migration 0016 to production

Run `scripts/pipeline/migrate_db.py` with the admin URL (checksum-enforced,
idempotent). Read back: `schema_migrations` latest = 0016, `to_regclass`
for `prediction_market_selections`, `has_table_privilege` for
`cks_prod_pipeline` (SELECT, INSERT) and the production web role (SELECT),
`prediction_grades.market_quote_id` column. Stop on any mismatch.

### Step 2 — Build the production release driver

New `scripts/pipeline/release_v5_bestquote_replacement_production.py` with
subcommands: `prepare` (copy the `-r2` artifacts preview → production
namespace with production `artifact_uri`/`feature_snapshot_uri` only;
SHA receipts), `packet` (emit the five authorization-record JSONs from the
production manifests with the locked `decision_ref`), `score` (the rehearsed
threshold-aware scorer for Weeks 0–3), `verify` (the full rehearsed suite:
forecast equality vs the currently selected originals, selections, grades,
market-tick lines, idempotency bounds). Focused unit tests for the
manifest-rewrite and packet builder; scoped pytest + ruff before use.

### Step 3 — Prepare candidates and validate packets (no Neon writes)

Run `prepare` (R2 writes only, production namespace). Run `packet`, then
`validate_v5_release_packet.py --kind replay` per week against the
production manifests; require `{"valid": true}` × 5. Read back production
preconditions (V4 intact, originals selected, 0016 applied, W4 finals
count). **This step ends the authorized execution. Do not proceed to
production Neon writes.**

### Step 4 — Release decision (user gate; hard stop)

Present the five validated packets. The user approves all five (locked
scope), a subset, or defers. No authorization insert, publish, score, or
selection before this explicit decision for the exact approved rows.

### Step 5 — Insert authorizations (admin only)

Under `neondb_owner`, insert exactly the validated, approved rows into
`v5_replay_release_authorizations` and no others. Read back the rows and
prove `cks_prod_pipeline` SELECT access.

### Step 6 — Publish, score, select (pipeline role)

Per approved week, W0→W3 then W4, via `with_production_pipeline_env.sh`:
`publish_to_db.py --from-artifact --run-id … --no-update-current --state
published` → publication invariants → driver `score` (W0–3 only; expect
281 total grades: 157 spread + 124 total; reject on deviation) → driver
`verify` → `select_public_run.py --reason "best-quote replacement release
v5-bestquote-replacement-review-2026-09-26"`. W4 is published and selected
only. `system_stats` recomputes are derived-only; the site computes records
live from selected grades (documented, never hand-forged).

### Step 7 — Production readback, health, rollback proof

`site_week_selections` on the five replacement runs; public health;
served-line market-tick proof via SQL; per-week W-L-P. Original V5 replay
runs and V4 runs verified untouched (states and grade counts). Rollback
path: re-select an original run via `select_public_run` (documented
commands; no live drill per the locked decision).

### Step 8 — Close-out

Amend the parent contract (Amendment 4), mark its Task 6 DoD Implemented,
refresh `docs/modeling/v5_status.md`, write the session log, and propose a
commit message. W4 replacement scoring resumes at its own finals gate; the
Week 5 live lane takes precedence at any atomic checkpoint (plan-02 stop
condition carries over).

## Validation

- `scripts/pipeline/migrate_db.py` checksum pass + privilege readback (Step 1).
- Scoped `pytest`, `uv run ruff check .`, `make contracts-check` (Step 2).
- `{"valid": true}` for all five replay packets + precondition readback (Step 3).
- Per-run coverage/forecast/selection/grade verifier output, V4 + originals
  intact, health endpoint, market-tick proof (Steps 6–7).
- `mkdocs build --strict --quiet`, `git diff --check` (Step 8).

## Risks and Edge Cases

- The authorization unique key `(environment, season, week, prediction_run_id)`
  accepts the five new rows; reusing these packets for any other run, week,
  or environment is forbidden — the validator and `require_replay_release_record`
  fail closed on mismatch.
- Selecting W4 while its finals are absent is display-only by design; the
  scorer must remain unable to score it until the finals gate.
- Immutability: `frozen`/`scored` runs refuse re-publish; scored weeks repeat
  only the score call (verified no-drift on Preview).
- Never select the unsuffixed `-20260926` Preview debris batch; it exists only
  on Preview and fails every environment check by construction.
- If the Week 5 live lane's stabilized-finals gate opens mid-execution, pause
  at the nearest atomic checkpoint and prioritize the live lane.

## Definition of Done

- [x] Migration 0016 applied on production with privilege readback.
- [x] Five production candidate artifacts prepared; five packets validate.
- [x] User release decision recorded with the exact approved rows (all five).
- [x] Authorizations inserted by admin; publish/score/select executed per week.
- [x] Production readback (lines, grades, health, rollback targets intact).
- [x] Parent contract Amendment 4 + Task 6 DoD Implemented; docs and log updated.
