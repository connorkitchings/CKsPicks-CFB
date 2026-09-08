# Transformation Documentation Reset and Revised Phase 3–6 Sequence

> **Superseded 2026-09-08.** The [review and corrective contracts](../2026-09-08/transformation-review-and-authority-reset.md) replace this sequence. Historical decisions below are preserved.

- **Status:** Superseded
- **Created:** 2026-09-06
- **Planner:** Sol
- **Approval source:** User approved the proposed plan and requested that it be documented on 2026-09-06.
- **Implementation log:** `session_logs/2026-09-07/01-phase3-plus-documentation-resequence.md`
- **Commit policy:** Separate plan commit

## Goal

Update the repository's active authority to reflect that Phases 0–2 are
complete, preserve superseded evidence as historical records, and replace the
existing Phase 3–6 contracts with a sequence that removes avoidable staged
selection dependencies.

The revised sequence is:

1. Phase 3 certifies measurement meaning and selects the shared football core.
2. Phase 4A jointly selects the context-free rating prior and updater.
3. Phase 4B selects at most one target-specific context family using the frozen
   rating and a canonical forecast bridge.
4. Phase 5 selects final spread and total forecast formulations.
5. Phase 6 collects prospective frozen evidence and authentic market
   comparisons.
6. Phase 7 is planned only if Phase 6 evidence supports promotion review.

V4, production publication, Neon activation, betting policy, and the weekly
operating workflow remain unchanged.

## Current State

Phases 0–2 are complete. Phase 2d published a checksum-valid audit,
automation-admission artifact, and 70-ref core eligibility handoff. Phase 2e
bound 63 checksum-valid immutable Bronze captures and registered six Preview
datasets for recruiting, returning production, coaching, roster continuity,
strictly lagged polls, and reconstructed market references. Phase 2e evidence
is reconstructed research evidence and is activation-ineligible.

The active documentation still contains contradictory Phase 2 status text and
the existing Phase 3 contract selects target context through a provisional
rating updater and forecast head. Phase 4 later reselects the updater, and
Phase 5 later reselects the forecast formulation. That staging can make context
retention depend on scaffolding that is subsequently replaced.

The corrected Phase 1 dispositions remain authoritative. Repairing source data
does not retroactively validate historical R1/R2, direct, candidate-v1, or NB2
modeling results.

## Proposed Approach

First reconcile all active documentation and publish replacement phase
contracts while preserving historical documents with supersession banners.
Then execute the revised phases as separate Terra tasks. Phase 3 remains focused
on football measurement validity and the shared core. Phase 4 is divided into a
context-free rating tournament and a target-context tournament. Phase 5 treats
the resulting simple target baselines as the references for final forecast
selection.

Phase 4A evaluates its two priors across all four updaters as one bounded
eight-candidate grid. Phase 3 uses its original simple scaffold for core
selection and adds a predeclared recency sensitivity gate so the selected core
cannot depend materially on one temporary updater.

## Scope

### Included

- Active documentation reconciliation and explicit historical supersession.
- Replacement Phase 3, 4A, 4B, 5, and 6 contracts.
- Phase 3 measurement reconstruction, independent certification, and shared
  core selection.
- Context-free rating selection, target-context selection, forecast selection,
  prospective evaluation, and post-selection market diagnostics.
- All completed regular and postseason games involving at least one FBS team
  in 2015–2019 and 2021–2025.

### Excluded

- Changes to V4, production bundles, Neon activation, publication, weekly
  operations, or rollback behavior.
- 2020 data in any historical boundary.
- Market-derived model features, CLV claims from reconstructed lines, betting
  decisions, staking, or bankroll policy.
- Automatic promotion after Phase 6.

## Affected Components and Contracts

- Active repository, data, modeling, evaluation, roadmap, and contract-index
  documentation.
- The current Phase 3–6 contracts, which become superseded historical records.
- New Phase 3–6 research runners, configurations, schemas, and immutable
  Preview artifacts when their replacement contracts are executed.
- The Phase 2d core and Phase 2e auxiliary eligibility manifests, which remain
  immutable inputs.

## Implementation Tasks

### Task 1 — Reconcile documentation authority

**Changes:**

- Mark Phases 0, 1, and 2 implemented and closed throughout active authority.
- Add one Phase 0–2 evidence table with the Phase 2d audit,
  automation-admission, 70-ref eligibility handoff, Phase 2e 63-capture set,
  six auxiliary datasets, checksums, code bindings, timing classes, permitted
  uses, and `activation_eligible: false`.
- Identify the defective eligibility artifact as superseded and the failed
  partial Phase 2e apply as unregistered diagnostic evidence.
- Correct returning-production Bronze count to 1,300 and betting-line Bronze
  count to 26,844, reconciling lower compatibility-projection counts.
- Remove the obsolete 2016–2018 play-gap claim and describe game statistics as
  reconciliation evidence.
- Preserve exact Phase 1 result dispositions. Add supersession banners and
  current-authority links to historical plans and reports without rewriting
  their findings or modifying session logs.
- Update navigation and links so the revised roadmap and replacement contracts
  are the sole active transformation path.

**Acceptance criteria:**

- Active pages agree on phase status, chronology, populations, artifact
  identities, 2020 exclusion, reconstructed-only restrictions, and V4
  isolation.
- No active page presents a historical result as validated by the Phase 2 redo.

### Task 2 — Replace Phase 3 with measurement certification and core selection

**Changes:**

- Consume only the signed, checksum-valid Phase 2d core eligibility manifest
  and its exact 70 refs.
- Rebuild and independently verify EPA/PPA per play, success rate, 20-yard
  explosiveness, scoring-opportunity efficiency, field position, pace,
  turnovers, pass/rush classification, and four-iteration opponent adjustment.
- Preserve every eligible FBS-involved game. Missing evidence receives
  fold-local fallback values, maximum training-fold uncertainty, reasons, and
  indicators.
- Compare `epa_only`, the equal-weight four-measure core, four leave-one-out
  cores, equal pass/rush EPA, and the split-EPA quality core.
- Rank using `rho=0.60`, the exposure-weighted updater, and fold-local Ridge
  `alpha=10`.
- Add a sensitivity gate using `rho=0.60`, recency half-life 4, and the same
  Ridge head. A candidate must pass the primary 0.5% pooled-improvement,
  90% paired-bootstrap, coverage, and 5% seasonal-regression gates and may not
  regress more than 0.5% versus EPA-only under the sensitivity scaffold.
- Select the fewest-component candidate within 0.5% of the best passing result;
  otherwise retain EPA-only.
- Publish definitions, observations, adjusted measurements, fold predictions,
  attribution, coverage/fallback, exclusions, and a retained-core manifest.
  Phase 3 selects no auxiliary context.

**Acceptance criteria:**

- Measurement meaning, numerators, denominators, exposure, reconciliation,
  timing, adjustment, population, and fallback behavior pass independent
  verification.
- Source or definition defects return through a new Phase 2 artifact version
  and block dependent work.

### Task 3 — Add Phase 4A context-free rating selection

**Changes:**

- Consume the frozen Phase 3 core and evaluate the full eight-combination grid:
  neutral or fixed annual `rho=0.60` prior crossed with exposure weighting or
  recency half-lives 2, 4, and 8.
- Use a fixed fold-local Ridge `alpha=10` translation head and select one shared
  offense/defense rating from combined margin and total evidence.
- Require at least 0.5% pooled improvement over the `rho=0.60` exposure
  reference, a 90% paired-bootstrap interval excluding zero, equal coverage,
  and no target-season regression above 5%.
- Prefer the least complex candidate within 0.5% of the best passing result;
  otherwise retain the reference.
- Estimate uncertainty chronologically and preserve attribution, exposure,
  movement, completed games, effective time, and fallbacks. Use eligible named
  FCS history when available and a preceding-data-only partially pooled fallback
  otherwise.
- Exclude Phase 2e auxiliary evidence from every rating prior.

**Acceptance criteria:**

- All eight candidates use identical populations and folds.
- The selected rating has reproducible pregame state, uncertainty, and fallback
  behavior for first games, byes, sparse teams, FBS–FCS games, and the
  2019-to-2021 transition.

### Task 4 — Add Phase 4B target-context selection

**Changes:**

- Consume the Phase 4A rating, Phase 3 contextual measurements, and Phase 2e
  auxiliary eligibility manifest.
- Freeze the Phase 4A Ridge `alpha=10` head as the canonical simple forecast
  bridge.
- Test field position, pace, turnovers, recruiting, returning production,
  coaching, roster continuity, and strictly lagged AP/Coaches polls one family
  at a time for margin and total.
- Fit every transform and replacement inside the training fold. Enforce
  `poll_week < game_week`, structural roster and recruiting fallbacks, explicit
  missing indicators, and complete population retention.
- Retain at most one family per target. Require a 0.5% pooled MAE improvement,
  a 90% paired-bootstrap interval excluding zero, no coverage loss, and no
  validation-season regression above 5%.
- Choose the fewest-feature family within 0.5% of the best passing family;
  otherwise retain no context.
- Freeze the resulting simple margin and total baselines for Phase 5. Exclude
  reconstructed market references entirely.

**Acceptance criteria:**

- No context family enters ratings or causes a game to disappear.
- Target choices, fallbacks, exclusions, and complete evidence are sealed under
  immutable identities.

### Task 5 — Replace Phase 5 forecast selection

**Changes:**

- Consume the Phase 4A rating and exact Phase 4B target baselines and context
  choices.
- Compare rating-based Ridge margin/total, Ridge team scores, direct
  football-core Ridge, and a newly rebuilt NB2 score candidate. Historical NB2
  results provide no validated performance claim.
- Use Ridge alphas `{0.1, 1, 10, 100}` with fold-local standardization. NB2 must
  pass current-lineage, finite-mean, uncertainty, and population checks before
  evaluation.
- Supply each candidate with the frozen Phase 4B target context. Context-free
  ablations are diagnostic and cannot reopen context selection.
- Select spread and total separately. Require MAE and CRPS within 1% of the
  simple reference, no seasonal MAE regression above 5%, and a 90% paired
  bootstrap interval excluding zero before claiming an improvement of at least
  0.5%.
- Prefer the simplest candidate within 0.5% of the best passing result. Retain
  the Phase 4B baseline if no challenger passes.
- After selection, publish a separate reconstructed-market diagnostic covering
  sign verification, coverage, forecast-versus-line error, and disagreement.
  It cannot affect selection or be described as CLV.

**Acceptance criteria:**

- All candidates use identical chronological folds and game populations.
- One immutable spread candidate and one immutable total candidate, or their
  simple references, are ready for prospective freezing.

### Task 6 — Replace Phase 6 and define the conditional Phase 7 boundary

**Changes:**

- Freeze candidate and V4 predictions before kickoff, targeting T-2h and
  requiring at least T-1h before the slate's first kickoff.
- Require six completed normal-coverage slates containing at least 40 games.
  Week 0 and all weeks before the candidate freeze are ineligible.
- Score finalized outcomes after at least 24 hours. Any candidate change starts
  a new evidence window.
- Compare authentic prediction-time and closing quotes only after football
  evaluation, with exact quote lineage and paired populations.
- Permit Phase 6 to recommend retaining V4, continuing shadow evidence, or
  drafting Phase 7. Phase 7 remains a separate promotion and operational
  readiness contract.

**Acceptance criteria:**

- No freeze is backdated, no historical reconstructed line is treated as
  prospective evidence, and no Phase 6 result activates or publishes a model.

## Public Interfaces and Safeguards

- Phase 3: `--core-eligibility-uri`.
- Phase 4A: `--phase3-retained-uri`.
- Phase 4B: `--phase4-rating-uri` and `--auxiliary-eligibility-uri`.
- Phase 5: `--phase4-rating-uri` and `--phase4b-context-uri`.
- Phase 6: `--phase5-candidate-uri`.
- Preserve Phase 3 schema version 1 because no Phase 3 artifact has been
  published. Introduce distinct version-1 schemas for Phase 4 rating selection,
  Phase 4B context selection, Phase 5 candidates/predictions, and Phase 6
  freezes/evaluation.
- Dry runs write nothing. Apply runs require Preview, a clean tracked worktree,
  exact committed code SHA, signed checksum-valid parents, and immutable output
  identities.
- Reject 2020, future information, markets as features, duplicate games,
  nonfinite outputs, unsigned or wrong-role manifests, code-SHA mismatches, and
  silent row loss.

## Testing Strategy

- Add documentation checks for reopened Phase 2 language, obsolete play-gap
  claims, incorrect inventory totals, and active links to superseded contracts.
- For each implementation phase, test chronology, exact parent membership,
  checksum drift, duplicate keys, 2020 rejection, fold-local fitting,
  population preservation, deterministic identities, immutable collisions,
  bootstrap units, thresholds, and fallback cohorts.
- Run focused affected tests plus the full warning-as-error Python suite with
  coverage, Ruff, contracts validation, strict MkDocs, repository-boundary and
  V4 checks, and `git diff --check` before closing each phase.

## Risks and Edge Cases

- Predictive measurement value depends partly on the evaluation scaffold. The
  Phase 3 sensitivity gate limits this dependency without turning Phase 3 into
  the rating tournament.
- Phase 4B context may interact differently with Phase 5 challengers. Context is
  frozen before Phase 5; ablations expose the interaction without reopening the
  search.
- Reconstructed auxiliary evidence supports historical research only. It cannot
  establish protected timing, activate a model, or satisfy prospective market
  requirements.
- Historical winners remain immutable evidence but cannot enter the revised
  sequence without being rebuilt and evaluated under current lineage.
- Failed or inconclusive candidates remain diagnostics. Candidate grids and
  thresholds are not expanded after outcomes are inspected.

## Definition of Done

- [ ] Active documentation consistently closes Phases 0–2 and identifies exact
  authoritative evidence.
- [ ] Historical plans and reports retain their content with clear supersession
  banners.
- [ ] Replacement Phase 3, 4A, 4B, 5, and 6 contracts are approved and linked as
  the sole active sequence.
- [ ] Each phase completes its acceptance criteria and required validation in a
  separate Terra task.
- [ ] Phase 6 produces a retain, continue, or Phase 7 planning recommendation.
- [ ] V4 and production remain unchanged.
- [ ] Documentation and implementation session logs are complete.
- [ ] This plan is marked `Implemented` only after the full sequence above is
  complete.

## Amendments

New measurement or model families, candidate grids, folds, thresholds,
bootstrap units, opponent-adjustment behavior, context stacking, rating priors
using auxiliary evidence, market-informed modeling, promotion, or publication
require a revised approved contract.
