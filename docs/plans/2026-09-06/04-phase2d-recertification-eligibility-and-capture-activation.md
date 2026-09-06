# Phase 2d Recertification, Eligibility, and Preview Capture Activation

- **Status:** Implemented
- **Created:** 2026-09-06
- **Planner:** Sol
- **Approval source:** User supplied and explicitly authorized this exact Phase 2d plan on 2026-09-06, directing the plan be documented before implementation begins.
- **Implementation log:** `session_logs/2026-09-06/06-phase2d-recertification-and-capture-activation.md`
- **Commit policy:** Separate plan, implementation, and evidence commits

## Goal

Certify only the sealed Phase 2c lineage, publish the immutable Phase 3
eligibility handoff, and activate the existing daily Preview capture workflow
only after one successful remote rehearsal. Phase 2d succeeds when the
eligibility manifest is `eligible`, its audit has zero certification blockers,
and the enabled workflow is demonstrated to write only Preview evidence.

## Current State

Phase 2c is complete at
`artifacts/research/data-first-football-v1/phase2/silver/runs/2026-09-06T1437Z-phase2c-expanded-silver-v1/ref-set.json`
(`data_first_phase2c_ref_set_v1`, SHA-256
`b3023ab5b7a304ddbc81ae2feca56238959520a54b3a75ed9be136f5d8f51df3`). It
contains ten seasons, 80 registered Preview Silver outputs, ten verified
checkpoints, no 2020, and zero blocking reconciliation conflicts.

The existing Phase 1 audit is broad historical evidence. Its v3 report retains
two non-canonical research objects and historical result dispositions that are
not Phase 2c inputs. Amendment 2 is controlling authority: those objects and
results remain explicit historical exclusions and do not block certification of
an otherwise correct Phase 2c input.

The local workflow exists but GitHub `main` is an ancestor of local `main` and
does not contain it. The required enable variable and all required repository
secrets are absent. The user will fast-forward `main` and provision secrets;
the implementation verifies secret names only.

## Proposed Approach

Add a certification scope to the existing evidence-audit flow instead of
allowing its historical root graph to define new Phase 3 inputs. The scope pins
the Phase 2c ref set, validates its declared manifests plus catalog lineage,
and reports historical problems separately. A v2 eligibility artifact binds
the passing audit, the exact Phase 2c refs, and the remote automation-admission
record. Capture activation stays Preview-only and is enabled only after the
remote workflow proves its own routing and timing evidence.

## Scope

### Included

- Phase 1 audit v4 scoped to the exact Phase 2c ref set.
- Immutable Phase 2d identity, automation-admission, and eligibility artifacts.
- Preview-only GitHub Actions hardening, rehearsal, and schedule enablement.
- Phase 2 and Phase 3 lifecycle documentation after all gates pass.

### Excluded

- V4 or production data/model/schema behavior.
- New providers, purchases, Phase 3 measurement implementation, or model selection.
- Repairing or admitting the two non-canonical historical research objects.
- Secret-value access, force pushes, or automated Git commits/pushes.

## Affected Components and Contracts

- `scripts/research/audit_data_first_evidence.py` and a new v4 configuration
  gain a certification-root boundary that supports exact Phase 2c admission
  while retaining historical evidence dispositions.
- `src/cks_picks_cfb/data/data_first_phase2.py` and
  `scripts/research/build_data_first_eligibility.py` gain the Phase 2d
  identity, coverage, role, timing, and immutable eligibility contracts.
- `scripts/research/capture_data_first_phase2.py` and
  `.github/workflows/data-first-pregame-capture.yml` require explicit Preview
  routing and record the v2 capture identity.
- The public Phase 3 handoff is `data_first_phase2_eligibility_v2`; its
  `phase3_input_refs` contains only the exact eligible Phase 2c refs.

## Implementation Tasks

### Task 1 — Establish the committed Phase 2d checkpoint

**Changes:**

- Mark this contract `In Progress` and create the implementation log.
- Add a dedicated Phase 2d audit configuration that pins the exact Phase 2c
  ref-set URI/checksum, Phase 1 v3 audit prefix, strict coverage thresholds,
  required stages, and the historical-exclusion policy.
- Define immutable schemas `data_first_phase2d_run_identity_v1`,
  `data_first_phase2d_automation_admission_v1`,
  `data_first_phase2_eligibility_v2`, and
  `data_first_phase2_capture_run_v2`.

**Acceptance criteria:** A committed code SHA can unambiguously bind audit,
eligibility, and automation evidence without changing any production contract.

### Task 2 — Implement certification-scoped audit v4

**Changes:**

- Make the evidence resolver honor a root-level no-follow policy for the Phase
  2c ref set. Verify every declared input manifest by URI and raw/declared hash,
  then traverse only registered catalog parents and source captures.
- Require exactly ten permitted seasons and eight outputs per season; validate
  all 80 refs, manifests, objects, schemas, catalog rows, parents, capture
  provenance/timing, row counts, finite values, key uniqueness, reconciliation,
  and 2020 exclusion.
- Calculate coverage per season, season type, population, and stage. Emit an
  explicit `not_applicable` row for absent FBS-FCS postseason data.
- Apply strict `>` thresholds to every observed required stage: 95% FBS-FBS,
  90% FBS-FCS. Require 100% outcomes/source-reconciliation/postseason detail,
  zero Phase 2c blocking reconciliation rows, and only declared regular
  `provider_response_omission` gaps.
- Crosswalk all v3 issues into `resolved_for_certification`,
  `historical_exclusion`, or a blocking Phase 2c disposition. Retain historical
  result statuses and reasons without admitting them.
- Publish v4 under
  `artifacts/research/data-first-football-v1/phase1/<UTC>-phase1-evidence-audit-v4/`.
  It may be `complete_with_exclusions` only when certification blockers are zero.

**Acceptance criteria:** The expected Phase 2c minima pass: FBS-FBS regular
plays/byplay/drives/reconciled `0.9819193324`, FBS-FBS regular team stats
`0.9986091794`, FBS-FCS regular plays/byplay/drives/reconciled
`0.9734513274`, and every observed postseason stage `1.0`.

### Task 3 — Publish the immutable eligibility handoff

**Changes:**

- Harden the eligibility CLI to require Preview, an explicit UTC `as_of`, the
  committed SHA, the exact Phase 2c ref set, matching v4 audit, and a verified
  automation-admission artifact.
- Write an immutable run identity and
  `eligibility-manifest.json` at
  `artifacts/research/data-first-football-v1/phase2/recertification/runs/<UTC>-phase2d-recertification-v1/`.
- Include exact refs/checksums/schemas/parents/captures, season/population
  coverage, historical reconstruction timing, semantic availability,
  omissions, null policy, and permitted uses.
- Assign fixed roles: games for denominator/chronology; outcomes for labels;
  plays, stats, byplay, drives, and reconciled team-game for Phase 3
  measurement validation; source reconciliation for audit only; teams and
  corrections for supporting lineage only.
- Admit the 32 regular play and one regular stat omission only with their exact
  `provider_response_omission` reason. Any postseason omission blocks output.
- Set `production_activation_authorized=false` and
  `model_selection_authorized=false`.

**Acceptance criteria:** The v2 manifest is `eligible` only with zero
certification blockers, passing coverage, valid automation admission, and
exactly seven Phase 3 dataset roles across all ten seasons. Historical
exclusions do not become input refs.

### Task 4 — Harden Preview capture and prove remote activation

**Changes:**

- Require `--environment preview` for capture and record it in v2 capture
  manifests; reject every other environment.
- Remove `DATABASE_URL` from the GitHub workflow. Retain only Preview R2,
  Preview Neon, and CFBD secrets; preserve 12:00 UTC scheduling, manual
  dispatch, seven-request limit, quota preflight, retry bound, immutable
  request results, and concurrency lock.
- Add a verifier that seals `automation-admission.json` only after the exact
  GitHub run has seven successful captures, checksummed/readable R2 objects,
  Preview catalog registration, authentic capture/effective timestamps, the
  workflow code SHA, sufficient quota evidence, and at least one future
  scheduled kickoff.

**Operational sequence after the code checkpoint passes:**

1. Run local audit-v4 and eligibility dry-run at the committed SHA.
2. The user runs a non-forced `git push origin main`.
3. The user configures exactly these GitHub repository secrets:
   `CFB_R2_PREVIEW_BUCKET`, `CFB_R2_PREVIEW_ACCOUNT_ID`,
   `CFB_R2_PREVIEW_ACCESS_KEY`, `CFB_R2_PREVIEW_SECRET_KEY`,
   `PREVIEW_DATABASE_URL`, and `CFBD_API_KEY`.
4. Verify secret names only; verify the workflow exists on GitHub `main`.
5. Dispatch the manual 2026 workflow run and verify its captured evidence.
6. Seal automation admission, apply the final eligibility handoff, then set
   `CFB_DATA_FIRST_CAPTURE_SCHEDULE_ENABLED=true`.

**Acceptance criteria:** No failed, empty, partial, misrouted, or unverifiable
run enables the variable. The first scheduled run is not required to close
Phase 2d; the successful manual remote rehearsal is the activation gate.

### Task 5 — Close Phase 2 and stop

**Changes:**

- Record identities, URIs/checksums, exact coverage, omissions, v3 issue
  crosswalk, historical exclusions, GitHub run URL/SHA, quota evidence, and
  enabled-variable confirmation in the contracts and session log.
- Mark Phase 2d and overall Phase 2 `Implemented`; mark Phase 3 `Unblocked`.
- Produce an evidence-only commit proposal. Do not begin Phase 3.

## Testing Strategy

- Unit-test ref-set validation, checksum drift, crossed identities, duplicate
  refs, malformed manifests, catalog/parent/capture mismatch, 2020 rejection,
  immutable collisions, timing semantics, and omission rules.
- Test certification-blocker versus historical-exclusion scope, v3 issue
  crosswalks, strict threshold behavior, `not_applicable` coverage, result
  disposition retention, and deterministic eligibility content.
- Test eligibility roles/permitted uses, automation-admission rejection, capture
  v2 Preview routing, seven-request bounds, resume behavior, and workflow
  environment isolation.
- Run focused audit/Phase 2/Phase 2c/capture tests; full warning-as-error
  Python suite with the existing 60% branch-coverage gate; scoped Ruff
  format-check/lint; repository lint; contracts validation; MkDocs; workflow
  YAML validation; V4/repository-boundary tests; and `git diff --check`.

## Risks and Edge Cases

- Historical exclusions must never be silently converted to repaired or
  admissible evidence.
- R2 and Neon are not transactional together, so every final artifact must
  reverify the objects and catalog records it names.
- GitHub secret values remain user-managed and must never appear in logs.
- If audit or remote rehearsal fails, preserve its immutable evidence, leave
  Phase 2d `In Progress`, and do not enable the schedule.

## Definition of Done

- [ ] Implementation checkpoint is committed before data or remote operations.
- [ ] Scoped audit v4 has zero certification blockers and complete issue crosswalk.
- [ ] Eligibility manifest v2 is checksum-verified and `eligible`.
- [ ] Remote manual Preview rehearsal passes and automation admission is sealed.
- [ ] GitHub enable variable is confirmed `true` after rehearsal verification.
- [ ] Required validation, documentation, session log, and evidence-only closeout pass.
- [ ] Phase 2d and Phase 2 are marked `Implemented`; Phase 3 is only `Unblocked`.

## Amendments

Production changes, new providers or purchases, altered thresholds, admission
of excluded historical evidence, a Phase 3 implementation step, or a failed
gate that requires changed acceptance criteria requires a revised plan and
explicit user approval.
