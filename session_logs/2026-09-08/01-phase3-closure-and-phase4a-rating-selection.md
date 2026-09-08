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

- [x] Focused Phase 3/4A warning-as-error tests: 28 passed.
- [x] Full warning-as-error Python suite: 765 passed, 2 skipped.
- [x] Ruff lint: clean; all Phase 4A remediation files formatted.
- [x] Contracts validation: passed.
- [x] MkDocs strict: built (existing unlisted-page notices only).
- [x] `git diff --check`: clean.
- [x] First R2 Preview dry-run attempt used committed SHA
  `721ab60d1817ec1dd10d33426d59c889b30b31fb`, made no writes, and failed
  closed on the subsequently narrowed local floating-point-status wrapper.
- [ ] Corrected R2 warning-as-error dry run, apply, and independent remote
  verification remain pending the required user commit and clean tracked
  worktree.

## Amendments and Blockers

- The Phase 4A analytic-posterior amendment is user-authorized and recorded in
  the implementation contract.
- The first committed-SHA Preview dry run reached team-state composition and
  exposed object-dtype standard deviations after candidate concatenation. No
  R2 write was possible because the command was a dry run. The follow-up fixes
  coerce role uncertainty before propagation and normalize all-null optional
  state columns before concatenation; they require one additional user commit
  before retrying the immutable-run gate.
- The second dry run then rejected a Phase 2d schedule row absent from the
  certified Phase 3 measurement population. The runner now projects the
  schedule to the exact Phase 3 observation game keys before tournament
  evaluation, preserving Phase 3 as the sole population authority. It also
  normalizes nullable source-season state columns before concatenation. This
  follow-up remains dry-run-only and requires a further user commit before the
  next retry.
- The third dry run completed all 101,024 fold predictions and retained
  `rho_0_60__exposure`, but emitted Ridge overflow warnings from an underflowed
  `1e-8` fold feature scale. The rating path now uses the established `0.05`
  scale floor for fold-local standardization. This requires a final user commit
  and warning-free dry-run repeat before apply can be considered.
- The subsequent dry run still reported overflow, which means the underlying
  fold feature range—not only a near-zero scale—is unstable. Phase 4A now
  fails closed before Ridge fitting when a fold center, scale, or standardized
  feature is non-finite, retaining the offending feature's maximum magnitude
  in the error. This diagnostic guard must pass before any revised numerical
  treatment can be considered.
- Read-only range diagnostics then established that every candidate's offense
  and defense states remain roughly within -3 to +3. The actual cause is a
  pandas nullable-`Float64` to NumPy-`object` conversion at the Ridge boundary,
  despite finite standardized values. The bounded numerical-execution
  amendment now forces contiguous native `float64` feature/target matrices,
  promotes every Ridge numerical warning to contextual failure, and rejects
  non-finite predictions, coefficients, errors, and attribution evidence both
  before retention and in independent verification. It changes no modeling
  semantics and awaits a user commit before the required warning-as-error dry
  run.
- The first R2-backed warning-as-error retry reached native Ridge prediction
  and failed closed on a low-level `matmul` floating-point status created by an
  over-broad local `np.errstate(...="raise")` wrapper, not a `RuntimeWarning`
  or non-finite value. That wrapper is removed: Ridge warnings remain fatal,
  while the contractually required finite input/output checks continue to guard
  numerical integrity. The narrowed execution guard needs its own user commit
  before another clean-SHA dry run.

## Handoff Notes

- **Resume at:** After the user commits this numerical-execution remediation,
  run the Phase 4A dry run with `PYTHONWARNINGS=error` against the signed Phase
  3 manifest. Apply and independently verify immutable Preview artifacts only
  if it is warning-free with the established population counts.
- **Watch out for:** Preserve unrelated `.opencode/` work. Do not execute R2
  writes until the user has committed the exact code and the tracked worktree
  is clean.

**tags:** ["data-first", "phase3", "phase4a", "ratings"]
