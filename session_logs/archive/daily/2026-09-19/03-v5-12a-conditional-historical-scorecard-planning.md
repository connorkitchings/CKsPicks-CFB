# Session: V5-12A Conditional Historical Scorecard Planning

## TL;DR

- **Worked On:** Finalized and persisted the approved Contract 12A execution specification.
- **Outcome:** The conditional scorecard has an exact 11A entry record, frozen population, metric definitions, publication boundary, verification requirement, and validation plan.
- **Plan Contract:** `docs/plans/2026-09-19/12a-v5-conditional-historical-scorecard.md`
- **Approval / Status:** User explicitly authorized the exact plan with “PLEASE IMPLEMENT THIS PLAN” on 2026-09-19; contract is `Approved`.
- **Blockers:** None for the conditional scorecard. Four audit findings remain open and are preserved as limitations; they block final readiness, not this bounded historical scorecard.
- **Next:** Open a fresh Terra task using the approved plan path; implement code, run the clean-SHA Preview preflight/apply/re-read sequence, then render and certify the report.

## Context and Decisions

- Contract 11A was successfully published at `conditional-v1-20260919-9265314-11a`; its exact raw/canonical/record hashes are now pinned in Contract 12A.
- Scorecard CRPS and intervals use final target-season calibration variance, not the forecast bridge's stored head-selection CRPS.
- The immutable verified forecast population is 7,318 target rows over 3,659 games. All rows are reportable; a malformed row fails closed rather than changing the population.
- Outputs remain Preview-only `conditional_historical_results_only`; they cannot clear audit findings, restore forecast eligibility, recommend readiness, compare V4, or authorize 2026 work.

## Work Completed

- Updated the Contract 12A approval metadata and added its exact metric, population, evidence, and verifier requirements.
- Created this planning log. No implementation code, model/configuration, R2 artifact, production, Neon, web, catalog, or V4 state was changed.

## Validation

- [x] Confirmed clean starting worktree and committed 11A closure (`c2f03f7`).
- [x] Re-read the published 11A manifest and record from Preview R2 without exposing credentials.
- [x] Verified source population and calibration shape against the frozen forecast artifact.
- [ ] `git diff --check` after the documentation checkpoint.

## Amendments and Blockers

- None. The implementation specification makes only mechanical details available to Terra; all material scope and statistical choices are fixed by the approved plan.

## Handoff Notes

- **Resume at:** Fresh Terra task with `.agent/skills/implement-plan/` and the exact Contract 12A path.
- **Watch out for:** Require the exact 11A success record before score calculation. Keep all four audit findings in the evidence and report; do not broaden the conditional-use boundary.

**tags:** ["v5", "contract-12a", "planning", "historical-scorecard"]
