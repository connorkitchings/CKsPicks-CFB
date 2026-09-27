# Session: Ratings Lifecycle Migration Rollout

## TL;DR

- **Worked On:** Applied committed migration 0017 to Preview, verified it, then applied it to production.
- **Outcome:** Both Neon branches enforce non-null rating manifest provenance for V5 prediction runs. Existing V4 rollback runs remain valid under the V5-only constraint.
- **Plan Contract:** `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` (Implemented); this is a separately authorized operational rollout after implementation commit `83607c2`.
- **Approval / Status:** User explicitly requested: “Apply migration 0017 to Preview, verify it, then apply it to production.”
- **Blockers:** None.
- **Next:** Continue the normal weekly operating cadence; prospective Week 5 production activation remains a separate exact release decision.

## Context and Decisions

- The earlier “continue” request was rejected by automatic approval review because the implementation plan excluded live migrations. No database mutation occurred on that attempt. The user then gave the exact Preview-then-production migration authorization above.
- The production `.env` owner/migration credential was read-only matched to the restricted production pipeline connection using the same 68-run fingerprint before use. The Preview Keychain wrapper supplied its branch-scoped migrator credential.
- The append-only migration runner committed only 0017 on each branch. No prediction row, rating snapshot, selection, or publication was modified by the operator.

## Work Completed

1. Confirmed commit `83607c2` contains migration 0017 and the worktree had only unrelated archive files untracked.
2. Preview preflight: schema version 0016; 21 V5 prediction rows, zero missing rating SHA. Applied 0017 through `with_preview_env.sh make migrate-db`.
3. Preview verification: migration ledger checksum matches committed 0017 SQL; named CHECK constraint is present and validated; 21 V5 rows, zero missing SHA.
4. Production preflight: schema version 0016; 16 V5 prediction rows, zero missing rating SHA. Applied 0017 with the production owner/migration credential after read-only branch identity comparison.
5. Production verification: migration ledger checksum matches committed SQL; the same CHECK constraint is present and validated; 16 V5 rows, zero missing SHA.

## Files Modified

- `docs/ops/production_runbook.md` — current production migration level.
- `docs/plans/index.md` — current contract rollout state.
- `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` — separately authorized rollout record.
- `session_logs/2026-09-27/11-ratings-lifecycle-migration-rollout.md` — this log.

## Validation

- [x] Preview and production pre-application null-SHA audits: 0 missing.
- [x] Preview and production schema migration ledger version `0017` with matching SQL checksum.
- [x] Preview and production `chk_prediction_runs_rating_manifest_required` is present and `convalidated = true`.
- [x] Preview and production post-application null-SHA audits: 0 missing.
- [x] Documentation build and `git diff --check` after log updates.

## Amendments and Blockers

The rollout is a separate user-authorized operation. It does not change the implemented contract's V5-only scope or authorize prospective publication. No blockers remain.

## Handoff Notes

- **Resume at:** Follow the [production runbook](../../docs/ops/production_runbook.md) and the exact release process for any prospective Week 5 decision.
- **Watch out for:** The constraint applies to V5 `prediction_runs` and permits V4 rows without rating provenance; no public selection was made in this rollout.
- **Suggested commit message:** `docs: record ratings provenance migration rollout`

**tags:** ["ops", "migration", "ratings", "preview", "production"]
