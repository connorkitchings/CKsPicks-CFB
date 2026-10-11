# Session: Exact-key adjusted-row investigation

## TL;DR
- **Worked On:** Read-only historical/current/source reconciliation for 95 database-only adjusted rows.
- **Outcome:** All 95 recovered, independently explained and unchanged in both environments; zero unresolved findings. No database/R2 mutation. Separate remediation remains open.
- **Plan Contract:** `docs/plans/2026-10-10/04-investigate-database-only-adjusted-rows.md`
- **Approval / Status:** Explicit user implementation request; Implemented (investigation only).
- **Blockers:** None for investigation; replacement/cleanup needs its own reviewed execution scope.
- **Next:** Engineer/user scopes certified historical EPA replacement, exact stale-key cleanup, backups, guarded apply/readback and rollback proof.

## Context and Decisions
- `dev` at `d22efb1a`; preserved the five uncommitted preparation documents. The repair matrix alone gained authorized findings/amendment.
- Approved contract and planning log persisted before code edits; same-chat implementation explicitly authorized.
- Durable source remains Preview R2; storage identity checked against pinned Task 4 plan. No root `data/`, publication, schema/model change, release approval, Git stage/commit/merge/push or stash operation.
- Restricted Preview/Production pipeline roles verified as login and effective role. Both transactions confirmed read-only and repeatable-read, then rolled back after snapshots.

## Work Completed
- Found original full snapshots retained under the prior scratchpad `matchup/previous-preview` and `previous-production` folders. Verified adjusted/game-log/component Parquet bytes against saved metadata and preserved them under the new evidence directory.
- Reconstructed pinned candidate entirely in memory; historical database 2,062 keys, shared candidate 1,967, original extras 95, candidate-only historical zero. Added as-of-6 scope is 549, kept separate.
- Recovered every canonical key; 95 EPA rows across 45 teams (as-of 1/2/3/4/5: 4/34/31/18/8).
- Hash-checked original measurement parent and corrected published observations/populations. Verified completed valid game identities and eligibility windows. Rebuilt every legacy extra, including rank/cohort/exposure, using the original whole adjustment population. Corrected missing/nonfinite eligible PPA leaves no observed EPA in each extra's window.
- Both current databases retain all 95 unchanged and all 2,062 historical business rows unchanged. Later 549 rows match candidate values/population, with provenance differences bound to verified publication manifests. Exact business parity across 2,611 keys.
- Explicitly compared every field offline: 2,611 environment-specific `updated_at` differences retained in CSV as operational metadata. Original snapshots omit write timestamps, so historical timestamp equivalence is not claimed.
- Emitted new local snapshots, complete key/field CSVs, source explanations, adjustment-population hashes and checksummed code/input/output receipts. Final Preview receipt `620ca22402e3b2a0259339a348a622de2ffaf213b227003cd3157e4affa160a2`; Production receipt `cd6888f28e59000afe6c773d67747a704ffa3d0e4d385b147c4cece750e703a7`.
- Preserved all intermediate/failed evidence. The initial report-envelope mismatch was corrected by checking the actual adjusted-table sections, which match exactly. Only `preview-final`, `production-final` and `review-final` are the completed handoff.
- Updated repair matrix and Amendment 11 without claiming repair/release completion. Report recommends full historical EPA replacement, since 951 shared EPA rows also differ; deletion of 95 alone is insufficient.

## Files Modified
- `src/cks_picks_cfb/audit/adjusted_rows.py` — pure exact-key comparison/source evidence helpers.
- `scripts/pipeline/investigate_adjusted_rows.py` — explicit environment/pinned-plan/fresh-output read-only CLI.
- `tests/test_adjusted_rows_investigation.py` — 18 focused boundary/negative tests.
- New investigation contract, planning log, this log and `docs/plans/2026-10-10/adjusted-row-investigation/` evidence/report/offline verifier.
- `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md` — investigation disposition, next owner/gate and Amendment 11.

## Validation
- [x] 18 investigation + 17 unchanged documentation-authority tests: 35 passed with warnings as errors.
- [x] Scoped Ruff lint and format checks, including offline evidence verifier.
- [x] Final Preview/Production CLI invocations: exit 0, zero unresolved findings; Production compares final Preview snapshot.
- [x] Offline verification: every final receipt/output checksum, exact keys, complete fields and individual dispositions.
- [x] Strict MkDocs (initial out-of-docs YAML link corrected to a code path).
- [x] `git diff --check`.

## Amendments and Blockers
- Different report envelopes clarified mechanically; actual adjusted-table comparisons equal. No scope/acceptance relaxation.
- No remediation authority or execution inferred from a passing investigation receipt.

## Handoff Notes
- **Resume at:** Review `docs/plans/2026-10-10/adjusted-row-investigation/decision-report.md` and separately plan certified historical EPA replacement/cleanup.
- **Watch out for:** Preserve all old snapshots, immutable parents and later as-of-6 rows. Recheck before-state drift before any future write. This investigation does not close descendant certification or the repair track.
- **Suggested user-run commit:** `feat(audit): reconcile historical adjusted rows with read-only source evidence`.

**tags:** ["audit", "data-integrity", "read-only", "documentation"]
