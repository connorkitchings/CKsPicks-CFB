# Session: Verified Artifact and Legacy Flow Cleanup

## TL;DR

- **Worked On:** Implemented the approved post-V5 artifact and example-flow cleanup contract.
- **Outcome:** Retired the unused Prefect example flow. Audited all 460 named local files and retained them because the configured Preview R2 bucket has no exact-key counterparts and no explicit immutable mapping was found. No local artifact was deleted; artifact bytes reclaimed: 0.
- **Plan Contract:** `docs/plans/2026-09-27/02-verified-artifact-and-legacy-flow-cleanup.md` (Implemented).
- **Approval / Status:** User explicitly requested implementation of the complete proposed plan on 2026-09-27.
- **Blockers:** None for this contract. Further artifact recovery needs independently verifiable immutable copies; uploads were excluded.
- **Next:** Review and commit the contract, report, source deletion, and this log. Continue Week 5 line refresh and freeze through the separate weekly operator.

## Context and Decisions

- The earlier turn stopped before any tracked edit or deletion because Week 5 production still selected Week 4 and release work dirtied the tree. This turn confirmed production `/api/health` selected published run `2026w5-d6366e59fd43` (56 predicted, 34 lined), the release record in `session_logs/2026-09-27/06.md`, and a clean worktree before implementation.
- Pre-edit Ruff passed and the CI-equivalent full Python baseline was 1,458 passed, 2 skipped, 66.16% coverage.
- The user confirmed there are no external users of the flows. Repository scans found no caller or protected identity for `example_flow.py`; the historical `preaggregations_flow` appears in two 2025 execution logs and remains.
- Read-only Preview R2 listing returned zero objects under both exact candidate prefixes, before and after Week 5 activation. Local sidecars and tracked references gave no explicit alternate immutable mapping. No local file met the plan's deletion proof rule.
- During final checks, separate edits appeared in `web/src/app/ratings/page.tsx` and `web/src/lib/v5.ts`. This cleanup did not make or modify them; they remain outside the cleanup change set.

## Work Completed

1. Audited and SHA-256 hashed all five Preview training files and 455 legacy-archive files; all paths, sizes, allocated bytes, and hashes were unchanged on the post-release pass. No symlinks were present. The before/after account and retained dispositions are in `docs/reports/2026-09-27-verified-artifact-and-legacy-flow-cleanup.md`.
2. Removed only `src/cks_picks_cfb/flows/example_flow.py` from tracked code (1,674 apparent bytes; 4,096 allocated in the working tree before removal). Preserved the rest of `flows/`, all V5/V4 paths, and all ignored artifacts.
3. Persisted the implementation contract, cleanup report, and this session log. No R2 object was written or removed.

## Files Modified

- `src/cks_picks_cfb/flows/example_flow.py` — retired unused example flow.
- `docs/plans/2026-09-27/02-verified-artifact-and-legacy-flow-cleanup.md` — approved contract and completed lifecycle.
- `docs/reports/2026-09-27-verified-artifact-and-legacy-flow-cleanup.md` — proof and byte accounting.
- `session_logs/2026-09-27/07-verified-artifact-and-legacy-flow-cleanup.md` — implementation record.

## Validation

- [x] Pre-edit CI-equivalent full Python suite: 1,458 passed, 2 skipped, 66.16% coverage; Ruff format and lint passed.
- [x] Post-edit CI-equivalent full Python suite: 1,458 passed, 2 skipped, 66.21% coverage.
- [x] Post-edit Ruff format and lint passed; 23 repository-boundary/documentation-authority tests passed.
- [x] Shared-contract validation and MkDocs build passed.
- [x] V5 live/replay dispatcher, scheduled capture workflow, V4 rollback references, all 13 production and 28 V5 compatibility-required paths, and historical preaggregation flow remain.
- [x] `git diff --check`; only the approved tracked example flow was removed. No ignored local artifact was deleted.

## Amendments and Blockers

None. The empty R2 prefixes triggered the contract's retain-unmatched rule; they did not justify a broader remote search or new uploads.

## Handoff Notes

- **Resume at:** Review and stage only the four cleanup paths when ready; leave the concurrent web edits unstaged. No cleanup execution remains.
- **Watch out for:** The 1.35 GB of local artifacts remain as unverified local evidence. Do not treat filename similarity or an R2 ETag as deletion proof.
- **Suggested commit message:** `chore: retire unused example flow and verify local artifacts`

**tags:** ["cleanup", "repository", "artifacts", "v5", "prefect"]
