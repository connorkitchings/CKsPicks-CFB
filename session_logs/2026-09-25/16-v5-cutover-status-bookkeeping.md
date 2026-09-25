# Session: Post-cutover status and bookkeeping

## TL;DR

- **Worked On:** Verified W4 remains unscored, retired the Vercel weeks variable, and updated status docs to reflect the live V5 replay cutover.
- **Outcome:** Docs now state the true public state (V5 replay primary W0–4; V4 rollback-ready). Plan 02 DoD reflects executed reality; W4 scoring + 2025 audit + final Implemented marking remain open.
- **Plan Contract:** `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` (Approved; 4/7 DoD items checked).
- **Approval / Status:** No new approvals sought or granted; no production writes.
- **Blockers:** W4 finals gate (1/58 kicked off, 0 finals as of 2026-09-25 ~17:00 UTC).
- **Next:** Push `main` to deploy the cutover publicly; after W4 finals certify, score V5 W4, run the 2025 audit, then mark plan 02 Implemented; Week 5 live path at the finals gate.

## Context and Decisions

- Full pytest after all recent Python changes: 1397 passed, 2 skipped.
- The Vercel weeks variable is dead in current source but live in production (local main is 117 commits ahead of origin/main). Retired it in code comments, env files, and live docs; the deploy that kills it is the user's push.
- `CFB_PUBLICATION_MODE`/`SEASON` stay env-driven deliberately (fail-closed boundary).

## Work Completed

- Production read-only recheck: W4 run published, 0 grades, 0 finals; V4 run frozen.
- `v5_status.md`: public-site statements now describe V5 replay primary + V4 rollback + pending live activation.
- Plan 02: DoD checkboxes + execution-status note (open: 2025 audit, W4 scoring, final pass).
- Retired-weekly-variable change (previous session log 15 covers the edits).

## Files Modified

- `docs/modeling/v5_status.md` - cutover status.
- `docs/plans/2026-09-25/02-v5-week4-replay-site-cutover.md` - DoD + execution status.

## Validation

- [x] Full pytest: 1397 passed, 2 skipped.
- [x] Production read-only rechecks (W4 state, V4 frozen).
- [x] Strict MkDocs build; `git diff --check`.

## Amendments and Blockers

None.

## Handoff Notes

- **Resume at:** Commit below; push to deploy; after W4 finals certify, score V5 W4 (frozen quotes staged) and run the 2025 coverage audit.
- **Watch out for:** Deploy ships 117+ commits; keep `CFB_PUBLICATION_MODE=predictions` in Vercel and delete the dead weeks variable after deploy.

**Suggested commit message:** `Record V5 replay cutover status`

**tags:** ["v5", "docs", "status"]
