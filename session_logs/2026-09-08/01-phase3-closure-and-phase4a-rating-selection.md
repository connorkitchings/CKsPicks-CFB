# Session: Phase 3 Closure and Phase 4A Rating Selection

## TL;DR

- **Worked On:** Closed Phase 3 documentation status and began the approved
  Phase 4A context-free rating-selection contract.
- **Outcome:** Phase 3 is recorded as implemented with the precise selection
  result; Phase 4A implementation is in progress and remains Preview-only.
- **Plan Contract:** `docs/plans/2026-09-07/02-phase4a-context-free-rating-selection.md`
- **Approval / Status:** User explicitly authorized implementation on
  2026-09-08; contract status is `In Progress`.
- **Blockers:** Remote dry run/apply requires a clean tracked worktree at a
  committed matching code SHA. The user controls the required commit.
- **Next:** Implement and locally validate the Phase 4A contracts, rating grid,
  runner, and independent verifier before preparing the clean-SHA remote run.

## Context and Decisions

- The sole Phase 4A parent is the signed Phase 3 retained-core manifest.
- Phase 2e context, markets, V4, production, Neon, and publication are not
  inputs or outputs in this phase.
- Uncertainty uses the user-selected analytic posterior with a 100-play
  equivalent exposure and no residual floor or volatility design.

## Work Completed

- Reconciled Phase 3 plan, roadmap, authority index, and session-log status.
- Corrected the Phase 3 selection wording: no challenger passed all gates;
  point-MAE improvements alone did not satisfy the paired-bootstrap gate.
- Recorded the decision-complete Phase 4A implementation amendment.
- Implemented the sealed eight-candidate EPA-only rating grid, analytic
  posterior, role-composed team state, FCS fallback, fold-local Ridge
  tournament, selection gates, immutable schemas, Preview-only runner, and
  independent verifier.

## Files Modified

- `docs/plans/2026-09-07/01-phase3-measurement-certification-and-core-selection.md` - finalized lifecycle status and evidence wording.
- `docs/plans/2026-09-07/02-phase4a-context-free-rating-selection.md` - started implementation and recorded selected technical decisions.
- `docs/plans/index.md`, `docs/planning/roadmap.md`, `docs/planning/data-first-football-forecasting-roadmap.md`, `AGENTS.md` - synchronized current authority.
- `tests/test_data_first_documentation_authority.py` - made the authority assertion robust to editorial line wrapping.
- `conf/research/data_first_football_v1/phase4a_rating_v1.yaml` - sealed Phase 4A candidate and selection settings.
- `src/cks_picks_cfb/data/data_first_phase4a.py`, `src/cks_picks_cfb/ratings/phase4a.py` - contracts and deterministic rating/tournament logic.
- `scripts/research/run_data_first_phase4a.py`, `scripts/research/verify_data_first_phase4a.py` - Preview-only immutable execution and independent verification.
- `src/cks_picks_cfb/data/schema_contracts.py`, `tests/test_data_first_phase4a.py` - executable artifact schemas and focused behavior coverage.

## Validation

- [x] Focused Phase 3/4A/documentation tests: 22 passed.
- [x] Full warning-as-error Python suite: 756 passed, 2 skipped.
- [x] Ruff: clean.
- [x] Contracts validation: passed.
- [x] MkDocs strict: built (existing unlisted-page notices only).
- [x] `git diff --check`: clean.
- [ ] R2 dry run/apply and independent remote verification pending the required
  user commit and clean tracked worktree.

## Amendments and Blockers

- The Phase 4A analytic-posterior amendment is user-authorized and recorded in
  the implementation contract.

## Handoff Notes

- **Resume at:** After the user commits this scoped work, run the Phase 4A dry
  run against the signed Phase 3 manifest, then apply and independently verify
  its immutable Preview artifacts.
- **Watch out for:** Preserve unrelated `.opencode/` work. Do not execute R2
  writes until the user has committed the exact code and the tracked worktree
  is clean.

**tags:** ["data-first", "phase3", "phase4a", "ratings"]
