# Phase 2 — Minimum Viable Team-State Baseline

- **Status:** Implemented
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

## Implementation Record

Executed on 2026-08-25 (session log
`session_logs/2026-08-24/04-phase1-phase2-completion.md`).

- Code (committed at `cba1577`/`fed8c68`): `src/cks_picks_cfb/ratings/`
  (`state_contracts.py`, `states.py`, `state_audit.py`),
  `conf/ratings/team_state_baseline_v1.yaml` (state design ID
  `ddd6033824909620aa381527dba202a06c65155de53403849b59ffcaaae7092d`),
  Preview-only CLI `scripts/pipeline/build_rating_team_states.py`.
- Inputs: exactly the bounded Phase 1 v2 authoritative refs
  (observations `2d167baa0be6f79eb3fad0ed`, snapshots
  `3163c5e6a18cc01a30542cb2`, terminal `8ccf480cb367e3124086cd69`) and the
  passing audit at
  `artifacts/research/rating-successor/measurements/340091b6…/runs/2026-08-24T2000Z-bounded/`,
  at cutoff `2026-08-24T18:30:00Z` from code commit `4a31a4f` (relevant
  paths identical to `48c0f11`).
- Outputs under
  `artifacts/research/rating-successor/states/ddd60338…/runs/2026-08-25T1153Z/`:
  measurement states `rating_measurement_states_v1` version
  `69965b6a3eb6856f86ed554d` (content SHA-256
  `e43135aa281eefee7e61f7dd04c7a61e1720b64ebfed3f21c7c1849d37111247`;
  77,184 component rows) and team states `rating_team_states_v1` version
  `1fdcb1ca6d235bf2ecf87414` (content SHA-256
  `e4355c14c87d90b9c15ec8d1282649a7ed04939d2e93b790f5a4e21fb6ba454b`;
  8,984 pregame team rows across 2021–2026 and 664 season-terminal team
  rows). Audit report SHA-256
  `5b4dc230128a6a930f85b8534626532df550dc1c716c92e04c04b887b87adc44`.
- Exit gate: all seven audit checks pass (schedule coverage against Phase 1
  pregame snapshot triples, non-null states, eight-component attribution,
  positive uncertainty, terminal identity, market-free, forbidden seasons).
  Behavior is as designed: mean overall uncertainty contracts 0.839 → 0.341
  from zero to twelve completed games while mean observed-evidence weight
  rises 0.00 → 0.845; EPA/success Spearman is 0.75–0.81 across roles. A
  same-stamp rerun reproduced both version IDs and the report SHA
  byte-for-byte. No catalog registration occurred; only `pregame` rows are
  eligible Phase 3 inputs.
