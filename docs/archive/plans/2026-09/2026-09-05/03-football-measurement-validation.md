# Phase 3: Football Measurement Validation

- **Status:** Superseded
- **Created:** 2026-09-05
- **Planner:** Sol
- **Approval source:** User approved the original data-first plan on 2026-09-05 and the staged Phase 3 redesign on 2026-09-06.
- **Implementation log:** Pending corrected Phase 2 eligibility handoff
- **Commit policy:** Separate plan and implementation/evidence commits

> **Superseded 2026-09-07.** This contract is retained as historical planning
> evidence. Its Phase 3C target-context selection moved to the independent
> [Phase 4B target-context selection](../2026-09-07/03-phase4b-target-context-selection.md)
> contract so that context cannot be selected through a rating updater or
> forecast head that is later replaced. Execute
> [Phase 3 measurement certification and core selection](../2026-09-07/01-phase3-measurement-certification-and-core-selection.md)
> instead.

## Goal

Determine which football measurements provide reliable, distinct forecast
information before Phase 4 selects a rating system. Freeze one shared
offense/defense quality set plus any separately justified spread- or
total-specific context. Adding information is not required.

## Current State

Phase 2c contains ten reconstructed development seasons: 2015–2019 and
2021–2025, with 2020 forbidden. The checksum-valid Phase 2d replacement
eligibility handoff is published under the Phase 2d repair contract, and the
separate Phase 2e manifest admits reconstructed-only auxiliary context.
Existing rating measurement code is reusable reference behavior,
but its 2021–2025 artifacts and historical evaluation head are not Phase 3
inputs: the older head excludes 2025 and can silently omit games without a
fallback row.

The four quality measurements are EPA/PPA per play, success rate, explosive
play rate at 20 yards, and points per scoring opportunity. Average starting
field position, plays per drive, and turnover rate are context measurements.
Opponent adjustment occurs once at measurement level using four fixed,
league-centered additive iterations.

## Proposed Approach

Phase 3 has three sealed stages. Phase 3A reconstructs and independently checks
measurement meaning. Phase 3B compares a bounded shared quality core with one
fixed updater and forecast head. Phase 3C tests context one family at a time,
separately by target. Phase 3A/3B require Phase 2d; Phase 3C additionally
requires the reconstructed-only Phase 2e auxiliary eligibility manifest.

## Scope

### Included

- All completed regular and postseason games involving at least one FBS team.
- Measurement construction, four-iteration adjustment, fixed comparison state,
  chronological forecasts, attribution, coverage, fallback, and retention.
- Explicit FBS-FBS/FBS-FCS, first-game, unequal-experience, overtime, and
  missing-input cohorts.

### Excluded

- V4 or production changes; market inputs; Phase 4 rating selection; special
  teams without admitted evidence; provider purchases; model promotion.
- Market references as model inputs, selection metrics, or CLV evidence.

## Interfaces and Fixed Design

- Inputs are only the checksum-valid replacement Phase 2 eligibility manifest
  and its exact `phase3_input_refs`.
- New outputs use `data_first_phase3_measurement_observations_v1`,
  `data_first_phase3_adjusted_measurements_v1`,
  `data_first_phase3_fold_predictions_v1`, and
  `data_first_phase3_retained_measurements_v1` beneath
  `artifacts/research/data-first-football-v1/phase3/`.
- Every measurement row records season, week, game, team, role, numerator,
  denominator, exposure, raw value, adjusted value/iteration, eligible-event
  rule, missing reason, timing class, and exact parents.
- Chronological validation folds train on all permitted earlier seasons and
  validate 2018, 2019, 2021, 2022, 2023, 2024, and 2025. The 2019→2021 gap is
  two elapsed years; 2020 contributes no rows, labels, priors, or transforms.
- The comparison updater is fixed: neutral state for the first available season,
  0.60 annual terminal carryover thereafter, and the existing exposure-weighted
  empirical-Bayes update. It is evaluation scaffolding, not the Phase 4 winner.
- The forecast head is fold-local Ridge with alpha 10 and training-fold
  standardization. Margin and total are fitted separately from home/away
  offense and defense state means plus an intercept. No team identity, market,
  future result, or second opponent adjustment is allowed.
- Missing team/component evidence produces a row using the training-fold role
  mean, maximum observed training-fold uncertainty, and an explicit fallback
  flag. It never disappears from aggregate evaluation. FBS opponents without
  eligible history use the same rule and are reported separately.

## Implementation Tasks

### 3A — Reproduce and validate measurement meaning

1. Add a Phase 3 configuration and runner that reject invalid eligibility
   signatures, unexpected refs, 2020, market data, non-Preview routing, dirty
   apply worktrees, or code-SHA mismatch.
2. Rebuild the seven baseline measurements from Phase 2 inputs under new
   identities. Eligible plays require `is_drive_play == 1` and `garbage == 0`;
   success excludes null-success plays from both numerator and denominator;
   explosiveness uses `yards_gained >= 20`; PPSO uses the reconciled score
   stream and opportunities; zero exposure stays null with a reason.
3. Independently recompute sampled and aggregate numerators/denominators,
   offense-defense symmetry, score-stream reconciliation, overtime handling,
   and four-iteration opponent adjustment. Preserve iteration 0 and 4.
4. Build audited pass/rush EPA components using the canonical play-type
   classification. Ambiguous or excluded plays remain counted in coverage and
   receive a reason; they are never silently assigned.
5. If source or definition correctness fails, publish diagnostics and return the
   defect through Phase 2 versioning. Phase 3B remains blocked.

### 3B — Compare the shared quality core

1. Freeze these candidates before outcomes are evaluated:
   `epa_only`; `quality_core_equal` (four quality measures at 0.25 each);
   four leave-one-out variants with remaining weights renormalized equally;
   `epa_pass_rush` (pass/rush EPA equally weighted); and
   `quality_core_epa_split` (pass/rush EPA at 0.125 each plus the other three
   quality measures at 0.25 each).
2. Build identical pregame states and predictions for every candidate and fold.
   Fit standardization, carryover inputs, updater inputs, and Ridge only from
   seasons preceding the validation season.
3. Evaluate unique games on identical candidate populations. Report margin and
   total MAE, RMSE, bias, game counts, fallback counts, and paired error deltas
   overall and by season, population, season type, first-game involvement,
   unequal experience, and overtime.
4. Use 2,000 fixed-seed paired hierarchical bootstrap replicates, resampling
   seasons and then week blocks while keeping every game's candidates and
   targets together.
5. Rank shared-core candidates by the mean of margin and total MAE relative to
   `epa_only`. An addition has clear value only when it improves the pooled
   score by at least 0.5%, its 90% paired bootstrap interval excludes zero, it
   loses no coverage, and neither target has a validation-season MAE regression
   above 5%. Choose the fewest components within 0.5% of the best eligible
   score; otherwise retain `epa_only`.

### 3C — Evaluate admitted context by target

1. Starting from the selected shared core, test average starting field position,
   plays per drive, and turnover rate one family at a time as forecast-head
   context. Do not add them to the offense/defense quality composite.
2. Retain context independently for margin or total only when that target gains
   at least 0.5% pooled MAE, its 90% paired bootstrap interval excludes zero,
   coverage does not fall, and no validation season regresses by more than 5%.
   Do not search combinations after a one-family result.
3. Test recruiting, returning production, coaching, roster continuity, and
   strictly lagged AP/Coaches polls from the Phase 2e manifest alongside field
   position, pace, and turnovers. Polls may use only `poll_week < game_week`;
   the first available game keeps an explicit fallback.
4. Retain at most one context family per target. Rank passing families by that
   target's pooled MAE and choose the fewest-feature family within 0.5% of the
   best. Do not stack context families or search combinations.
5. Seal the retained manifest with the shared core, target-specific context,
   exact refs/checksums, candidate registry, folds, metrics, bootstrap seed,
   fallback rules, exclusions, and authorization flags set false for production
   activation and model selection outside Phase 4.

## Testing Strategy

- Unit-test numerator/denominator definitions, pass/rush classification, zero
  exposure, score reconciliation, adjustment centering, and deterministic IDs.
- Test fold-local fitting and explicit rejection of future, 2020, market, and
  outcome-derived inputs; cover the two-year gap and first-game priors.
- Test that missing features, FBS-FCS games, unequal experience, postseason,
  and overtime remain in predictions with explicit cohort/fallback flags.
- Test paired bootstrap units, candidate/population equality, thresholds,
  simplicity tie-breaks, deterministic reruns, and immutable collisions.
- Run focused Phase 2/3 and rating tests, the full warning-as-error Python suite
  with coverage, Ruff, contracts validation, MkDocs, repository-boundary/V4
  checks, and `git diff --check`.

## Risks and Failure Behavior

- Measurement-definition or source defects return to Phase 2 and block dependent
  comparisons; thresholds are not relaxed after results.
- Correlated measures may look useful alone while adding no distinct value;
  paired leave-one-out and bootstrap evidence governs retention.
- The fixed updater/head can affect measured utility. Phase 3 records this
  limitation, and Phase 4 may select a different rating method without changing
  Phase 3 measurement definitions.
- Failed and inconclusive candidates remain immutable diagnostics and cannot
  expand the Phase 4 feature set.

## Definition of Done

- [ ] Corrected Phase 2 eligibility is verified before any Phase 3 apply run.
- [ ] Phase 3A definitions and four-iteration adjustment pass independent checks.
- [ ] Phase 3B freezes one shared quality set under the stated rules.
- [ ] Phase 3C freezes any target-specific context and explicit deferred families.
- [ ] All games and fallback cohorts reconcile to the independent denominator.
- [ ] Artifacts, tests, documentation, session log, and deterministic rerun pass.
- [ ] V4 and production remain unchanged.

## Amendments

New candidate families, grids, folds, updater/head behavior, retention gates,
bootstrap units, opponent-adjustment policy, or admission beyond the signed
Phase 2e reconstructed-only context requires a revised approved plan.
