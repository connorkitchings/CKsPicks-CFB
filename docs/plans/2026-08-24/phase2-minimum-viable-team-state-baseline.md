# Phase 2 — Minimum Viable Team-State Baseline

- **Status:** In Progress
- **Created:** 2026-08-24
- **Planner:** Sol
- **Approval source:** User explicitly authorized this exact plan on 2026-08-24.
- **Implementation log:** `session_logs/2026-08-24/03-phase1-remediation-and-phase2-implementation.md`
- **Commit policy:** Separate implementation commit required before Preview artifact materialization.

## Goal

Build an isolated empirical-Bayes successor state from corrected Phase 1
measurements. For every eligible pregame target and season terminal, emit
attributable offense, defense, overall-quality, and non-null uncertainty.
No prediction, market, V4, production, public, Neon, or publication interface
is introduced.

## Frozen Baseline

- Inputs are the exact v2 Phase 1 observation, season-to-date snapshot,
  terminal snapshot, and passing audit refs/checksums.
- Components are EPA/play, success rate, explosive rate, and points per scoring
  opportunity; each contributes 25% to offense and defense.
- Standardize separately by measurement and role with the preceding season's
  team-equal terminal mean and sample standard deviation, floored at EPA 0.05,
  success 0.02, explosive 0.01, and finishing 0.25. Use 2021 fallback
  `(center, scale)` values of `(0.00, 0.15)`, `(0.42, 0.06)`, `(0.10, 0.04)`,
  and `(4.00, 0.75)` respectively.
- Reverse defensive standardized values so higher is always better.
- Carry a returning team's terminal component state with `rho = 0.60`; use
  `mean = rho * terminal_mean` and
  `variance = rho^2 * terminal_variance + (1-rho^2)`. 2021 and unseen teams
  use zero mean and unit variance with a quality flag.
- Use equivalent prior exposure 100 for play measurements and 8 for finishing.
  Given prior variance `V0`, current exposure `N`, and standardized adjusted
  observation `z`, use prior precision `1/V0`, observation precision `N/k`,
  and their precision-weighted posterior. Missing/zero current evidence keeps
  the prior.
- Component uncertainty is posterior standard deviation. Unit and overall
  uncertainty use the conservative perfect-positive-correlation weighted sum.

## Interfaces and Workflow

- Add Preview-only immutable `rating_measurement_states_v1` and
  `rating_team_states_v1` datasets. Both include `state_kind` (`pregame` or
  `season_terminal`) and stable state IDs (`game:{season}:{game_id}` or
  `terminal:{season}:{team}`).
- Component rows carry cutoff, prior source, frozen scale, native and
  standardized observations, exposure, precision/weight decomposition,
  posterior state, quality flags, and exact Phase 1 lineage.
- Team rows carry offense/defense/overall means and uncertainty, completed-game
  count, aggregate observed-evidence weights, component count, quality flags,
  and full code/config/parent lineage.
- Process 2021–2026 chronologically. Build terminal states before using them
  as following-season priors. Only `pregame` rows may be consumed by Phase 3.
- Use an isolated config/package/CLI/audit. Refuse production targets, outputs
  outside the research prefix, ref mismatches, missing input coverage, and
  uncommitted relevant code. Preview catalog registration is explicit and
  optional.

## Validation and Exit Gate

- Test exact posterior algebra, constants, direction, weights, uncertainty,
  first-season/new-team priors, terminal carryover, season/future/same-kickoff
  isolation, missing measurement fallback, and component attribution.
- Test schema, checksums, immutable collision, deterministic rerun, code-commit
  identity, 2020/2019 exclusion, market rejection, and V4 isolation.
- Audit full team coverage, state distributions, evidence weights by game
  ordinal, uncertainty contraction, largest movements, missingness, and
  EPA/success correlation; do not evaluate prediction or market outcomes.
- Phase 2 is implemented only when the corrected Phase 1 artifact gate passes
  and state artifacts reproduce from the committed source. Otherwise this plan
  remains In Progress and no Phase 3 work begins.
