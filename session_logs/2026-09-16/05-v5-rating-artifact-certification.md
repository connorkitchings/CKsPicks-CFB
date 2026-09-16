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

**Task 4 (Evidence-bound apply):**
- Extend `run_data_first_possession_ratings.py` with `--apply` path
- Parse preflight evidence JSON
- Verify R2 prefix is clean (no partial artifacts)
- Materialize all 7 partitioned datasets with deterministic ordering
- Write retained manifest last (manifest-last ordering)
- Idempotent: re-running apply with same evidence returns `already_applied`

**Task 5 (Independent verifier):**
- Create `possession_rating_verification.py` module
- Must not import any producer code (enforced by AST import-boundary test)
- Independently reconstruct: priors, states, bridge predictions, selection
- Compare reconstructed digests to stored artifact digests
- Report verification status with detailed mismatch diagnostics

**Task 6 (Certification execution):**
- Run apply with 03A preflight evidence
- Run independent verifier on materialized artifacts
- Run idempotent repeat (expect `already_applied`)
- Update umbrella V5-03 to Implemented
- Write session log and commit documentation

## Validation

- [ ] Focused tests for apply path (prefix checks, manifest ordering, idempotency)
- [ ] Focused tests for verifier (import boundary, reconstruction accuracy)
- [ ] Full warning-as-error suite passes
- [ ] Ruff, ruff format, contracts-check, MkDocs strict
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
