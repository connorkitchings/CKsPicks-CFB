# V5-03B: Possession Rating Artifact Certification

- **Status:** Draft
- **Created:** 2026-09-16
- **Planner:** Codex planning task
- **Approval source:** Pending user approval of this execution decomposition.
- **Implementation log:** Pending; create `session_logs/<execution-date>/NN-v5-rating-artifact-certification.md`.
- **Commit policy:** Separate materializer/verifier code commit and certified-evidence documentation commit; user executes Git.

## Goal

Complete steps 4–6 of the approved V5-03 contract after V5-03A passes and is
committed: publish the complete rating tournament under a fresh immutable Preview
identity, independently reconstruct and verify its retained design, prove exact
idempotency, and close the umbrella contract. Success produces the sole eligible
Contract 04 rating parent; code completion alone is not certification.

## Current State and Entry Gate

This contract is blocked until V5-03A has a clean committed SHA and a reviewed,
deterministic no-write preflight containing complete part plans and digests. It
must consume the same exact R6 and Repair v2 parent URIs, configuration, cutoff,
and run identity used by that preflight. Never reuse the diagnostic
`possession-v1-ratings-20260916-453ad7c-preflight` identity or a failed/partial
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

- [ ] Complete preflight evidence is reproduced exactly by immutable apply.
- [ ] All seven datasets and retained manifest pass schema, lineage, checksum, population, and uncertainty gates.
- [ ] Independent verifier reconstructs the selected design and all selection evidence without producer imports.
- [ ] Exact repeat apply is idempotent; failed/partial prefixes remain ineligible.
- [ ] Umbrella V5-03 and authority documentation name one sole eligible Contract 04 parent.
- [ ] Required validation and full implementation/certification session logs are complete.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be logged
if output order, bytes, plans, digests, identities, and acceptance criteria are
unchanged. Any change to sources, math, registry, folds, gates, schemas,
eligibility, or verification independence requires user-approved replanning.
