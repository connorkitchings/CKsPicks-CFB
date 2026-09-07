# Transformation Check-In, Phase 2d Repair, and Phase 3 Redesign

> **Current-authority note (2026-09-07).** The Phase 2d/2e evidence described
> here remains authoritative. Its staged Phase 3C context-selection design is
> superseded by the [Phase 3–6 resequencing contract](06-transformation-documentation-and-phase3-plus-resequence.md)
> and the replacement Phase 3–6 contracts linked from the
> [contract index](../index.md).

- **Status:** Implemented
- **Created:** 2026-09-06
- **Planner:** Sol
- **Approval source:** User approved the complete transformation check-in plan in this task and explicitly directed implementation on 2026-09-06.
- **Implementation log:** `session_logs/2026-09-06/07-transformation-check-in-phase2d-repair.md`
- **Commit policy:** Separate implementation checkpoint and evidence closeout commits; user executes Git operations

## Goal

Correct the incomplete Phase 2d certification boundary, publish a verifiable
replacement Phase 3 handoff without recapturing valid provider evidence, and
make the staged Phase 3 measurement-validation contract decision-complete.
V4 and production behavior remain unchanged.

## Current State

Phase 0 architecture boundaries passed their compatibility checks. Corrected
Phase 1 audit v3 preserves exact unsupported and correction-required historical
result dispositions. Phase 2c sealed 80 Preview Silver outputs across
2015–2019 and 2021–2025. Phase 2d audit-v4 and automation admission are readable
and checksum-valid, but the published eligibility manifest fails its own
checksum and implementation does not enforce every promised membership,
coverage, lineage, omission, timing, quota, and workflow-identity gate.

## Proposed Approach

Preserve the valid Phase 2c corpus, audit-v4 evidence, and remote capture. Add
pure validation contracts and fail-closed runners, then publish a fresh Phase
2d identity and replacement audit, automation-admission, and eligibility
artifacts from the committed repair SHA. Mark the existing eligibility artifact
superseded in documentation. Phase 3 proceeds in stages: measurement meaning,
core comparison, then context comparison.

## Published Evidence

The checksum-valid Phase 2d replacement is bound to committed SHA
`285422026816bc933279a69e997021847b4bfb31`:

- Audit: `artifacts/research/data-first-football-v1/phase1/2026-09-06T2358Z-phase2d-recertification-v2/audit-v5.json`
  (`0fd8a32a13ce64a261fa8a0179cdaa1de1cb93e428e362d50ad0aa9970c7761f`)
- Automation admission: `artifacts/research/data-first-football-v1/phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/automation-admission.json`
  (`7a46adfaff0bcb89b86f244c586d93085557ba3119699da81824ffa4e83f5518`)
- Eligibility: `artifacts/research/data-first-football-v1/phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/eligibility-manifest.json`
  (`cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760`)

It has zero certification blockers, 70 verified Phase 3 input refs, 32 exact
regular-season play omissions, one exact regular-season team-stat omission,
and no postseason omissions. The earlier defective eligibility artifact remains
superseded evidence.

The separate Phase 2e reconstructed-only handoff is bound to committed SHA
`80aba46df8b5e92959024510140cbd06de6b3b3e`:

- Capture set: `artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/capture-set.json`
  (`c2ff56b084e58b5cd159f884171df05187746c0dc40b42817912866a540de650`)
- Eligibility: `artifacts/research/data-first-football-v1/phase2/auxiliary/2026-09-07T0016Z-phase2e-auxiliary-v1/eligibility-manifest.json`
  (`d06ed3968a7bb6ec7ba97212aa2063068c253f26202e810c921b044006ab13ad`)

It registers 63 immutable Bronze captures and six Preview datasets. It is
`eligible_reconstructed_only` with `activation_eligible: false`; its context
coverage is recruiting 99.34%, returning production 99.08%, coaching 90.69%,
roster continuity 100%, and lagged rankings 100%. Recruiting 2021–2023 is an
explicit forbidden-2020 four-class-window fallback, and roster continuity has
the declared 2015/2021 prior-roster fallback.

## Scope

### Included

- Phase 0–2 status reconciliation, Phase 2d contract and runner hardening,
  focused tests, replacement Preview evidence, and detailed Phase 3 planning.
- Read-only verification of existing R2, Preview Neon, and GitHub evidence.

### Excluded

- Provider recapture unless verification finds a source defect; production or
  V4 changes; Phase 3 execution; purchases; model promotion or publication.

## Affected Components and Contracts

- `src/cks_picks_cfb/data/data_first_phase2d.py` owns pure certification,
  automation, and eligibility validation.
- Phase 2d research runners must validate raw immutable bytes, catalog lineage,
  source captures, timing, omission identities, and remote workflow evidence.
- `data_first_phase2_eligibility_v2` remains readable history; the corrected
  handoff uses a new schema/versioned identity and exact checksum semantics.
- The Phase 3 contract defines one shared quality core and target-specific
  context, with no second opponent adjustment.

## Implementation Tasks

### Task 1 — Harden Phase 2d contracts

- Require exact unique season/dataset membership for all 80 inputs and all 70
  Phase 3 refs, matching audit/ref-set identities, and raw-byte checksums.
- Enforce strict population thresholds plus 100% outcomes,
  source-reconciliation, and observed postseason-detail coverage.
- Verify exact omission game identities and reasons against Phase 2c entries.
- Verify capture request identities, immutable result bytes, catalog timing,
  nonempty responses, quota sufficiency, workflow run/SHA, and future kickoff.
- Fix manifest signing so the final stored eligibility payload verifies.

### Task 2 — Add regression coverage and validate

- Add tests for duplicate/missing refs, identity mismatch, checksum drift,
  special coverage gates, omission drift, capture duplication, quota failure,
  timing failure, workflow mismatch, and deterministic manifest signing.
- Run focused tests, the full warning-as-error Python suite and coverage gate,
  Ruff, contracts validation, MkDocs, V4/boundary checks, and `git diff --check`.

### Task 3 — Publish replacement evidence

- After the user commits the implementation checkpoint, rerun Phase 2d from
  that exact SHA without provider calls, independently verify all referenced
  objects/catalog rows, and publish a checksum-valid eligible handoff.
- Preserve the defective eligibility artifact and document it as superseded.

### Task 4 — Reconcile roadmap and Phase 3 contract

- Mark Phase 2 reopened until Task 3 passes and distinguish this transformation
  from historical phase numbering.
- Split Phase 3 into 3A meaning validation, 3B shared-core comparison, and 3C
  admitted context evaluation. Freeze candidates, folds, retention rules,
  fallback/population behavior, outputs, and consequences for Phases 4–6.

## Testing Strategy

Use pure unit tests for contract failures and runner-level tests for byte,
catalog, timing, and workflow verification. Repeat the existing Phase 0–2
focused suite, then run repository validation. Replacement evidence must be
read back independently and every declared checksum recomputed from raw bytes.

## Risks and Edge Cases

- Existing immutable evidence cannot be overwritten; corrections require fresh
  run IDs and explicit supersession.
- R2 and Preview Neon are not transactional; every referenced object and
  catalog relationship must be verified before eligibility.
- GitHub workflow evidence may use an earlier capture code SHA than the audit;
  it must match the actual successful run, while the replacement audit and
  eligibility bind the committed repair SHA.
- Historical reconstruction is development evidence only. Daily source capture
  is not a frozen model prediction.

## Definition of Done

- [x] Phase 2d implementation rejects every identified false-positive case.
- [x] Required local validation passes.
- [x] A committed repair SHA produces checksum-valid replacement evidence.
- [x] Phase 0–2 status documentation and historical result dispositions agree.
- [x] The Phase 3 contract is decision-complete and remains gated on Phase 2.
- [x] Phase 2e code rejects malformed capture matrices, duplicate identities,
  incomplete context coverage, and non-lagged rankings; it writes only
  reconstructed-only Preview evidence.
- [x] A committed repair SHA produces signed, independently verified Phase 2e
  auxiliary evidence alongside the Phase 2d replacement handoff.
- [x] Implementation log is updated and the Phase 3 contract is unblocked.

## Amendments

### 2026-09-06 — Phase 2e auxiliary evidence extension

**Approval source:** User approved the Transformation Continuation plan and
explicitly directed implementation on 2026-09-06.

Phase 2d remains the exact 80-ref core handoff. Phase 2e separately verifies
the 63 committed primary-lake captures, normalizes reconstructed-only context
in Preview, and emits a signed auxiliary eligibility manifest. It admits
recruiting, returning production, coaching, roster continuity, and strictly
lagged polls for Phase 3 research only. Historical betting lines become a
post-Phase-5 diagnostic reference only. Phase 3A/3B remain gated on Phase 2d;
Phase 3C requires both handoffs.
