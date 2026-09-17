# Session: V5 Rating Artifact Certification

## TL;DR

- **Worked On:** Implementing the approved V5-03B artifact certification contract (Tasks 4–6).
- **Outcome:** All tasks complete. Task 6 certification run passed end to
  end; Contract 03B and umbrella V5-03 are Implemented.
- **Plan Contract:** `docs/plans/2026-09-16/02-v5-rating-artifact-certification.md`
- **Approval / Status:** User approved this execution decomposition on 2026-09-16 and the R2 apply on 2026-09-17; Contract 03B is Implemented.
- **Blockers:** None.
- **Next:** Contract 04 (forecast bridge and fitting-window selection) — entry gate met.

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

**Task 6 (Certification execution):** COMPLETE 2026-09-17
- Fresh identity `possession-v1-ratings-20260917-d029526-cert` under committed
  code `d029526`, shared cutoff `2026-09-17T01:55:00Z`, exact R6/Repair parents.
- No-write preflight: zero warnings, 60/60 ok, selected
  `ppp__rho_0_60__exposure`; all digests identical to reviewed 03A evidence.
- Evidence-bound apply: recomputation matched evidence; 7 datasets written;
  signed retained manifest published last (raw SHA `7568c910…`).
- Independent verifier: full reconstruction from exact parents, no producer
  imports; all digests/rows/selection confirmed; signed verifier manifest
  (`fc3120d4…`).
- Idempotent repeat returned `already_applied` with no recomputation.
- Umbrella V5-03, plan index, roadmap, and authority docs name the retained
  manifest as the sole eligible Contract 04 parent. V4 unchanged.

## Validation

- [x] Focused tests for apply path (prefix checks, manifest ordering, idempotency) — 7 passed
- [x] Focused tests for verifier (boundary, agreement, perturbation, tamper, CLI) — 7 passed
- [x] Full warning-as-error suite — 934 passed, 2 skipped
- [x] Ruff, ruff format, contracts-check, MkDocs, `git diff --check`
- [x] Certification preflight: zero warnings, 60/60 ok, digests match reviewed evidence
- [x] Evidence-bound apply: manifest published last, `already_applied: false`
- [x] Independent verifier: `verified`, all digests/rows/selection confirmed
- [x] Idempotent repeat: `already_applied`, no recomputation
- [x] Documentation updated (umbrella contract, roadmap, plan index, session logs)

## Amendments and Blockers

None. Contract 03B approved as specified.

## Handoff Notes

- **Resume at (Contract 04):** entry gate met — independently verified 03
  ratings at
  `artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`.
  Contract 04 selects the frozen uncertainty-bearing shadow candidate
  (fitting-history experiment). Use `plan-session` (Sol) for the 04 execution
  contract since it affects forecasting architecture.
- **Watch out for:** Historical selection is development evidence, not a
  prospective win. `production_activation_authorized` is `False` on every
  artifact. V4 production unchanged.

**tags:** ["v5", "ratings", "certification", "preview"]
