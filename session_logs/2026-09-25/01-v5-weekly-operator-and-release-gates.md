# Session: V5 weekly operator and release gates

## TL;DR

- **Worked On:** Began Terra implementation of the approved manual V5 weekly operator and exact release gates.
- **Outcome:** Core code, append-only migration 0014, focused tests, and operating docs were added. Work stopped at a material production-role conflict; the plan remains In Progress.
- **Plan Contract:** `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` (In Progress).
- **Approval / Status:** User explicitly authorized this exact plan path. Git operations remain user-controlled. No production V5 activation was authorized.
- **Blockers:** The configured production `DATABASE_URL` uses `neondb_owner`, while the plan requires a restricted pipeline role with SELECT-only access to exact authorization rows. An owner connection defeats that database permission boundary. Renewed Sol design review is required before implementation resumes.
- **Next:** Decide how to enforce the admin/pipeline separation, preferably by provisioning a dedicated production pipeline role and switching V5 publisher/ops connections to it. Reconcile this worktree with the revised contract, then complete and validate the implementation.

## Context and Decisions

- V5 replay and Preview rollback remain complete; V4 still serves production. Week 4 finals were not used for new 07/08/09/05 evidence.
- The operator code composes existing research runners, independent verifiers, and ops state-machine receipts. It separates reviewed preflight from apply, binds code/config/parent SHA values, and preserves stable retry IDs.
- Candidate preparation is separate from Neon publication. A proposed exact release table and publisher/selection checks bind one prediction run, forecast, readiness receipt, model, config, and artifact.
- While preparing the production boundary, a read-only parse of `.env` showed the production `DATABASE_URL` username is `neondb_owner`. No credential value was printed. This contradicts the approved SELECT-only pipeline-role assumption and is material to the authorization design.

## Work Completed

- Added the manual cycle controller, read-only release packet validator, immutable candidate mode, exact authorization module, migration/schema updates, and focused tests.
- Added a pinned-outcomes option to the existing close operation so reviewed finals can be scored without rebuilding that ref.
- Applied migration 0014 only to the verified Preview Neon branch using the branch-scoped wrapper. Verified version `0014`, zero authorization rows, pipeline SELECT true/INSERT false, and web SELECT false.
- Updated the V5 weekly, production, and model-status documentation. No production database migration or write, release row, public selection, or V5 activation occurred.

## Files Modified

- `src/cks_picks_cfb/ops/v5_cycle.py`, `scripts/pipeline/run_v5_weekly_cycle.py` — manual component preflight/apply/status and receipts.
- `src/cks_picks_cfb/ops/v5_release.py`, `scripts/pipeline/validate_v5_release_packet.py`, `contracts/migrations/0014_v5_exact_release_authorization.sql`, canonical/shared schemas — proposed exact release boundary.
- `scripts/pipeline/generate_weekly_bets.py`, `scripts/pipeline/generate_v5_weekly_bets.py`, `scripts/pipeline/publish_to_db.py`, `scripts/pipeline/select_public_run.py`, `src/cks_picks_cfb/ops/public_selection.py`, `src/cks_picks_cfb/ops/__main__.py` — candidate preparation, publication/selection guards, pinned close ref.
- Focused tests in `tests/` and V5 operating docs under `docs/ops/` and `docs/modeling/`.

## Validation

- [x] Full pytest at the checkpoint before the final focused test addition: 1335 passed, 2 skipped.
- [x] Focused V5 release/operator/publication/ops tests: 117 passed before the final focused test addition.
- [x] Web lint, typecheck, and production build.
- [x] Contracts validation and strict MkDocs build.
- [x] Preview migration 0014 and role-grant readback.
- [x] Final focused rerun after the last edits: 119 passed; Ruff, contracts validation, strict MkDocs, and `git diff --check` passed.
- [ ] Complete end-to-end Preview operator apply and production-role boundary verification after a revised contract.

## Amendments and Blockers

No amendment was made. The production role mismatch changes the release architecture and requires renewed Sol review under the implement-plan skill. Preserve all implementation changes for review; do not mark this plan Implemented or create a production authorization.

## Handoff Notes

- **Resume at:** Resolve the production publisher role and authorization authority in a revised plan. The smallest proposed correction is a dedicated `cks_prod_pipeline` role with only the required runtime grants, including SELECT-only authorization access, and an explicit connection switch for V5 operations.
- **Watch out for:** Preview 0014 is already applied, empty, and append-only. The current uncommitted code is incomplete until the role architecture is corrected and all final gates are rerun. V4 production serving is unchanged.

**Suggested commit message after review:** `Prepare V5 weekly operator and exact release guards`

**tags:** ["v5", "weekly-ops", "release", "blocked"]
