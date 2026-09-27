# Verified Artifact and Legacy Flow Cleanup

- **Status:** Implemented 2026-09-27
- **Created:** 2026-09-27
- **Planner:** Sol (conversation plan)
- **Approval source:** User explicitly requested implementation of the complete proposed plan in this task on 2026-09-27
- **Implementation log:** `session_logs/2026-09-27/07-verified-artifact-and-legacy-flow-cleanup.md`
- **Commit policy:** Commit with implementation; user controls Git operations

## Goal

Recover local space only from byte-verified immutable duplicates and retire the unused Prefect example flow without disturbing V5 operations, V4 rollback, or historical reproduction. Success is a complete audit of the 460 named local files, deletion only with recorded proof, and removal of the example flow after the Week 5 release and dependency gates.

## Current State

- The prior [cleanup inventory](../../reports/2026-09-27-post-v5-cleanup-inventory.md) retained five Preview training files and 455 legacy-archive files pending counterpart proof.
- Production health and the Week 5 release log now show `2026w5-d6366e59fd43` selected and published. The worktree was clean before tracked edits.
- `preaggregations_flow` appears in historical execution logs and remains available. `example_flow.py` has no repository caller or protected identity, and the user confirmed no external flow users.

## Approach and scope

Audit the local candidates and read only the configured Preview R2 bucket. Match a local file only to its exact relative key or an explicit manifest/provenance link; require a streamed SHA-256 match and an immutable remote identity before deleting it. Retain unmatched files, the local locked-candidates CSV while it is a command default, MLflow/Hydra evidence, logs, diagnostics, and model binaries. Do not upload or alter R2 objects. Remove only `src/cks_picks_cfb/flows/example_flow.py` from tracked code; retain the rest of `flows/` and all V5/V4 paths.

## Implementation tasks

1. Confirm Week 5 production selection, clean worktree, CI-equivalent baseline, current references, local counts and byte sizes, ignored status, and symlink absence.
2. Inventory all five Preview training files and 455 legacy-archive files. List exact R2 prefixes and inspect explicit provenance links. For any mapped candidate, stream local and remote bytes through SHA-256; delete only after immutable identity, local-consumer, and unchanged-file checks. Otherwise retain it and record why.
3. Recheck imports, dynamic calls, CI, tests, docs, compatibility declarations, and historical identities for the example flow. Remove that file only; preserve the historical preaggregation flow.
4. Publish a cleanup report with proof for every deletion, grouped retained dispositions, and before/after apparent and allocated bytes. Complete the implementation log.

## Validation

- CI-equivalent Python Ruff and full pytest checks, repository-boundary tests, shared-contract validation, MkDocs build, and `git diff --check` after edits.
- Inspect V5 live/replay, scheduled capture, and V4 rollback references; confirm only the approved tracked file was removed and no unverified local artifact was deleted.

## Risks and failure handling

An unmatched file, missing immutability evidence, R2 access failure, changed local file, or required local-path consumer means retention. The Week 5 release gate must remain satisfied before any deletion or tracked edit. No source-tree reduction beyond the example flow is authorized here.

## Definition of done

- [x] Release and baseline gates verified.
- [x] All 460 local files dispositioned, with no deletion lacking proof; no local artifact qualified for deletion.
- [x] Example flow removed; historical flow and operating paths retained.
- [x] Required validation passes; [report](../../reports/2026-09-27-verified-artifact-and-legacy-flow-cleanup.md) and session log complete.

## Amendments

None.
