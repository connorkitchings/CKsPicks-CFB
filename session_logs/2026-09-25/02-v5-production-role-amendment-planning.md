# Session: V5 production-role amendment planning

## TL;DR

- **Worked On:** Renewed Sol review of the production-role conflict in the V5 weekly operator contract.
- **Outcome:** Documented the approved restricted-role and production-migration amendment; made no implementation or production changes.
- **Plan Contract:** `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` (In Progress; amendment approved, execution paused).
- **Approval / Status:** User approved the proposed dedicated pipeline role, chose provisioning and production migration 0014 now, and requested plan documentation only. Git operations remain user-controlled; V5 activation is not authorized.
- **Blockers:** Amendment implementation, reviewed migration commit, and real production permission verification remain pending.
- **Next:** In a separate Terra implementation task, resume the exact amended contract after user handoff; do not create an authorization row or activate V5.

## Context and Decisions

- The existing production `DATABASE_URL` authenticates as `neondb_owner`, which defeats the planned SELECT-only authorization boundary for the pipeline.
- Read-only production inspection on 2026-09-25 found `cks_pipeline` as a NOLOGIN group, no `cks_prod_pipeline` role, and migration 0012 as the latest applied version. The authorization table does not exist there yet. No production SQL writes were made.
- Use a dedicated `cks_prod_pipeline` LOGIN role inheriting only `cks_pipeline`; keep the owner credential for administration and migrations. Production V5 publication and selection must require the exact login and effective role.
- Apply pending migrations 0013 and 0014 in production after the reviewed 0014 file is committed. Keep the authorization table empty and V4 serving unchanged. The Preview-applied 0014 file must remain byte-identical.
- Store the production pipeline URL in macOS Keychain under a dedicated service and use a wrapper for V5 commands. No credential belongs in tracked files or Vercel.

## Work Completed

- Amended the existing V5 weekly operator contract with ordered role, wrapper, migration, guard, and verification tasks.
- Corrected the implementation-contract index to show In Progress and the documented amendment.
- No code, database role, migration, authorization row, or public selection was changed in this planning session.

## Files Modified

- `docs/plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md` — approved amendment and revised production boundary.
- `docs/plans/index.md` — current contract status and amendment note.
- `session_logs/2026-09-25/02-v5-production-role-amendment-planning.md` — planning handoff.

## Validation

- [x] `.venv/bin/mkdocs build --strict --quiet` — passed.
- [x] `git diff --check` — passed.

## Amendments and Blockers

The amendment explicitly overrides the original milestone's production-migration exclusion. It does not authorize the one-slate release record or V5 activation. The prior Terra implementation remains uncommitted and paused until the amended contract is handed off.

## Handoff Notes

- **Resume at:** Review the existing uncommitted code, implement the exact role guard and Keychain wrapper, provision and verify the production role, then apply the reviewed 0013→0014 chain after the user commits 0014.
- **Watch out for:** Do not edit 0014, which is already applied on Preview. Stop on unexpected production migration or privilege drift. Preserve V4 serving and the original Week 4 finals gate.

**Suggested commit message:** `Document V5 production role amendment`

**tags:** ["v5", "planning", "neon", "release"]
