# Session: V5 weekly operator implementation (amended contract)

## TL;DR

- **Worked On:** Resumed the paused Terra implementation of the V5 weekly operator contract under the approved 2026-09-25 production-role amendment.
- **Outcome:** Dual-identity release guard, production Keychain wrapper, restricted `cks_prod_pipeline` role, and production migration verification are complete; fixture-class Preview operator rehearsal passed end to end; the plan is Implemented.
- **Plan Contract:** `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` (Implemented).
- **Approval / Status:** User authorized this exact plan path and the amendment, committed the reviewed work (`990c824`, `5a32ee0`), and applied production migrations 0013→0014 themselves with Week 4 freeze (`e5d7c93`). Git operations remain user-controlled. No production V5 activation was authorized.
- **Blockers:** None.
- **Next:** After stabilized Week 4 finals, run the live 07/08 refresh under new immutable IDs through the operator, then verified Contract 09 forecast/readiness; the exact release packet and a separate activation decision remain later work.

## Context and Decisions

- The commit checkpoint landed before production work, as the amendment requires. The user applied 0013→0014 in production during the Week 4 freeze; this session verified that end state instead of re-applying.
- `assert_v5_database_environment` now requires both `session_user` and `current_user` to exactly equal the restricted pipeline role per environment; selection wraps the failure as `PublicSelectionError` to keep its exception contract uniform.
- An accidental repo-wide `ruff format` touched nine unrelated clean files; they were reverted to HEAD, restoring the session-scoped worktree.
- The Preview rehearsal uses the exact accepted-chain parents (inputs bundle `season-2026-w0-w3-byplay.json`, anchor `repair-v2-20260909T1417Z`) and is explicitly fixture-class evidence on stabilized Weeks 0–3 data.

## Work Completed

- Added `scripts/ops/with_production_pipeline_env.sh` (Keychain `ckspicks-cfb/production/pipeline-url`, fails closed) and documented it as the production V5 operator/publisher/selector entry point.
- Tightened the V5 database guard to the exact dual-role check at the publisher and selection boundaries, including direct `--from-artifact` and direct selection calls.
- Extended tests: exact-role positives, and negatives for owner, migrator, web, wrong-branch, prefix-impostor, and `SET ROLE` sessions at both boundaries with zero prediction/selection writes.
- Read-only production inspection; provisioned `cks_prod_pipeline` (single `cks_pipeline` membership, no admin attributes) and stored its branch URL in Keychain without printing it.
- Verified production migration state (0013/0014 checksums byte-identical to committed files), zero authorization rows, unchanged V4 serving (`2026w4-da5d98761831` frozen, 58/58), and all grants through a real wrapper connection.
- Ran the end-to-end Preview operator rehearsal: preflight → reviewed evidence → apply with independent verification → status → idempotent repeat (`resume_skip`), cycle `v5-rehearsal-2026w4`, run `repair-2026-rehearsal-20260925` (157/157/157, zero omissions, `repaired_live_only`).
- Updated runbooks, `v5_status.md`, `docs/plans/index.md`, and the plan (Implemented with an evidence record).

## Files Modified

- `scripts/ops/with_production_pipeline_env.sh` - new production pipeline wrapper.
- `src/cks_picks_cfb/ops/v5_release.py` - exact dual-identity environment guard.
- `src/cks_picks_cfb/ops/public_selection.py` - wrap guard failure as `PublicSelectionError`.
- `tests/test_v5_release.py`, `tests/test_public_selection.py`, `tests/test_publish_to_db.py` - guard protocol and boundary negatives.
- `docs/ops/v5_weekly_operator.md`, `docs/ops/production_runbook.md`, `docs/modeling/v5_status.md`, `docs/plans/index.md`, `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` - documented production identity, migration state, and rehearsal evidence.

## Validation

- [x] Full pytest: 1364 passed, 2 skipped (before docs-only edits; focused V5 suites rerun after).
- [x] `uv run ruff check .`, `uv run python contracts/validation.py`, `make contracts-check`, strict MkDocs, `git diff --check`.
- [x] Web typecheck and lint via Nx.
- [x] Production: role/grant readback through the real wrapper connection; authorization table 0 rows; V4 active run unchanged.
- [x] Preview: cycle apply receipt `v5-cycle-v5-rehearsal-2026w4-repair` succeeded with independent verification; repeat apply `resume_skip`.

## Amendments and Blockers

None. The user-executed production migration (instead of Terra applying it) matches the amendment's expected end state; checksums verified.

## Handoff Notes

- **Resume at:** After Week 4 finals stabilize (24h post-final-certified), refresh 07/08 via the operator under new immutable IDs, then the verified Contract 09 forecast and 05 readiness for the next slate.
- **Watch out for:** Production V5 publication still requires an admin-written `v5_serving_authorizations` row from a separate exact-packet decision; nothing in this session authorizes activation. Keep 0014 byte-identical. Never run V5 publisher/selector with the owner URL.

**Suggested commit message:** `Complete V5 operator release boundary and production role`

**tags:** ["v5", "release", "neon", "ops", "security"]
