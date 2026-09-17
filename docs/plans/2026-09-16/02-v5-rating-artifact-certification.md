# V5-03B: Possession Rating Artifact Certification

- **Status:** Implemented
- **Created:** 2026-09-16
- **Approved:** 2026-09-16
- **Certified:** 2026-09-17
- **Planner:** Codex planning task
- **Approval source:** User approved this execution decomposition on 2026-09-16.
- **Implementation log:** `session_logs/2026-09-16/05-v5-rating-artifact-certification.md`.
- **Commit policy:** Separate materializer/verifier code commit and certified-evidence documentation commit; user executes Git.

## Certification Evidence

Run `possession-v1-ratings-20260917-d029526-cert` executed the full sequence
under committed code SHA `d0295261c1985cadd6f076ae9c60a007eac6ccb4`:

- **No-write preflight:** deterministic, zero warnings; all 60 candidates ok;
  selected `ppp__rho_0_60__exposure`; digests identical to the reviewed 03A evidence.
- **Evidence-bound apply:** recomputed the tournament, bound every partition
  and dataset digest to the preflight evidence, published the signed retained
  manifest last (`already_applied: false`).
- **Independent verifier:** reconstructed all priors, states, bridge
  predictions, and selection from the exact R6/Repair v2 parents without
  producer imports; all 7 digests, row counts, and selection fields confirmed;
  signed verifier manifest
  `.../runs/possession-v1-ratings-20260917-d029526-cert/verification/verifier-manifest.json`
  (`fc3120d4…`).
- **Idempotent repeat:** identical apply returned `already_applied` with no recomputation.

Certified artifact:
`artifacts/research/data-first-football-v1/possession-v1/ratings/runs/possession-v1-ratings-20260917-d029526-cert/retained-rating-manifest.json`
(raw SHA `7568c910…`). Selected candidate `ppp__rho_0_60__exposure`, selection
SHA `5bb2e7b6…`. This is the sole eligible Contract 04 rating parent.

## Goal

Complete steps 4–6 of the approved V5-03 contract after V5-03A passes and is
committed: publish the complete rating tournament under a fresh immutable Preview
identity, independently reconstruct and verify its retained design, prove exact
idempotency, and close the umbrella contract. Success produces the sole eligible
Contract 04 rating parent; code completion alone is not certification.

## Current State and Entry Gate

V5-03A is complete under commit `90b78d1f182945b0e4ea466235ddd4eddcab61fb`. The
deterministic preflight evidence is:

- **Selected candidate:** `ppp__rho_0_60__exposure`
- **Selection SHA:** `5bb2e7b6640d3d7243bda9f3fb30d51e85170c608baf8f5d340c943bdde53f1a`
- **Population SHA:** `12755d314a266f47151c76f63423ec006f42b9181a24db2f72c3ddc5671d518d`
- **Output digests:** 7 datasets with reproducible SHA-256 checksums

This contract must consume the same exact R6 and Repair v2 parent URIs, configuration,
cutoff, and run identity used by that preflight. Never reuse the diagnostic
`possession-v1-ratings-20260916-90b78d1-preflight` identity or a failed/partial
prefix.

The existing verifier checks only the retained manifest envelope. It is not yet
independent reconstruction and cannot certify a rating artifact.

## Proposed Approach

Extend the runner with an evidence-bound `--apply --preflight-evidence` path.
Recompute the complete tournament once, compare every partition's membership,
row count, and canonical digest to the reviewed preflight, and write immutable
children in deterministic order. Write the retained manifest last; its absence
makes any partial prefix permanently ineligible.

Build a verifier-owned reconstruction module that may share schema constants and
generic lake readers but must not import producer prior/state/tournament/
materializer code. It rereads and hashes exact parents, reconstructs the selected
prior trajectories, states, bridge predictions, all selection metrics/gates, and
the winner, then publishes a signed verification record. Repeat the exact apply
must return `already_applied` without recomputation or writes.

## Scope

### Included

- Immutable partition writers, publication plan, final retained manifest, independent verifier, idempotency, certification evidence, and lifecycle documentation.
- Negative handling for collisions, partial prefixes, mismatched preflight evidence, changed parents/config/code/cutoff, and verifier disagreement.

### Excluded

- Any candidate redesign or rerun intended to improve inspected results.
- Contract 04 forecasts, live readiness, prospective collection, catalog/Neon/production/serving writes, markets, or promotion.

## Affected Components and Interfaces

- Complete `scripts/research/run_data_first_possession_ratings.py` apply and idempotency paths.
- Replace envelope-only behavior in `scripts/research/verify_data_first_possession_ratings.py` and add verifier-owned logic in `src/cks_picks_cfb/ratings/possession_rating_verification.py`.
- Use `PartitionedDatasetWriter` and existing immutable lake primitives; do not invent a second storage format.
- Add CLI flag `--preflight-evidence <json>` for apply. Verifier interface remains `--manifest-uri`, `--expected-code-sha`, and `--environment preview`.
- Final retained manifest exposes exact parents, identity, seven output refs, preflight/selection checksums, selected recipe, verification ref, eligibility, and `production_activation_authorized: false`.

## Implementation Tasks

### Task 4 — Materialize the complete immutable artifact

**Changes:**

- Parse and validate reviewed preflight JSON: exact identity, parent hashes,
  config SHA, selected candidate, selection checksum, all seven dataset plans,
  partition order, row counts, and record digests.
- Before writes, inspect the target prefix. An exact final manifest returns
  `already_applied`; an incompatible final manifest or any pre-existing partial
  prefix is rejected and never repaired into eligibility.
- Write a signed immutable publication plan first, then child partitions and
  partitioned dataset manifests in deterministic order. Use compact immutable
  datasets only for registry/attribution; use the partition boundaries declared
  by 03A for all larger outputs.
- During recomputation, compare each part to preflight before enqueueing its
  write. After materialization, reread manifests and verify content/record hashes,
  counts, parent refs, and schema validation. Write the retained-rating manifest
  last and never overwrite it.
- Persist the selected structural/fitting recipe, inner alpha/noise histories,
  fallbacks, stage metrics, and exact Contract 04 replay inputs.

**Acceptance criteria:**

- All seven outputs exactly match preflight plans/digests and are readable under
  registered schemas; the final manifest appears only after every child passes.
- No partial/incompatible prefix can become eligible. No catalog, Neon,
  production, V4, or public write occurs.

### Task 5 — Independently reconstruct and verify

**Changes:**

- Implement verifier-owned parent decoding, auxiliary normalization,
  standardization, priors, analytic/recency/Kalman updates, bridge fitting,
  diagnostics, bootstrap, gates, tie order, and cross-definition selection.
- Forbid imports from `possession_ratings`, `possession_rating_tournament`,
  `possession_rating_materializer`, and the runner; add an AST import-boundary
  test and a producer-only perturbation test that the verifier catches.
- Verify stored bytes before decoding, all schema/key/finite/positive-variance
  constraints, exact source/cutoff chronology, complete population, candidate
  result/failure coverage, both valid references, and exactly one selected row.
- Reconstruct every selection metric for all candidates and full trajectories/
  predictions for the retained candidate. Compare rows and canonical digests by
  partition without full-history concatenation.
- Write a signed immutable verifier manifest linked from certification evidence;
  verifier disagreement leaves the producer artifact ineligible.

**Acceptance criteria:**

- Verifier-selected candidate, parameters, metrics, trajectories, predictions,
  plans, and digests exactly equal stored evidence.
- Independence tests prove that producer selection or state defects are not
  mirrored automatically by the verifier.

### Task 6 — Execute bounded certification and close V5-03

**Changes:**

- Run focused/full validation on a clean committed worktree. Choose a fresh run
  ID only after capturing the full commit SHA; use one shared UTC cutoff and the
  exact parent/config arguments for dry run and apply.
- Execute: no-write preflight → evidence review → evidence-bound Preview apply →
  independent verifier → identical repeat apply. Record elapsed phases,
  row counts, digests, selected design, source coverage, and immutable URIs.
- Update the retained manifest's eligibility only through the declared signed
  verification/certification record; never edit an existing object.
- Mark the umbrella V5-03 contract Implemented only if every definition-of-done
  gate passes. Update plan index, canonical roadmaps/methodology/requirements,
  and the implementation log with the sole eligible Contract 04 parent.

**Acceptance criteria:**

- Preflight, apply, independent verification, and repeat apply all pass under
  identical lineage; repeat apply returns `already_applied` and writes nothing.
- Documentation distinguishes code implementation, historical development
  selection, artifact certification, downstream eligibility, and prospective
  evidence. V4 and production remain unchanged.

## Testing Strategy

- Writer tests: exact evidence reconstruction, per-part mismatch, reordered/
  missing/extra partition, checksum drift, immutable collision, partial prefix,
  manifest-last ordering, write failure, retry, and exact idempotency.
- Verifier tests: import independence, producer perturbation, future/same-game
  leakage, prior/noise/bridge/selection disagreement, population/fallback/stage
  mismatch, invalid variance, tampered bytes, wrong parent/config/code/cutoff,
  and both-reference validity.
- Integration: small complete dry-run/apply/verify/reapply fixture with all seven
  outputs, plus read-only exact-parent smoke checks before the full Preview run.
- Validation: focused warning-as-error tests, full warning-as-error suite and
  coverage, scoped Ruff, schema/contract checks, production-boundary regression,
  strict MkDocs, CLI help/compile, R2 prefix inventory, and `git diff --check`.

## Risks and Edge Cases

- Long computation or writes can leave immutable child objects. Manifest-last
  publication and fresh identities make these safely ineligible; never reuse
  such a prefix.
- Producer/verifier shared helpers can create false agreement. Share only generic
  serialization/schema/lake utilities, not rating or selection calculations.
- A valid development winner is not prospective evidence and cannot activate
  production. Contract 04 remains a separate dependency-gated task.
- If certification reveals a semantic defect, preserve the failed identity and
  return to planning. Mechanical performance/observability fixes require a new
  commit and fresh run identity.

## Definition of Done

- [x] Complete preflight evidence is reproduced exactly by immutable apply.
- [x] All seven datasets and retained manifest pass schema, lineage, checksum, population, and uncertainty gates.
- [x] Independent verifier reconstructs the selected design and all selection evidence without producer imports.
- [x] Exact repeat apply is idempotent; failed/partial prefixes remain ineligible.
- [x] Umbrella V5-03 and authority documentation name one sole eligible Contract 04 parent.
- [x] Required validation and full implementation/certification session logs are complete.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be logged
if output order, bytes, plans, digests, identities, and acceptance criteria are
unchanged. Any change to sources, math, registry, folds, gates, schemas,
eligibility, or verification independence requires user-approved replanning.
