# Documentation Alignment and Next Research Steps

- **Status:** Implemented
- **Created:** 2026-09-10
- **Planner:** Codex planning task
- **Approval source:** User explicitly approved the complete plan with “PLEASE IMPLEMENT THIS PLAN” on 2026-09-10.
- **Planning log:** `session_logs/2026-09-10/14-transformation-documentation-planning.md`
- **Implementation log:** `session_logs/2026-09-10/15-transformation-documentation-implementation.md`
- **Commit policy:** Separate plan checkpoint; user controls staging, commits, and pushes.

## Goal and execution boundary

Make project status and research authority accurate, then complete Phase 3 v2
as a benchmark before finalizing the possession-based rating methodology.

This contract authorizes documentation alignment and documentation-authority
test updates. The current planning task saves only this contract and its log;
a separate implementation task performs the edits and validation below.
Research execution remains in separate tasks under exact phase contracts.
Do not implement a new estimator, run Phase 3, publish artifacts, or change
production as part of this documentation contract.

## Current state and evidence

- Repair v2 is implemented and independently Preview-verified, as recorded in
  `session_logs/2026-09-09/01-data-first-repair-v2-implementation.md`.
- Phase 3 v2 code is committed, including compact tournament state at `ea91c9f`.
  Its active contract is [the September 10 compact-state replacement](phase3-v2-compact-tournament-state.md).
  Preview dry run, apply, independent verification, and idempotent rerun remain
  unchecked in its latest log. This planning assessment directly listed Preview
  R2 on September 10: both `phase3/v2/` and `phase4a/v2/` contained zero objects
  under `artifacts/research/data-first-football-v1/`.
- The inspected checkpoint is `7ef201e`; the tracked worktree was clean and
  `.opencode/` was the only untracked item. Recheck at implementation time.
- The September 10 operations log records Week 1 scored and Week 2 run
  `2026w2-43b25511a100` frozen with 49/49/49 coverage. Cite dated evidence;
  do not infer or repeat an unsupported exact Week 1 scoring timestamp.
- The 2025 V4 operational replay is complete. The September 10 shadow
  equivalence log records unchanged predictions for 100 W0–W2 games. Its formal
  pooled scoring verdict remains pending Week 2 close. These are V4 diagnostics,
  not successor progress or prospective evidence for a new rating design.

## Approved direction and authority

The user chose football meaning first: offense and defense ratings should
estimate scoring efficiency per possession against an average opponent under
standard conditions. Retain one rating per unit with uncertainty; passing,
rushing, explosiveness, and finishing are supporting diagnostics. Model
possession volume separately when translating efficiency into game scores.
Compare learned preseason priors with a simpler carryover baseline.

The user explicitly chose to finish the old Phase 3 tournament first. Its
selected core is benchmark evidence for the redesign, not automatic authority
for the possession-scoring estimator. The estimator, possession definition,
normalization, and scoring attribution are not yet specified or certified.

Use the data-first roadmap as the canonical status page, modeling requirements
as semantic authority, and dated contracts as execution authority. Preserve the
September 8 review's invalid-lineage prohibitions and historical findings.
Phase 4A–6 keep their original approval records but receive an explicit execution
hold pending methodology review. Do not mark them Superseded until replacement
contracts exist. This approved sequencing amendment does not alter Phase 3's
sealed computation or gates.

## Documentation implementation

### Current status and navigation

- Update `docs/planning/data-first-football-forecasting-roadmap.md` and
  `docs/plans/index.md` to one queue: Repair verified → Phase 3 v2 certification
  pending → methodology redesign → replacement implementation contracts.
  Link active Phase 3 entries directly to the September 10 contract; retain
  September 8/9 links only as historical or inherited-contract references.
- Update `README.md`, `AGENTS.md`, `docs/index.md`, and `.agent/CONTEXT.md`
  with a concise dated checkpoint and links to the canonical pages. Remove
  stale claims that repair is unexecuted or later phases may execute directly.
- Update `docs/planning/roadmap.md` and onboarding status to the dated Week 1
  scored / Week 2 frozen record. Separate operational diagnostics from ratings
  work and leave weekly procedures in the existing runbooks. Check
  `.codex/QUICKSTART.md` for current-status examples; label illustrative values
  as examples instead of treating them as live configuration.
- Add navigation for this contract where appropriate in `mkdocs.yml` and the
  contract index. Avoid copying the full research queue into every entry point.

### Modeling meaning and evaluation

- Put the agreed requirements first in `docs/modeling/rating_system_requirements.md`.
  Separate decided requirements, unresolved design decisions, and clearly labeled
  historical implementations. Preserve historical artifact IDs and claims in
  their original scope; remove their appearance of current execution authority.
- Update `docs/modeling/measurement_catalog.md` to distinguish certified existing
  measurements from proposed possession-scoring measurements. State that points
  per scoring opportunity is not points per possession and that plays per drive
  measures drive length, not clock tempo. Do not imply proposed data is available
  or validated merely because related drive fields exist.
- Update `docs/modeling/evaluation.md` and
  `docs/architecture/repository_boundaries.md` with the intended efficiency →
  possession volume → score forecast separation. Preserve temporal validation,
  uncertainty distinctions, market exclusion, and prospective evidence rules.
  Label existing Ridge/NB2 model-family and distribution rules as belonging to
  the earlier approved design under review, not the finalized new methodology.

### Contracts and historical records

- Add dated execution-hold notices to the September 8 Phase 4A, 4B, 5, and 6
  contracts. Preserve their Approved status and original approval source;
  state that the September 10 direction requires replacement/reaffirmation
  before execution. Update the September 8 authority-reset document with a
  dated subsequent-direction note without rewriting its original review.
- Record the user's choices and the sequencing amendment in
  `docs/decisions/decision_log.md`, linking this contract.
- Preserve historical session logs, artifact identities, and superseded plans.
  Do not perform a broad archive migration or change production runbooks unless
  a specific stale status/reference requires correction; operating behavior is
  outside scope.

## Subsequent task sequence

1. Complete this documentation implementation and its checks in a separate task.
2. Close the existing Phase 3 v2 benchmark under the September 10 compact-state
   contract unchanged: no-write Preview preflight, inspect counts and selection,
   apply from a matching clean committed checkpoint, independent verifier, and
   required idempotent rerun. Require 6,318 validation games, 142,960 compact
   feature rows, and 202,176 predictions. Record actual output identities and
   checksums; completion requires every gate in that contract, not counts alone.
3. In a dedicated planning task, finalize possession eligibility, scoring
   attribution, field-position normalization, opponent adjustment, rating scale,
   preseason priors, state updates, uncertainty, possession volume, and score
   translation. Resolve overtime, defensive/special-teams scores, clock-ending
   possessions, missing evidence, and FCS coverage. Produce a decision-complete
   specification before estimator implementation.
4. Issue replacement execution contracts for measurement certification, rating
   estimation, score forecasting, and prospective evaluation. Specify exact
   inputs/outputs, frozen comparisons, acceptance gates, and verified predecessor
   requirements. Supersede prior contracts only where actually replaced.
5. Implement sequentially: certify measurements → verify ratings → verify score
   forecasts → freeze the full candidate → collect prospective evidence. V4
   continues normal weekly operations. Update status after each verified gate.

Steps 2–5 are the handoff queue, not the definition of done for this documentation
task. No unresolved modeling decision is delegated to its documentation implementer.

## Interfaces, compatibility, and assumptions

- No production API, schema, database, model bundle, public prediction, or
  research computation changes. Only documentation and authority tests change.
- Preserve repaired data and reusable replay infrastructure. Finish Phase 3's
  existing mathematics and selection gates unchanged.
- Exclude 2020. Historical research remains reconstructed development evidence;
  preserve six qualifying prospective slates and separate promotion authority.
- Betting remains deferred. No new subscriptions, captures, or data writes.
- Preserve `.opencode/` and all unrelated work. Git operations remain user-controlled.

## Validation and acceptance

- Update `tests/test_data_first_documentation_authority.py` to verify the current
  Phase 3 link, repaired-foundation status, and Phase 4A–6 execution holds while
  retaining historical evidence and checksum checks. Distinguish links retained
  as history from links that authorize execution. Avoid tests that only enforce
  incidental prose formatting.
- Run `uv run pytest -q tests/test_data_first_documentation_authority.py`,
  `uv run mkdocs build --strict --quiet`, and `git diff --check`. Use scoped Ruff
  checks if the test file changes; no broad formatting.
- Review all changed active entry points for consistent status, next task,
  approved direction, and production boundaries. Verify local documentation
  links and that historical sections cannot be mistaken for the active queue.
- Check that possession-based capabilities are labeled proposed, with no
  invented measurement certification, estimator selection, or passing artifact.
- Save an implementation log with files, validation, evidence limits, and next
  handoff. Mark this contract Implemented only when documentation acceptance
  passes; Phase 3 completion remains a separate status.

## Risks and amendments

The main risk is confusing historical engineering completion with current
predictive eligibility, or turning an agreed direction into an invented
estimator specification. Preserve scope labels and explicit dependencies.
Material changes to modeling, timing, candidate grids, uncertainty, evaluation
thresholds, or production boundaries require a separately approved contract or
amendment before affected execution.

## Implementation closure (2026-09-10)

Documentation and authority-test implementation completed under
`session_logs/2026-09-10/15-transformation-documentation-implementation.md`.
Focused authority tests, scoped Ruff, strict MkDocs, and `git diff --check`
passed. This completion updates documentation authority only; Phase 3 v2
remains In Progress until its own Preview gates pass.
