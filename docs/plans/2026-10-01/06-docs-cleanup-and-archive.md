# Documentation Cleanup, Contract Close-out and Archive/Delete

- **Status:** Implemented
- **Created:** 2026-10-01
- **Planner:** Sol
- **Approval source:** User approved the plan and the per-contract status table in-session on 2026-10-01.
- **Implementation log:** `session_logs/2026-10-01/12-docs-cleanup-and-archive.md`
- **Commit policy:** One commit per step; each reverts independently.

## Goal
Make the documentation tree truthful and navigable without changing behavior.

## Scope
1. Format the 15 files failing `ruff format --check` (formatting only).
2. Close out 20 stale contract statuses (table recorded in the implementation log and each contract's status line).
3. Archive August 2026 session logs (`session_logs/2026-08-*` → `session_logs/archive/daily/`) with scripted link rewriting and a link-equivalence check.
4. Delete tracked legacy: `.opencode/`, `artifacts/{cross_validation,reports,spread_bucket_summary.json,totals_threshold_summary.json}` (git history retains them).
5. Fix `file:///Users/...` links, make `mkdocs build --strict` pass, add missing nav entries, refresh stale dates/text.

## Constraints
- `tests/test_data_first_documentation_authority.py` pins strings in `docs/modeling/v5_status.md` and reads `docs/plans/2026-09-08/*` and `docs/archive/v5-contracts/**`; those are not edited or moved.
- Plan files are not moved; only Status lines change.

## Deleted in step 4 (recoverable from git history)
`.opencode/plans/` (7 plans dated 2026-09-09 and earlier; a second plans location superseded by `docs/plans/`) and tracked V2-era artifacts: `artifacts/cross_validation/`, `artifacts/reports/week_16_email.html`, `artifacts/spread_bucket_summary.json`, `artifacts/totals_threshold_summary.json`. `artifacts/README.md` stays.

## Definition of Done
- [x] pytest unchanged (1543 passed, 3 skipped with a dummy `CFBD_API_KEY`); `ruff format --check` and `ruff check` clean.
- [x] `mkdocs build --strict` passes; link checker finds no broken or changed link targets.
- [x] No `file:///Users` links; no non-archive `session_logs/2026-08` references.

## Rollback
`git revert` the step's commit.
