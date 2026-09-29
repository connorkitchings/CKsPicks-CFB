# Session: Migration target incident and Preview recovery

## TL;DR
- **Worked On:** Reviewed the accidental production 0018 migration and fixed the unsafe migration entry point.
- **Outcome:** Left production's checksum-valid additive 0018 migration intact. Disabled the ambiguous Make target, required an explicit target in the CLI, and applied 0018 to the independently verified Preview branch.
- **Plan Contract:** `docs/plans/2026-09-29/v5-intended-update-2026-production-repair.md` (Task 6, in progress).
- **Approval / Status:** Preview rehearsal was already authorized; no production rollback, authorization, or selection was performed.
- **Blockers:** Full Preview rehearsal and release packets remain open. The new authorization gate must be committed before the R2 `--apply` chain can run.
- **Next:** Commit the migration and Preview authorization fixes, publish the immutable R2 chain, then rehearse Preview publication, selection, rollback, and reactivation before preparing production packets.

## Context and Decisions
- Independent read-only production checks confirmed 0018's ledger checksum matches the committed SQL. The two new tables contain one backfilled legacy approval and zero successor authorizations. Selected Weeks 0–5 still match the source lock; no grades or statistics were changed by 0018.
- Dropping the additive tables and deleting the checksum ledger would introduce another production mutation without restoring user-visible state. We did not do it.
- `make migrate-db ENV=preview` ignored `ENV` and silently used `DATABASE_URL`. It now fails closed. The CLI requires `--database-url` or `--database-env`; the Preview command uses its Keychain wrapper and explicitly selects the wrapper's migration-role `DATABASE_URL`.
- A read-only preflight showed the Preview migration URL is on a different host from the production URL, connects as `cks_preview_migrator`, lacks 0018, and has the expected Preview Week 0 selection.

## Work Completed
- Updated migration CLI and current operator documentation; added target-selection regression tests.
- Applied migration 0018 to Preview only. Read-only verification found its exact committed checksum, one legacy approval, and zero successor authorizations.
- Required exact environment-scoped successor authorization on both Preview and production publication and selection paths. Preview records must pass the same immutable-artifact validation as production records.

## Files Modified
- `Makefile`, `scripts/pipeline/migrate_db.py`, `tests/test_migrations.py` — fail-closed migration entry points and tests.
- `.codex/QUICKSTART.md`, `AGENTS.md`, `contracts/README.md`, `docs/ops/weekly_pipeline.md`, `web/README.md` — corrected commands and target expectations.
- `src/cks_picks_cfb/ops/v5_intended_update_release.py`, `src/cks_picks_cfb/ops/public_selection.py`, `scripts/pipeline/publish_to_db.py`, `tests/test_public_selection.py` — environment-scoped release gate and regression tests.

## Validation
- [x] `make migrate-db ENV=preview` fails before database access.
- [x] CLI without an explicit target fails before database access.
- [x] Migration, public selection, and publication tests: 68 passed.
- [x] Ruff format and lint for changed Python files; `git diff --check`.
- [ ] `mkdocs build --strict` still fails on existing links outside the docs tree; no new warning from these edits.
- [ ] Full Preview rehearsal and production release packets.

## Amendments and Blockers
- Production 0018 was applied early by the separate session. The ledger should remain intact; a later production migration run will checksum-match and skip it.
- Preview now checks exact successor authorization, but no successor approval or run authorizations have been inserted yet. The complete rehearsal is still pending.

## Handoff Notes
- **Resume at:** User-executed commit of the current changes, then the immutable R2 `--apply` chain and Preview rehearsal in Task 6.
- **Watch out for:** Do not run `make migrate-db`; do not perform production selection or authorization before an exact packet decision.

**tags:** ["database", "migration", "preview", "v5", "incident"]
