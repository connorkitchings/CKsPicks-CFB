# V5-04B: Uncertainty Calibration, Candidate Freeze, and Artifact Certification

- **Status:** Draft
- **Created:** 2026-09-17
- **Planner:** Sol planning task
- **Approval source:** Pending user approval of this execution decomposition.
- **Implementation log:** Pending; create `session_logs/<execution-date>/NN-v5-forecast-calibration-and-certification.md`.
- **Commit policy:** Separate calibration/verifier code commit and certified-evidence documentation commit; user executes Git.

## Goal

Complete Tasks 4–5 of the approved V5-04 contract after V5-04A passes and is
committed: calibrate uncertainty from nested rolling-origin residuals, freeze
the serializable forecast candidate with its fitting recipes, publish the
complete forecast tournament under a fresh immutable Preview identity,
independently reconstruct and verify the frozen design, prove exact
idempotency, and close the umbrella contract. Success produces the frozen,
uncertainty-bearing shadow candidate that Contract 05 may consume; code
completion alone is not certification.

## Current State and Entry Gate

The 04A entry gate is met. V5-04A is **Implemented** (2026-09-17): the
hardened `scripts/research/run_data_first_forecasts.py` dry run binds all
three parent URIs exactly (`parent_uris` in the forecast identity), emits
expanded `head_metrics` (pooled + by-season + by-stage MAE/CRPS with counts),
`horizon_populations`, and `selection_seasons`/`reporting_seasons` evidence,
and reports 2018/2019/2021 retained-head diagnostics excluded from every
selection gate, plan digest, and apply population. The reviewed no-write
preflight (`forecast-v1-20260917-19ca44b-04a`, cutoff `2026-09-17T14:19:09Z`,
code `19ca44b7518c05a6810b1cf82f0c1c8e8137d289`, evidence SHA
`fcdad64c…`, three byte-identical runs) selected the shared `expanding`
horizon with the alpha-10 reference head on both targets: margin MAE 14.6446
/ CRPS 10.4413, total MAE 13.5433 / CRPS 9.5469, equal 3,659-game populations
per target per horizon.

This contract remains **Draft** until a separate explicit user approval.
Once approved, an approved 04B apply must consume the same exact 03/R6/
Repair v2 parent URIs, configuration, cutoff, and run lineage family as that
reviewed preflight — but it must generate a fresh complete 04B preflight
identity of its own. Never reuse a diagnostic preflight identity
(`forecast-v1-20260917-367b4a3-04a` and `forecast-v1-20260917-820bb1d-04a`
are dead) or a failed/partial prefix.

No calibration, forecast-schema, forecast-runner, or forecast-verifier code
exists yet. The existing verifier checks nothing about forecasts; full
verifier-owned reconstruction is built here.

## Proposed Approach

Extend the runner with an evidence-bound `--apply --preflight-evidence` path
following the proven 03B pattern. Recompute the complete offsets/bridge/
horizon computation plus nested calibration once, compare every partition's
membership, row count, and canonical digest to the reviewed preflight (plus
the new calibration evidence), and write immutable children in deterministic
order. Write the candidate manifest last; its absence makes any partial prefix
permanently ineligible.

Build a verifier-owned reconstruction module that may share schema constants
and generic lake readers but must not import producer offset/head/horizon/
calibration/materializer code. It rereads exact parents, reconstructs offsets,
nested fits, predictions, bootstrap horizon selection, uncertainty, and the
serialization round trip, then publishes a signed verification record. Repeat
the exact apply must return `already_applied` without recomputation or writes.

## Scope

### Included

- Nested rolling-origin residual calibration with Gaussian CRPS, intervals,
  and full season/stage/FCS diagnostics.
- Frozen candidate serialization with exact replay recipes and the 2026 refit.
- Immutable partition writers, publication plan, final candidate manifest,
  independent verifier, idempotency, certification evidence, and lifecycle
  documentation.
- Negative handling for collisions, partial prefixes, mismatched preflight
  evidence, changed parents/config/code/cutoff, and verifier disagreement.

### Excluded

- Any head/horizon redesign or rerun intended to improve inspected results.
- Contract 05 readiness/prospective work, live forecasts, catalog/Neon/
  production/serving writes, markets, or promotion.
- V4 evaluation-history extension; V4 comparisons appear only where its
  predictions have verified comparable lineage, with unavailable CRPS marked
  unavailable.

## Affected Components and Interfaces

- Complete `scripts/research/run_data_first_forecasts.py` apply and idempotency
  paths. Add CLI flag `--preflight-evidence <json>` for apply. The dry run
  remains the default; `--apply` requires evidence and a clean worktree.
- New verifier-owned logic in `src/cks_picks_cfb/forecast/forecast_verification.py`;
  extend `scripts/research/verify_data_first_forecasts.py` from envelope checks
  to full independent verification (`--manifest-uri`, `--expected-code-sha`,
  `--environment preview`, plus the three parent URIs).
- Use `PartitionedDatasetWriter` and existing immutable lake primitives; do not
  invent a second storage format.
- Final candidate manifest exposes exact parents, identity, seven output refs,
  preflight/selection/horizon checksums, selected horizon and head recipes,
  calibration refs, verification ref, eligibility, update recipe, and
  `production_activation_authorized: false`.

## Implementation Tasks

### Task 4 — Calibrate uncertainty and freeze serializable forecasts

**Changes:**

- For each outer season and candidate, generate earlier nested rolling-origin
  prediction residuals using the identical structural design, selected horizon,
  offset rule, and inner-alpha procedure. Require at least one eligible prior
  residual season; the first eligible residual season is 2017, allowing
  calibration for outer 2018. No current-validation residual or in-sample
  training error may substitute.
- Target variance is the mean squared prior prediction error, floor `1e-6`.
  No extra bias correction or second calibration of the same residuals. Keep
  posterior rating variance as attribution, never added to outcome variance.
- Emit labeled Gaussian marginal target distributions with analytical CRPS and
  central 50/80/95% intervals. Margin/total heads stay independent; no joint
  team-score distribution is claimed.
- Report MAE, RMSE, bias, CRPS, coverage, width, residual counts,
  season/stage/FCS coverage, floors/fallbacks, offsets, and scoring-ledger/
  possession-volume diagnostics. V4 comparisons only where its predictions
  have verified comparable cutoff and training lineage; unavailable V4 CRPS is
  marked unavailable, never zero.
- Freeze the selected design/horizon/target-alpha recipes, then refit
  unchanged on eligible history through 2025 for the 2026 candidate. Preseason
  priors, noise, heads, alpha choices, and calibration stay fixed during the
  live season; only declared prior-game state and offset updates are allowed.

**Acceptance criteria:**

- Complete serialized parameters reproduce means, variances, and intervals
  from exact states; calibration chronology is independently verified.
- Same-game/future perturbations cover every offset, parameter, and
  calibration path without altering earlier outputs.

### Task 5 — Materialize, verify, and close the frozen candidate

**Changes:**

- Parse and validate reviewed preflight JSON: exact identity, parent hashes,
  config SHA, selected horizon, head recipes, all seven dataset plans,
  partition order, row counts, and record digests.
- Before writes, inspect the target prefix. An exact final manifest returns
  `already_applied`; an incompatible final manifest or any pre-existing partial
  prefix is rejected and never repaired into eligibility.
- Write a signed immutable publication plan first, then child partitions and
  partitioned dataset manifests in deterministic order. During recomputation,
  compare each part to preflight before enqueueing its write. Write the
  candidate manifest last and never overwrite it.
- Implement verifier-owned parent decoding, offset reconstruction, nested
  fits, predictions, bootstrap selection, uncertainty, serialization round
  trip, and digest comparison. Forbid imports from producer forecast/rating
  modules and the runner; add an AST import-boundary test and a
  producer-perturbation test that the verifier catches.
- Run focused/full validation on a clean committed worktree. Choose a fresh
  run ID only after capturing the full commit SHA; use one shared UTC cutoff
  and the exact parent/config arguments for dry run and apply. Execute:
  no-write preflight → evidence review → evidence-bound Preview apply →
  independent verifier → identical repeat apply. Record elapsed phases, row
  counts, digests, selected design, and immutable URIs.

**Acceptance criteria:**

- Preflight, apply, independent verification, and repeat apply all pass under
  identical lineage; repeat apply returns `already_applied` and writes nothing.
- Verifier-selected horizon, parameters, metrics, predictions, plans, and
  digests exactly equal stored evidence.
- Documentation distinguishes code implementation, historical development
  selection, artifact certification, downstream eligibility, and prospective
  evidence. V4 and production remain unchanged.

## Testing Strategy

- Writer tests: exact evidence reconstruction, per-part mismatch, reordered/
  missing/extra partition, checksum drift, immutable collision, partial prefix,
  manifest-last ordering, write failure, retry, and exact idempotency.
- Verifier tests: import independence, producer perturbation, future/same-game
  leakage on every path, offset/parameter/calibration disagreement,
  population/fallback/stage mismatch, tampered bytes, wrong parent/config/
  code/cutoff, and serialization round-trip fidelity.
- Integration: small complete dry-run/apply/verify/reapply fixture with all
  seven outputs, plus read-only exact-parent smoke checks before the full
  Preview run.
- Validation: focused warning-as-error tests, full warning-as-error suite and
  coverage, scoped Ruff, schema/contract checks, production-boundary
  regression, strict MkDocs, CLI help/compile, R2 prefix inventory, and
  `git diff --check`.

## Risks and Edge Cases

- Nested rolling-origin residuals multiply the already-large 04A compute;
  bound the residual history per the contract and stream by partition.
- Long computation or writes can leave immutable child objects. Manifest-last
  publication and fresh identities make these safely ineligible; never reuse
  such a prefix.
- Producer/verifier shared helpers can create false agreement. Share only
  generic serialization/schema/lake utilities, not offset, head, horizon, or
  calibration calculations.
- A valid development winner is not prospective evidence and cannot activate
  production. Contract 05 remains a separate dependency-gated task.
- If certification reveals a semantic defect, preserve the failed identity and
  return to planning. Mechanical performance/observability fixes require a new
  commit and fresh run identity.

## Definition of Done

- [ ] Complete preflight evidence is reproduced exactly by immutable apply.
- [ ] All seven datasets and candidate manifest pass schema, lineage, checksum, population, and uncertainty gates.
- [ ] Independent verifier reconstructs the frozen design and all selection evidence without producer imports.
- [ ] Exact repeat apply is idempotent; failed/partial prefixes remain ineligible.
- [ ] Umbrella V5-04 and authority documentation name one frozen shadow candidate.
- [ ] Required validation and full implementation/certification session logs are complete.

## Amendments

Mechanical writer batching, checkpointing, or observability changes may be
logged if output order, bytes, plans, digests, identities, and acceptance
criteria are unchanged. Any change to sources, math, registry, folds, gates,
schemas, eligibility, or verification independence requires user-approved replanning.
