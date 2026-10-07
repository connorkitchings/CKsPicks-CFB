# Session: Stage 7B Preview registration and Production migrations

## TL;DR
- **Worked On:** Applied Preview legacy freeze attestation registration (`--apply`) and applied Production migrations 0023 and 0024 under explicit user authorization.
- **Outcome:** Preview attestation object written to Preview R2; Week 5 prospective record inserted and verified in Preview database with exact readback. Migrations 0023 and 0024 applied to Production database with checksum parity; schema readback confirmed empty tables and zero serving changes. Production registration dry run verified clean (exit code 0).
- **Plan Contract:** `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md`
- **Approval / Status:** In Progress. User authorized Preview apply and Production migrations separately. Production registration apply remains a separate later gate.
- **Blockers:** Production attestation apply decision; cutover week $N$ determination and fresh schedule/quote reconciliation; release packet building and authorization.
- **Next:** User authorization for Production registration apply, dynamic selection of $N$, and assembly of Preview/Production release packets.

## Context and Decisions
- Baseline commit: `458b9694` (clean worktree).
- User provided separate authorization for:
  1. Preview attestation registration with `--apply`.
  2. Production migrations 0023 and 0024.
  3. Production registration remains a separate later gate.

## Work Completed
1. **Preview Registration (`--apply`):**
   - Executed `scripts/pipeline/register_v5_legacy_freeze_attestation.py` via `scripts/ops/with_preview_env.sh` (as restricted role `cks_preview_pipeline`).
   - Wrote immutable snapshot objects and attestation JSON to Preview R2.
   - Inserted Week 5 row into `public.prospective_week_records` in Preview database.
   - Readback verified:
     - `season = 2026`, `week = 5`, `run_id = '2026w5-v5repair-20260929-p2'`
     - `freeze_receipt_uri = 'artifacts/prospective/v5/environment=preview/season=2026/week=5/2026w5-v5repair-20260929-p2/legacy-attestation-v1-9b3d04f3c72448aa712b9814a0a1aadedcc709946108d15cf1622b17452d31f6.json'`
     - `freeze_receipt_sha256 = '9b3d04f3c72448aa712b9814a0a1aadedcc709946108d15cf1622b17452d31f6'`
     - `frozen_at = '2026-09-29T20:43:53.376950+00:00'`, `first_kickoff_utc = '2026-10-02T00:00:00+00:00'`
   - Idempotent rerun confirmed zero remote writes (`Verified exact retry; zero remote writes`).
2. **Production Migrations (0023 & 0024):**
   - Executed `scripts/pipeline/migrate_db.py --database-env DATABASE_URL` connecting as `neondb_owner`.
   - Applied migrations `0023_prospective_week_records.sql` and `0024_v5_release_revocations.sql`.
   - Verified idempotent retry: `Applied migrations: none`.
   - Readback verified:
     - Checksums in `schema_migrations` match repository bytes.
     - Tables `public.prospective_week_records` and `ops.v5_release_revocations` exist and are empty (0 rows).
     - Role `cks_release_authorizer` provisioned as `NOLOGIN`.
     - Serving state unmutated (`current_week=(2026, 6)`, `site_week_selections` count=6).
3. **Production Registration Dry Run:**
   - Executed `scripts/pipeline/register_v5_legacy_freeze_attestation.py` via `scripts/ops/with_production_pipeline_env.sh` (as restricted role `cks_prod_pipeline`).
   - Verified all live Production sources, historical code SHA `acbd9c67…`, prediction manifest/artifact, schedule, and candidate generation with exit code 0 (`Verified local dry-run candidate; no R2 or database writes`).
   - No writes performed to Production prospective records.

## Files Modified
- `docs/plans/2026-10-06/02-stage7b-exact-release-and-cutover.md` — Updated with execution record.
- `session_logs/2026-10-06/12-stage7b-preview-registration-and-prod-migrations.md` — This session log.

## Validation
- [x] Preview registration apply: exit code 0; database readback verified.
- [x] Preview idempotent retry: exit code 0 (zero writes).
- [x] Production migration 0023 and 0024 apply: exit code 0.
- [x] Production migration idempotent retry: exit code 0 (none applied).
- [x] Production schema and grant readback: verified tables exist with 0 rows; serving state unchanged.
- [x] Production registration dry run: exit code 0 (`Verified local dry-run candidate; no R2 or database writes`).
- [x] `git diff --check`: passed cleanly.
- [x] `uv run mkdocs build --quiet`: passed cleanly.

## Handoff Notes
- **Resume at:**
  1. User decision to apply Production registration (`--apply`).
  2. Fresh schedule and quote capture to determine cutover week $N$ (e.g. Week 6).
  3. Assemble Preview release packet, perform Preview rehearsal, and review rollback receipts.
- **Proposed commit:** `docs(release): record Preview registration apply and Production migrations`

**tags:** ["release", "stage7b", "preview-apply", "prod-migrations", "parity"]
