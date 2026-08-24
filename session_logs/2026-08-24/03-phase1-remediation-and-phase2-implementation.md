# Session: Phase 1 remediation and Phase 2 team-state implementation

## TL;DR

- **Worked On:** Implemented the reviewed Phase 1 corrections and the isolated
  Phase 2 empirical-Bayes team-state baseline.
- **Outcome:** Local implementation and validation are complete; Preview
  materialization is deliberately blocked until the relevant source is in a
  recorded Git commit.
- **Plan Contracts:** `docs/plans/2026-08-24/phase1-rating-measurement-remediation.md`
  and `docs/plans/2026-08-24/phase2-minimum-viable-team-state-baseline.md`.
- **Approval / Status:** User explicitly authorized both on 2026-08-24. Both
  remain `In Progress` pending committed-code Preview artifact builds.
- **Blockers:** User-controlled commit is required before Preview writes; a
  protected 2026 observation remains reconstructed unless canonical parents
  carry genuine capture/effective timestamps.
- **Next:** Commit the implementation, then run the two Preview-only builders
  with exact immutable parent refs and run-stamped output URIs.

## Work Completed

- Added versioned Phase 1 v2 observation/snapshot contracts plus terminal
  adjusted measurement snapshots; v1 is now superseded for Phase 2 inputs.
- Corrected schedule/status alignment, season/game identity handling,
  season-to-date evidence scope, denominator-weighted adjustment, missing-PPA
  exposure, opportunity/field-position separation, quality propagation, and
  authentic source-time gating.
- Added the frozen Phase 2 configuration, component/team-state contracts,
  empirical-Bayes estimator, state audit, Preview-only CLI, executable lake
  schemas, and focused integration tests.
- Both builders require relevant paths to match their recorded Git commit;
  unrelated dirty worktree files do not affect that check.

## Validation

- [x] `tests/ratings/` — 56 passed
- [x] Full Python suite — 470 passed, 2 skipped
- [x] Ruff check
- [x] `contracts/validation.py`
- [x] Strict MkDocs build
- [x] `git diff --check`
- [ ] Preview v2 measurement build and audit — requires committed code
- [ ] Preview Phase 2 state build and audit — requires replacement Phase 1 refs

## Handoff Notes

- **Resume at:** After the user commits relevant implementation paths, invoke
  `build_rating_measurements.py --environment preview` with corrected run-
  stamped refs, then invoke `build_rating_team_states.py` with the passing v2
  refs and audit report.
- **Watch out for:** Do not pass v1 refs to the state builder; do not use a
  build timestamp as authentic 2026 source availability; neither workflow may
  target production.

**tags:** ["ratings", "phase1", "phase2", "empirical-bayes", "research-isolation"]
