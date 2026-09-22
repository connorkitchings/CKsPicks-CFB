# V5 Foundation-Blocker Diagnosis

- **Status:** Implemented
- **Created:** 2026-09-20
- **Planner:** Sol
- **Approval source:** User explicitly approved during the 2026-09-20 planning session with "Approve Contract 02 now — both lanes are ready to go."
- **Implementation log:** `session_logs/2026-09-21/02-v5-foundation-blocker-diagnosis.md`
- **Commit policy:** Separate diagnostic-code/report checkpoint; user controls Git operations.

## Goal

Determine the responsible layer, affected population, and corrective blast radius
for the two upstream blockers in the valid Contract 10B audit before any repair
or descendant artifact is replaced:

1. Finding 001: Repair v2 verification imports and calls producer
   `compute_repair`.
2. Finding 003: 81 team-game score-ledger keys record more points than their
   repaired final score.

The diagnostic must produce an evidence-backed recommendation for exactly one
subsequent corrective execution contract. It must not repair data, change a
finding disposition, publish an artifact, or select a new model identity.

## Current State

Contract 10B is Implemented. Its Preview run
`historical-audit-10b-20260919-full` is valid (`publication_valid: true`) and
records `contract11_permitted: false`. Findings 001 and 003 have
`severity: blocker`, `disposition: prohibited_until_closed`, and
`closure_state: open`.

The frozen parents are:

| Role | Identity |
| --- | --- |
| Repair | `repair-v2-20260909T1417Z` |
| Measurements | `possession-v1-measurements-20260915-18fb0aa-r6` |
| Ratings | `possession-v1-ratings-20260917-d029526-cert` |
| Forecasts | `forecast-v1-20260917-4600ddd-04b` |

Finding 003 may originate in repaired finals, score-event extraction,
event-to-team attribution, possession/scoring categorization, overtime handling,
or an interaction between layers. The existing 81-key count is a finding, not an
approved exclusion rule. Finding 001 requires a verifier that does not import
or call producer computation. If Finding 003 requires a new Repair artifact,
the independent verifier must certify that surviving identity rather than the
superseded one.

Implemented 11A and approved 12A remain a separate
`conditional_historical_results_only` lane. This diagnosis neither invalidates
their immutable evidence nor grants it further use. Full Contract 11 and final
Contract 12 remain blocked.

## Proposed Approach

Create a read-only, evidence-bound diagnostic that first verifies the exact
10B/Repair/R6 parents, then traces every excess key from repaired outcome through
source scoring events and ledger categories. Classify each key using a complete,
mutually exclusive cause taxonomy. In parallel, specify an independent Repair
verifier boundary and behavioral matrix without reusing the producer's
computation.

The diagnostic report then selects one of four factual dispositions:

1. Repair-layer correction;
2. measurement/scoring-attribution correction;
3. coordinated Repair and measurement correction; or
4. a narrowly justified finding-disposition amendment supported by exact
   evidence.

Only that completed diagnosis may determine the new identity, descendants, and
execution plan. No convenience threshold, row exclusion, or normalization can
turn an excess into a pass.

## Scope

### Included

- Exact-hash revalidation of the audit finding record, Repair v2 manifest, and
  R6 measurement/scoring-ledger parents before decoding records.
- Read-only reconstruction of the full 81-key population across all development
  seasons (2015–2019 and 2021–2025; reject 2020 and 2026).
- Per-key trace of repaired final score, schedule participants, raw score events,
  score increments, team attribution, conversion linkage, possession eligibility,
  scoring category, regulation/overtime class, and duplicate/split attribution.
- Complete cause taxonomy, affected-key digest, counts by season/category/cause,
  and bounded examples.
- Independent Repair-verification design, import-boundary check, and behavioral
  matrix.
- Lineage impact graph for each confirmed disposition, including measurements,
  ratings, forecasts, 11A/12A evidence, final fit, full Contract 11, and final
  Contract 12.
- A recommendation for one subsequent corrective execution contract.

### Excluded

- R2 apply, artifact replacement, catalog/Neon/production/web writes, V4 changes,
  or scorecard execution.
- Changing a score, assigning a new scoring category, ignoring a key, or relaxing
  a reconciliation threshold.
- Closing either audit finding or changing its severity/disposition.
- Rebuilding measurement, rating, forecast, or conditional-scorecard artifacts.
- Starting full Contract 11, final Contract 12, Contracts 06–09, or promotion.

## Affected Components and Contracts

- Audit evidence: `docs/research/2026-09-19-v5-10b-historical-foundation-audit-report.md`
  and the exact four Preview audit outputs named by Contract 10B.
- Repair producer/verifier boundary:
  `scripts/research/run_data_first_repair_v2.py` and
  `scripts/research/verify_data_first_repair_v2.py`.
- R6 scoring/measurement lineage and read-only audit interfaces under
  `src/cks_picks_cfb/ratings/`, `src/cks_picks_cfb/audit/`, and
  `scripts/research/`.
- New diagnostic CLI/module/tests only if implementation requires reusable,
  read-only machinery. Final file paths are fixed by the approved execution
  contract after the diagnostic report identifies the responsible layer.
- Downstream gate owners: Contracts 10, 11, 12, and 12A.

## Implementation Tasks

### Task 1 — Bind the diagnostic to exact evidence

**Changes:**

- Resolve and validate raw/canonical hashes, signatures, identities, code/config
  bindings, rejected seasons, and parent references for the 10B finding record,
  Repair v2, and R6 measurement ledger before any data interpretation.
- Fail closed on a missing/corrupt/ambiguous reference. Do not substitute a
  current working-tree artifact or infer a parent URI.

**Acceptance criteria:**

- The diagnostic names the exact verified inputs and cannot execute on a
  different Repair or R6 identity.
- Evidence records distinguish source bytes from derived diagnostic output.

**Validation:**

- Positive exact-parent fixture and negative wrong-hash/wrong-URI/rejected-season
  fixtures.

### Task 2 — Reconstruct and classify all excess keys

**Changes:**

- Reconstruct every one of the 81 keys from raw scoring events through repaired
  finals and ledger aggregation.
- Define a mutually exclusive cause taxonomy before inspecting aggregate counts.
  At minimum, distinguish repaired-final mismatch, event duplication,
  split-team attribution, participant/team mapping, conversion linkage,
  regulation/overtime class, possession/category attribution, and unresolved or
  otherwise unclassifiable evidence.
- Publish counts and a digest of the complete affected population; include only
  bounded human-readable examples.

**Acceptance criteria:**

- Every excess key has exactly one cause or an explicit unresolved classification.
- The sum of classified keys equals 81; no key disappears through deduplication,
  thresholding, or schedule-population changes.
- Shortfalls remain reported separately and are never converted into excesses.

**Validation:**

- Fixtures for duplicate/split attribution, conversion handling, overtime,
  wrong-team mapping, and a deliberately excess ledger.
- Full-population count/digest reconciliation against the 10B finding.

### Task 3 — Specify independent Repair verification

**Changes:**

- Define a verifier-owned reconstruction from generic readers and pure
  transformations. It must not import `run_data_first_repair_v2`, `compute_repair`,
  or any producer-only module.
- Add an import-boundary assertion and a behavioral matrix covering malformed
  sources, schedule/outcome changes, score corrections, duplicate events,
  2020 exclusion, and unchanged byte-identical inputs.
- State whether verification applies to the existing Repair identity or a new
  identity dictated by Task 2; do not run certification in this contract.

**Acceptance criteria:**

- The design is independently computable and detects a producer-only perturbation.
- The expected verified identity follows the evidence-based Repair disposition.

**Validation:**

- Static import graph test and bounded behavioral fixtures.

### Task 4 — Publish diagnosis and corrective recommendation

**Changes:**

- Render a readable, versioned diagnosis report under `docs/research/` from a
  signed read-only diagnostic record.
- Produce the lineage impact graph and recommend one corrective execution
  contract with exact parent role(s), new outputs, allowed writes, independent
  verification, idempotency, re-audit, and downstream eligibility rules.
- Update lifecycle pages only to link the diagnostic report and proposed
  corrective contract; do not mark a finding closed.

**Acceptance criteria:**

- A reviewer can determine why each affected artifact must be retained or
  replaced without reading code or guessing lineage.
- The recommended corrective contract has no unresolved architectural decision.

**Validation:**

- Report rendering from a verified record only; negative tests for a missing
  cause, count/digest mismatch, and an attempt to claim finding closure.

## Testing Strategy

Run focused warning-as-error tests for parent binding, key classification,
Repair-verifier import independence, report rendering, and lifecycle gates.
The full diagnostic run is read-only and must reconcile exactly to the 10B
81-key finding. Run the full warning-as-error Python suite, scoped Ruff,
contract validation, strict MkDocs, and `git diff --check` before recording an
implemented diagnosis.

## Risks and Edge Cases

- A Repair-layer correction can invalidate every descendant V5 artifact; do not
  preserve eligibility by relabeling descendants.
- A measurement-only correction can still change rating/forecast values and
  requires a new measurement identity plus appropriate descendants.
- An unresolved key remains a blocker; a low count is not a harmless exception.
- The 11A/12A conditional lane must retain its original parent identities and
  limitations even if later corrective work creates replacements.
- Historical reconstruction is not prospective evidence and cannot authorize
  2026 work.

## Definition of Done

- [x] Exact evidence binding passes before diagnosis.
- [x] All 81 keys are reconstructed, classified, and reconciled to a complete
  digest.
- [x] Independent Repair-verifier design and import boundary are proven on
  bounded fixtures.
- [x] A signed read-only diagnosis/report and lineage impact graph are available.
- [x] One decision-complete corrective execution contract is proposed.
- [x] No findings are closed and no mutable state changes occur.

## Amendments

Mechanical report/link/test corrections may be appended if they do not change
the cause taxonomy, evidence population, permitted use, or diagnostic boundary.
Any change to those items, any new data write, or any proposed repair/rebuild
requires a separate approved corrective execution contract.
