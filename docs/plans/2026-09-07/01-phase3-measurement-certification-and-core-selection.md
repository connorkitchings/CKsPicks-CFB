# Phase 3: Measurement Certification and Shared Core Selection

- **Status:** Implemented
- **Created:** 2026-09-07
- **Planner:** Sol
- **Approval source:** User-approved 2026-09-06 resequencing contract, `docs/plans/2026-09-06/06-transformation-documentation-and-phase3-plus-resequence.md`.
- **Implementation log:** `session_logs/2026-09-07/03-phase3-apply-and-verification.md`
- **Commit policy:** Separate plan and implementation/evidence commits; user executes Git operations.

## Goal

Certify the meaning and reproducibility of football measurements, then freeze
one small shared offense/defense quality core. Phase 3 selects no target
context, rating prior, updater, or final forecast formulation.

## Current State

The sole core parent is the signed Phase 2d eligibility artifact:

`artifacts/research/data-first-football-v1/phase2/recertification/runs/2026-09-06T2358Z-phase2d-recertification-v2/eligibility-manifest.json`

Its SHA-256 is
`cdeeea01035c9108491a42b2e29a9e6033cdd7781d1ab837df8e411b29afe760` and it
contains exactly 70 Phase 3 refs. All games involving at least one FBS team in
2015–2019 and 2021–2025 remain in scope; 2020 is forbidden. Phase 2e auxiliary
evidence is intentionally not an input to this phase.

## Proposed Approach

Rebuild the seven football measurements under new Preview-only identities,
independently certify their definitions and four-iteration adjustment, then
compare a predeclared quality-core registry through a fixed scaffold. The
primary scaffold is `rho=0.60`, the existing exposure-weighted updater, and
fold-local standardized Ridge with `alpha=10`; a four-game recency-half-life
sensitivity gate prevents a core from depending materially on that temporary
updater.

## Interfaces and Safeguards

- CLI input: `--core-eligibility-uri`; reject any unsigned, wrong-role,
  checksum-mismatched, unexpected, or non-70-ref parent.
- Outputs beneath `artifacts/research/data-first-football-v1/phase3/` use
  version-1 schemas for observations, adjusted measurements, fold predictions,
  attribution/coverage, and the retained-core manifest.
- Measurement rows retain season, week, game, team, role, numerator,
  denominator, exposure, raw and adjusted values, iteration, timing, parent
  identity, and explicit missing/fallback reason.
- Dry runs write nothing. Apply runs require Preview, clean tracked state,
  committed matching code SHA, and immutable non-colliding identities.
- Reject 2020, future information, market data, duplicate games, nonfinite
  values, and silent population loss. V4, production, Neon activation, and
  publication remain out of scope.

## Implementation Tasks

### Task 1 — Reconstruct and certify measurements

- Rebuild EPA/PPA per play, success rate, 20-yard explosive rate, points per
  scoring opportunity, average starting field position, plays per drive, and
  turnover rate from the exact Phase 2d refs.
- Require `is_drive_play == 1` and `garbage == 0`; exclude null-success plays
  from both success numerator and denominator; use `yards_gained >= 20` for
  explosiveness; preserve null zero-exposure values with a reason.
- Reconcile score streams and overtime; independently recompute sampled and
  aggregate numerators/denominators, offense/defense symmetry, and league
  centering across four additive opponent-adjustment iterations. Retain
  iterations zero and four.
- Produce audited pass/rush EPA with canonical classification. Ambiguous or
  excluded plays remain covered with a reason rather than being assigned.

### Task 2 — Select the shared quality core

- Freeze and evaluate `epa_only`, equal-weight four-measure core, each of its
  four leave-one-out variants, equal pass/rush EPA, and split-EPA plus the
  remaining three quality measures.
- Use expanding folds validating 2018, 2019, 2021, 2022, 2023, 2024, and 2025;
  all fitting, standardization, carryover, and Ridge estimation use only prior
  seasons. The 2019→2021 transition is a two-year gap.
- Keep every eligible game. Missing evidence uses a training-fold role mean,
  maximum observed training-fold uncertainty, and a reported fallback flag.
- Primary ranking is mean margin/total MAE relative to EPA-only. A candidate
  must improve pooled score by at least 0.5%, have a 90% paired hierarchical
  bootstrap interval excluding zero, retain coverage, and avoid any target-season
  MAE regression over 5%.
- Run the same gate with four-game recency weighting; a primary passer may not
  regress more than 0.5% versus EPA-only in sensitivity. Select the fewest
  components within 0.5% of the best passing result, else retain EPA-only.

## Validation

- Unit-test definitions, pass/rush classification, zero exposure, reconciliation,
  adjustment centering, deterministic identities, and rejected parents.
- Test fold-local fitting, population equality, fallback cohorts, 2020/future/
  market rejection, bootstrap units, thresholds, tie-breaking, and immutable
  collision behavior.
- Run focused Phase 2/3 tests, warning-as-error Python suite with coverage,
  Ruff, contracts validation, strict MkDocs, V4/repository-boundary checks, and
  `git diff --check`.

## Definition of Done

- [x] Signed Phase 2d lineage is independently verified before apply.
- [x] Measurement definitions and adjustment pass independent certification.
- [x] One retained shared core (or EPA-only) is frozen with complete evidence.
- [x] No auxiliary context, rating selection, or production action occurs.
- [x] Artifacts, tests, documentation, and a session log are complete.

## Completion Evidence

- **Run identity:** `phase3-v1-20260907T1500Z`
- **Manifest URI:** `artifacts/research/data-first-football-v1/phase3/runs/phase3-v1-20260907T1500Z/retained-core-manifest.json`
- **Manifest raw SHA-256:** `c8bc1ebd8a369c59cf298844dfdb2167baaa17dc72a3b29ceebd119eeacaf234`
- **Code SHA:** `6addf437e7d76f5e39f198c41acd47c4e9b2c5b4`
- **Selected candidate:** `epa_only` (no challenger passed every predeclared
  gate; some improved point MAE but their 90% paired-bootstrap intervals did
  not exclude zero)
- **Output rows:** 302,702 observations, 1,210,808 adjusted measurements, 202,048 fold predictions, 8 attribution rows
- **Independent verification:** passed (`scripts/research/verify_data_first_phase3.py`)
- **Quality gates:** 750 tests passed, ruff clean, contracts valid, mkdocs strict built

## Amendments

Any measurement family, candidate, fold, updater, threshold, bootstrap unit,
or opponent-adjustment change requires a revised approved plan.

- **2026-09-07 implementation note:** The first committed dry run exposed that
  `fbs_involved_games` carries informational score columns in addition to the
  authoritative `game_outcomes` parent. The runner now projects the schedule
  to identity, timing, and team columns before joining outcome targets. This
  resolves a mechanical column-name collision without changing inputs,
  population, targets, candidates, folds, gates, or output contracts.
