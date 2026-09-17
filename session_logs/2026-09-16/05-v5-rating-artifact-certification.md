# Session: V5 Rating Artifact Certification

## TL;DR

- **Worked On:** Implementing the approved V5-03B artifact certification contract (Tasks 4–6).
- **Outcome:** Task 4 complete and committed (`109d34f`). Task 5 drafted and
  stabilized but unproven; Tasks 5/6 remain open.
- **Plan Contract:** `docs/plans/2026-09-16/02-v5-rating-artifact-certification.md`
- **Approval / Status:** User approved this execution decomposition on 2026-09-16; Contract 03B is In Progress.
- **Blockers:** Task 5 needs agreement/perturbation/AST tests and a first
  end-to-end verification run before Task 6 certification can proceed.
- **Next:** Prove the verifier (see Handoff Notes), then run Task 6 certification.

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

**Task 5 (Independent verifier):** IN PROGRESS — draft complete, not yet proven
- New verifier-owned module `src/cks_picks_cfb/ratings/possession_rating_verification.py`
  (~2,200 lines): independent parent loading, re-derived standardization /
  carryover / learned-prior / Kalman-noise / incremental-replay / FCS-pool /
  bridge / bootstrap / selection math, full 60-candidate reconstruction,
  partition-by-partition stored-artifact comparison, signed verifier manifest
  write (`verification/verifier-manifest.json`, idempotent).
- Rewrote `scripts/research/verify_data_first_possession_ratings.py`: envelope
  checks preserved, then full `verify_rating_artifact` orchestration with
  `--measurement-manifest-uri` / `--repair-manifest-uri` and a JSON report.
- Import boundary holds by construction (only shared data contracts, lake
  readers, schema validation, signing) — AST test not yet written.
- Stabilized at wrap-up: fixed `_v_history_audit` part-count reference,
  simplified `_compare_partitioned` onto validated manifest metadata, wrapped
  all storage reads as `IndependentRatingError`. Compiles, lints, imports
  cleanly; `--help` verified.
- NOT yet done: producer-vs-verifier agreement test on the fixture, stored-
  artifact perturbation test, AST import-boundary test, and the Preview
  certification run (Task 6). The module has never executed end-to-end;
  bit-exactness of the independent floating-point paths is unproven.

**Task 6 (Certification execution):** Blocked on Task 5 proof — fresh run ID,
no-write preflight, evidence-bound apply, independent verify, repeat apply,
documentation close.

## Validation

- [x] Focused tests for apply path (prefix checks, manifest ordering, idempotency) — 7 passed
- [ ] Focused tests for verifier (import boundary, reconstruction accuracy)
- [x] Focused suites at wrap-up — 242 passed (ratings + runner) with warnings-as-errors
- [x] Ruff, ruff format, contracts-check, MkDocs, `git diff --check`, verifier import + CLI help
- [ ] Verifier module executed end-to-end (agreement with producer unproven)
- [ ] Actual certification run produces immutable artifacts
- [ ] Independent verifier confirms all digests match
- [ ] Idempotent repeat returns `already_applied`
- [ ] Documentation updated (umbrella contract, roadmap, session logs)

## Amendments and Blockers

None. Contract 03B approved as specified.

## Handoff Notes

- **Resume at:** Prove the verifier before any Preview certification run:
  1. AST test — `possession_rating_verification.py` must not import
     `possession_ratings`, `possession_rating_tournament`,
     `possession_rating_materializer`, or either research runner.
  2. Agreement test — producer `compute_tournament` vs verifier
     `reconstruct_tournament` on the materializer fixture: identical parts,
     digests, selection, candidate status.
  3. Perturbation test — tamper one stored artifact object; verification must
     fail loudly (and pass again on the untampered copy).
  4. If agreement fails, diff digests by dataset/partition to isolate the
     divergent formula; the bridge `varying`-feature filter and incremental
     recency accumulation order are the highest-risk spots.
- **Then Task 6:** fresh run ID + new commit SHA → no-write preflight →
  evidence review → `--apply --preflight-evidence` → verify script →
  repeat apply (`already_applied`) → close umbrella V5-03 as Implemented →
  commit documentation.
- **Watch out for:** The verifier module has never executed end-to-end (only
  compile/lint/import verified). Do not approve Task 6 until the agreement
  test passes. `production_activation_authorized` stays `False` throughout.

**tags:** ["v5", "ratings", "certification", "preview"]
