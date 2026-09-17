# Session: V5 Rating Artifact Certification

## TL;DR

- **Worked On:** Implementing the approved V5-03B artifact certification contract (Tasks 4–6).
- **Outcome:** Task 4 complete and committed. Task 5 proven: 7-test verifier
  suite passes, including bit-exact producer-vs-verifier agreement on the
  tournament fixture. Task 6 (Preview certification run) is next.
- **Plan Contract:** `docs/plans/2026-09-16/02-v5-rating-artifact-certification.md`
- **Approval / Status:** User approved this execution decomposition on 2026-09-16; Contract 03B is In Progress.
- **Blockers:** None for Task 5. Task 6 requires a fresh Preview run identity
  and R2 execution.
- **Next:** Task 6 certification run (fresh run ID → preflight → apply → verify → idempotent repeat → close).

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

**Task 5 (Independent verifier):** PROVEN
- New verifier-owned module `src/cks_picks_cfb/ratings/possession_rating_verification.py`:
  independent parent loading, re-derived standardization / carryover /
  learned-prior / Kalman-noise / incremental-replay / FCS-pool / bridge /
  bootstrap / selection math, full 60-candidate reconstruction,
  partition-by-partition stored-artifact comparison, signed verifier manifest
  write (`verification/verifier-manifest.json`, idempotent).
- Rewrote `scripts/research/verify_data_first_possession_ratings.py`: envelope
  checks preserved, then full `verify_rating_artifact` orchestration with
  `--measurement-manifest-uri` / `--repair-manifest-uri` and a JSON report.
- Agreement fixes during proving: partition-major prediction ordering (mirrors
  producer `_merged_chunks`), concat dtype normalization for `team_frame`,
  compact datasets use the frame digest (not `partitioned_records_sha`), and
  compact plans carry empty `parts` exactly like the producer evidence.
- 7-test suite `tests/test_possession_rating_verification.py`: AST
  import-boundary, bit-exact agreement (selected/status/selection-SHA/row
  counts/7 digests/all partition plans), snapshot-perturbation sensitivity
  (states+bridge change, priors+registry untouched), stored-bytes tamper
  rejection, full apply→verify round trip with idempotent verifier manifest,
  CLI success + CLI tamper rejection.

**Task 6 (Certification execution):** Blocked on Task 5 proof — fresh run ID,
no-write preflight, evidence-bound apply, independent verify, repeat apply,
documentation close.

## Validation

- [x] Focused tests for apply path (prefix checks, manifest ordering, idempotency) — 7 passed
- [x] Focused tests for verifier (boundary, agreement, perturbation, tamper, CLI) — 7 passed
- [x] Full warning-as-error suite — 934 passed, 2 skipped
- [x] Ruff, ruff format, contracts-check, MkDocs, `git diff --check`
- [ ] Actual certification run produces immutable artifacts (Task 6)
- [ ] Independent verifier confirms all digests match (Task 6)
- [ ] Idempotent repeat returns `already_applied` (Task 6)
- [ ] Documentation updated (umbrella contract, roadmap, session logs)

## Amendments and Blockers

None. Contract 03B approved as specified.

## Handoff Notes

- **Resume at (Task 6):** fresh run ID + new commit SHA → no-write preflight
  → evidence review → `--apply --preflight-evidence` → verify script →
  repeat apply (`already_applied`) → close umbrella V5-03 as Implemented →
  commit documentation. Never reuse the `90b78d1-preflight` identity.
- **Watch out for:** Task 6 executes real R2 Preview writes; each step needs
  its gates (clean worktree, committed SHA, reviewed evidence). The verifier
  manifest write is idempotent. `production_activation_authorized` stays
  `False` throughout.

**tags:** ["v5", "ratings", "certification", "preview"]
