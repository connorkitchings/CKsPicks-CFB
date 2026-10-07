# Session: Stage 7B Preview pipeline adjudication and dry-run verification

## TL;DR
- **Worked On:** Contract 04 Amendment 5 / Stage 7B Amendment 2 to adjudicate Preview's historical pipeline ledger gap and verify Preview registration dry-run.
- **Outcome:** Resolved the Preview evidence gap with an explicit contract amendment and codebase support. Preview dry-run `register_v5_legacy_freeze_attestation.py` through `with_preview_env.sh` (as restricted `cks_preview_pipeline`) successfully verified all live Preview sources, original code SHA `446c8805…`, prediction artifacts and schedule with code 0. Production dry-run failed closed on unapplied migration 0023 as expected.
- **Plan Contract:** `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- **Approval / Status:** In Progress. Live apply gates remain held pending explicit user decisions for Preview apply, Production migrations 0023/0024, and cutover week $N$.
- **Blockers:** Production 0023/0024 migration; explicit authorization for Preview and Production attestation apply; fresh provider quote reconciliation and dynamic $N$.
- **Next:** User authorization to apply Preview registration (`--apply`), apply Production migrations 0023/0024, and reconcile fresh schedule/quotes for cutover week $N$.

## Context and Decisions
- Investigated `ops.pipeline_runs` and `ops.activation_history` across both environments:
  - **Production:** Retains pipeline run `816d7d02c2364547bb5ad569b3113f25` (`freeze-week`, `succeeded`), step `freeze` (`succeeded`, return code 0), and freeze activation `2026w5-v5repair-20260929-p2` at 2026-09-30 12:34:06Z.
  - **Preview:** Retains freeze activation `2026w5-v5repair-20260929-p2` at 2026-09-29 20:43:53Z (`freeze_coverage_complete=true`), matching `prediction_runs` row, and selection history. However, in the Preview staging environment, the freeze was executed directly via `freeze_week.py` rather than through the `run_pipeline.py --command freeze-week` harness.
- Formulated and persisted **Contract 04 Amendment 5** and **Stage 7B Amendment 2**:
  - In Preview only, when authentic `ops.activation_history` freeze evidence, run record, and pre-kickoff selection history exist and no `freeze-week` pipeline run is present, `freeze_pipeline` is allowed to be `null` in the attestation payload.
  - Preview attestation explicitly includes: `"In Preview staging, the original Week 5 freeze was executed directly via freeze_week.py and recorded in ops.activation_history without an enclosing ops.pipeline_runs harness record."`
  - In Production, `freeze_pipeline` strictly requires the matching successful pipeline run and step.
- Executed actual live read-only dry-run using Keychain wrapper `scripts/ops/with_preview_env.sh` connecting as restricted role `cks_preview_pipeline`:
  - Output: `Verified local dry-run candidate; no R2 or database writes` (exit code 0).
  - Dry run against Production failed closed on missing 0023 schema as expected (exit code 1).

## Work Completed
- Added Contract 04 Amendment 5 in `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`.
- Added Stage 7B Amendment 2 in `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`.
- Updated `src/cks_picks_cfb/ops/prospective_records.py`:
  - `_derive_legacy_evidence`: tracks `freeze_week_pipelines` and allows `freeze_pipeline = None` in Preview only when no `freeze-week` pipeline was run.
  - `build_legacy_freeze_attestation` and `verify_legacy_freeze_attestation`: dynamically set and verify `limitations` including the Preview pipeline disclosure.
- Updated `tests/test_v5_legacy_freeze_attestation.py` to cover Preview null pipeline with disclosure and Production fail-closed behavior.

## Files Modified
- `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`
- `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- `src/cks_picks_cfb/ops/prospective_records.py`
- `tests/test_v5_legacy_freeze_attestation.py`
- `session_logs/2026-10-06/11-stage7b-preview-pipeline-adjudication.md` (this file)

## Validation
- [x] Focused pytest: 12 passed in `tests/test_v5_legacy_freeze_attestation.py`.
- [x] Batch selection tests: 5 passed, 2 skipped in `tests/test_v5_batch_selection_v2.py`.
- [x] Full Ruff linting: passed.
- [x] Contracts validation: `uv run python contracts/validation.py` passed.
- [x] Web publication suite: 133 of 133 passed (`npm --prefix web run test:publication`).
- [x] Web TypeScript and ESLint: `npm --prefix web run typecheck && npm --prefix web run lint` passed.
- [x] MkDocs build: `uv run mkdocs build --quiet` passed with 0 errors.
- [x] Git diff check: `git diff --check` passed cleanly.
- [x] Preview read-only dry run: verified live sources and candidate generation as `cks_preview_pipeline` with code 0.
- [x] Production read-only dry run: verified fail-closed on missing schema with code 1.

## Handoff Notes
- **Resume at:**
  1. User authorization to apply Preview registration (`--apply`).
  2. Apply Production migrations 0023 and 0024 under operator identity (`neondb_owner`).
  3. Run Production registration dry run, then apply upon approval.
  4. Capture fresh 2026 FBS schedule and quotes to determine cutover week $N$.
  5. Assemble Preview and Production release packets.
- **Proposed commit:** `feat(release): adjudicate Preview legacy freeze pipeline and verify dry-run`

**tags:** ["release", "stage7b", "preview", "attestation", "amendment5"]
