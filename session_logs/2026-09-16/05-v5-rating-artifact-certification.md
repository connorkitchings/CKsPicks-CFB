# Session: V5 Rating Artifact Certification

## TL;DR

- **Worked On:** Implementing the approved V5-03B artifact certification contract.
- **Outcome:** Contract 03B approved by user on 2026-09-16. Implementation in progress.
- **Plan Contract:** `docs/plans/2026-09-16/02-v5-rating-artifact-certification.md`
- **Approval / Status:** User approved this execution decomposition on 2026-09-16.
- **Blockers:** None. Entry gate met: 03A committed SHA `90b78d1` with reviewed preflight evidence.
- **Next:** Implement Task 4 (evidence-bound materialization), Task 5 (independent verifier), Task 6 (certification execution).

## Context and Decisions

- Contract 03A is complete under commit `90b78d1f182945b0e4ea466235ddd4eddcab61fb`.
- Preflight evidence: selected candidate `ppp__rho_0_60__exposure`, selection SHA `5bb2e7b6...`, population SHA `12755d31...`, all 60 candidates ok.
- Must consume exact R6 and Repair v2 parent URIs from 03A preflight.
- Never reuse the `possession-v1-ratings-20260916-90b78d1-preflight` identity.

## Implementation Plan

**Task 4 (Evidence-bound apply):** COMPLETE
- `--apply --preflight-evidence <json>` now performs the evidence-bound apply
- Evidence loader validates identity, 7 plans, ordered parts, digests, summaries
- Existing-manifest check returns `already_applied`; partial prefixes are
  permanently ineligible (prefix inspection before any write)
- Publication plan written first; 5 partitioned datasets written via
  `PartitionedDatasetWriter` with `expected_parts` evidence binding; 2 compact
  datasets via `build_dataset_version` with digest comparison
- Dataset-level `records_sha`/`row_count` re-verified against evidence after
  `finish()`; selection/candidate status re-verified against evidence
- Retained-rating manifest signed and written LAST
- Materializer gained a `PartitionSink` callback emitting each canonical
  partition frame exactly as its digest is planned (mechanical; all math,
  plans, digests unchanged — verified by 31 existing materializer tests)
- 7 new runner lifecycle tests: manifest-last ordering, exact idempotency,
  partial-prefix rejection, drifted-evidence rejection, identity mismatch,
  unordered partitions, identity collision

**Task 5 (Independent verifier):** Next — verifier-owned reconstruction in
`src/cks_picks_cfb/ratings/possession_rating_verification.py` plus AST
import-boundary test; replace envelope-only behavior in the verify script.

**Task 6 (Certification execution):** After Task 5 commits — fresh run ID,
no-write preflight, evidence-bound apply, independent verify, repeat apply,
documentation close.

## Validation

- [x] Focused tests for apply path (prefix checks, manifest ordering, idempotency) — 7 passed
- [ ] Focused tests for verifier (import boundary, reconstruction accuracy)
- [x] Full warning-as-error suite passes — 927 passed, 2 skipped
- [x] Ruff, ruff format, contracts-check, MkDocs, `git diff --check`, CLI help
- [ ] Actual certification run produces immutable artifacts
- [ ] Independent verifier confirms all digests match
- [ ] Idempotent repeat returns `already_applied`
- [ ] Documentation updated (umbrella contract, roadmap, session logs)

## Amendments and Blockers

None. Contract 03B approved as specified.

## Handoff Notes

- **Resume at:** Begin Task 4 implementation (evidence-bound apply path).
- **Watch out for:** Must not import producer code in verifier. Use separate commit for each task.

**tags:** ["v5", "ratings", "certification", "preview"]
