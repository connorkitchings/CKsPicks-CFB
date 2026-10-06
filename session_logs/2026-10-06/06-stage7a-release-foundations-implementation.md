# Session: Stage 7A Release Foundations implementation

## TL;DR
- **Worked On:** Implemented the approved Stage 7A schema, revocation guards, freeze/auth tooling, v2 selection controller, web read-path changes, and executed the authorized Preview migration and readback.
- **Outcome:** Local implementation, fixture/browser validation, migration upgrade tests, and database-backed v2 transaction tests are in place. Migrations 0023 and 0024 applied to Preview and verified read-only (zero data/serving writes). Stage 7A is Implemented.
- **Plan Contract:** `docs/plans/2026-10-06/01-stage7a-release-foundations.md`
- **Approval / Status:** User authorized implementation and the Preview migration. Stage 7A is Implemented.
- **Blockers:** None for Stage 7A. Stage 7B (Exact Release and Cutover) is a separate gate.
- **Next:** Handoff to Stage 7B planning and execution.

## Context and Decisions
- Work is on `dev`, starting from clean HEAD `63a62b6063e57d6d12614ad6a9321ad8779fff83`; the approved Stage 7A code baseline is Stage 6B close-out `320436f1d13b38068b9e21a2ea64d41a755c1551`.
- The migration chain ends at 0022. The correct registries are `public.v5_model_bundle_approvals` and `public.v5_intended_update_release_authorizations`.
- Exact known operator identities used by the guarded tools are Preview `cks_preview_migrator` and Production `neondb_owner`; the restricted pipeline identities remain separate. The NOLOGIN role membership helper is user-run and was not executed.
- No serving, current-week, selection, freeze, authorization, or revocation rows were changed. No git staging or commit was performed.

## Work Completed
- Added migrations 0023/0024, prospective-week trigger protections, append-only revocations, the NOLOGIN authorizer role, and synchronized canonical Python/TypeScript/SQL schema definitions. Extended contract validation for table synchronization.
- Added deterministic transaction advisory locks and revocation checks to public selection, exact successor authorization, the direct freeze path, and the v2 controller. The descriptor-driven weekly-cycle freeze now requires a decision reference and binds it into preflight/apply evidence. Added signed prospective freeze receipt handling and guarded user-run authorization, revocation, and role-membership tools.
- Added v2 signed packet verification, exact before/after bindings, contiguous replay/pending coverage, authorization and certification revalidation, fixed-order transaction locks, prospective-record preservation, stats/current-week readback, dry-run, retry, and rollback paths. Existing v1 batch path remains intact.
- Split selected replay and designated prospective Performance queries. Added class labels, separate status states, original run/receipt provenance, and push-excluding W-L-P rates. Added a fail-closed matchup lineage state that hides model-derived details and disables share controls when provenance is missing or mismatched.
- Added focused Python regressions, migration integration coverage, lineage unit tests, fixture cases, and Performance/matchup Playwright assertions.
- The real PostgreSQL run caught and repaired two migration-test assumptions: prospective Week 5+ scope now fails before run identity checks, and role-level UPDATE denial is tested separately from the table-owner append-only trigger.
- Added database-backed v2 coverage for read-only preflight, atomic selection of Weeks 0–5, idempotent retry without duplicate history, a failure after several selection writes, a failure after selection/team-stat/current-week writes, compensating rollback, and a real advisory-lock wait between selection and revocation. The focused suite passed 49 tests against the disposable cluster; the controller test stubs external authorization/finals proof reads and the exact database login guard.

## Files Modified
- `contracts/migrations/0023_prospective_week_records.sql`, `contracts/migrations/0024_v5_release_revocations.sql`, `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`, `contracts/validation.py` - schema and synchronization.
- `src/cks_picks_cfb/ops/{public_selection.py,v5_intended_update_release.py,v5_revocations.py,v5_freeze_guard.py,prospective_records.py,v5_batch_selection_v2.py}` - transaction guards and controller.
- `scripts/pipeline/{freeze_week.py,select_v5_intended_update_batch.py,authorize_v5_intended_update_preview.py,authorize_v5_intended_update_batch.py,authorize_v5_intended_update_production.py,revoke_v5_release.py,grant_v5_release_authorizer.py}` - guarded operator/pipeline entrypoints.
- `tests/test_migration_integration.py`, `tests/test_public_selection.py`, `tests/test_v5_batch_selection_v2.py`, `tests/test_v5_batch_authorization.py`, `tests/test_v5_revocations.py` - Python regressions.
- `web/src/lib/{v5.ts,matchup.ts,matchup-lineage.ts,matchup-lineage.test.ts,row-guard.ts,row-guard.test.ts}`, Performance/matchup components, fixtures, and `web/e2e/{performance.spec.ts,matchup.spec.ts}` - web read paths and tests.
- `docs/plans/2026-10-06/01-stage7a-release-foundations.md` - execution evidence and remaining gates.

## Validation
- [x] Focused Stage 7A Python tests: 40 passed, 7 PostgreSQL-dependent tests skipped.
- [x] Disposable PostgreSQL migration and controller integration: combined focused Stage 7A suite with database configured: 49 passed.
- [x] Full Python suite: 2,017 passed, 12 skipped in 292.35 seconds.
- [x] Ruff, direct `contracts/validation.py`, MkDocs, and `git diff --check` passed.
- [x] Web lint, typecheck, 131 publication tests, production build, and 24 Performance/matchup Playwright tests passed.
- [x] Preview migration and read-only identity/grant/schema/query readback: applied 0023 and 0024 via `migrate_db.py`, verified idempotence, confirmed effective role matrix, confirmed 0 rows, and verified query compatibility with zero serving writes.

## Amendments and Blockers
- No plan amendment. `make contracts-check` could not run through `uv`: the configured cache first returned a filesystem permission error; a writable-cache retry hit a local uv runtime panic. Its underlying `contracts/validation.py` command passed directly.
- PostgreSQL migration, logical 0022 upgrade, trigger, basic role-grant, controller transaction, rollback, and advisory-lock serialization checks passed against a temporary UTF-8 cluster.
- Stage 7A is Implemented.

## Handoff Notes
- **Resume at:** Handoff to Stage 7B: determine concrete cutover week $N$, assemble the release packet, and execute the atomic cutover and rollback rehearsal.
- **Watch out for:** Never run the production migration or live production activation without a separate explicit decision.

**tags:** ["release", "schema", "authorization", "web"]
