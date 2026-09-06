# Session: Transformation Check-In and Phase 2d Repair

## TL;DR

- **Worked On:** Phase 0–2 completion verification, Phase 2d certification repair,
  Phase 2e auxiliary certification, and staged Phase 3 redesign.
- **Outcome:** Code, tests, documentation, and read-only evidence verification
  are complete. Replacement immutable artifacts await the required committed SHA.
- **Plan Contract:** `docs/plans/2026-09-06/05-transformation-check-in-phase2d-repair-and-phase3-redesign.md`
- **Approval / Status:** User explicitly authorized implementation on 2026-09-06; contract is `In Progress`.
- **Blockers:** Replacement immutable evidence requires a user-executed implementation checkpoint commit.
- **Next:** Commit the implementation checkpoint, then publish and independently
  verify both Phase 2d and Phase 2e evidence from that SHA.

## Context and Decisions

- The existing Phase 2d eligibility manifest is marked eligible but fails its
  declared checksum; audit-v4 and automation-admission checksums pass.
- The existing code does not enforce all promised membership, special coverage,
  lineage, omission, timing, quota, and workflow-identity gates.
- Valid Phase 2c data and remote capture evidence will be preserved; provider
  recapture is not planned.
- Phase 3 will use a shared offense/defense quality core and target-specific
  context, retaining additions only for clear chronological incremental value.
- The 63 auxiliary captures are checksum-valid primary-lake Bronze evidence,
  but their null effective timestamps make every historical row reconstructed
  and activation-ineligible.

## Work Completed

- Persisted the approved implementation contract.
- Added final-content manifest signing and replacement v2/v3 identity schemas.
- Enforced exact 80-input and 70-Phase-3-ref membership, coverage-row
  completeness, strict population thresholds, 100% outcomes/reconciliation/
  postseason detail, input roles, and exact omission identities.
- Added raw dataset-manifest and Phase 2c ref-set checksums, single-connection
  catalog traversal, cached physical source-capture checksum verification, and
  evidence-based timing classification for the two certified legacy profiles.
- Hardened automation admission around exact request/result identity, nonempty
  unique captures, physical payload/catalog verification, authentic timing,
  quota sufficiency, and live GitHub run/SHA verification.
- Made all replacement artifact writers support `dry-run`/`apply` and reject an
  apply unless HEAD matches the expected SHA and tracked files are clean.
- Added eight focused Phase 2d regression tests.
- Reconciled Phase 0–2 status and historical result dispositions. Replaced the
  Phase 3 contract with the staged, decision-complete design and aligned Phases
  4–6.
- Added Phase 2e source-inventory, direct-Bronze normalization, coverage, and
  signed reconstructed-only eligibility contracts for recruiting, returning
  production, coaching, roster continuity, lagged polls, and market references.
- Corrected the historical inventory's returning-production count, betting-line
  lineage statement, obsolete play-gap claim, and box-score role.
- Ran the hardened verifier against the real Preview evidence. The v2 dry run
  passed with 80 inputs, two historical exclusions, zero blockers, all coverage
  gates passing, 32 exact play omissions, one exact team-stat omission, and no
  postseason omissions. The v2 remote automation dry run also passed against
  GitHub run `34045238393`.

## Files Modified

- `docs/plans/2026-09-06/05-transformation-check-in-phase2d-repair-and-phase3-redesign.md`
- `session_logs/2026-09-06/07-transformation-check-in-phase2d-repair.md`
- `src/cks_picks_cfb/data/data_first_phase2d.py` - fail-closed pure contracts.
- `scripts/research/recertify_data_first_phase2d.py` - full lineage and timing verification.
- `scripts/research/verify_phase2d_automation_admission.py` - remote capture verification.
- `scripts/research/build_phase2d_eligibility.py` - replacement artifact validation and signing.
- `conf/research/data_first_football_v1/phase2d_audit_v2.yaml` - versioned repair policy.
- `tests/test_data_first_phase2d.py` - focused regression coverage.
- `src/cks_picks_cfb/data/data_first_phase2e.py` - auxiliary capture and
  normalization contracts.
- `scripts/research/certify_data_first_phase2e.py` - Preview certification runner.
- `conf/research/data_first_football_v1/phase2e_auxiliary_v1.yaml` - exact
  backfill capture window and source matrix.
- `tests/test_data_first_phase2e.py` - auxiliary regression coverage.
- Active roadmap and Phase 0–6 contracts - corrected status and staged Phase 3 design.

## Validation

- [x] Focused Phase 0–2 suite: 45 passed; new Phase 2d suite: 8 passed.
- [x] Full warning-as-error Python suite: 725 passed, 2 skipped; 66.20% branch coverage (60% required).
- [x] Ruff format-check and lint: 316 files formatted; passed.
- [x] Contracts validation and strict MkDocs build: passed.
- [x] V4/repository-boundary focus: 25 passed.
- [x] Three repaired research CLI help checks: passed.
- [x] Real Preview/GitHub automation verification dry run: admitted.
- [x] Real 80-ref Phase 2d v2 recertification dry run: complete, zero blockers.
- [x] `git diff --check`.
- [x] Phase 2e pure contract suite: 6 passed; combined Phase 2d/2e suite: 14 passed.
- [x] Phase 2e runner CLI help, Ruff, and strict MkDocs build passed.

## Amendments and Blockers

- Phase 2d and Phase 2e apply are intentionally blocked until the user commits
  this code checkpoint. No immutable object was written in this session.

## Handoff Notes

- **Resume at:** User commits the implementation checkpoint, then rerun the v2
  Phase 2d recertification/automation/eligibility sequence and the Phase 2e
  auxiliary certification in apply mode under fresh UTC run IDs; independently
  verify both signed manifests before beginning Phase 3.
- **Watch out for:** Preserve V4, production, immutable evidence, 2020 exclusion, and unrelated `.opencode/`.

**tags:** ["data-first", "phase2", "phase3", "certification", "planning"]
