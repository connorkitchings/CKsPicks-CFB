# V5-03: Possession Rating Estimation Tournament

- **Status:** In Progress
- **Created:** 2026-09-13
- **Planner:** Codex planning task
- **Approval source:** User approved the complete package with “Implement the proposed plan.” on 2026-09-13; execution is dependency-gated.
- **Implementation log:** `session_logs/2026-09-16/02-v5-possession-rating-estimation.md`.
- **Commit policy:** Separate code and certified-evidence checkpoints; user executes Git.

## Goal, current state, and entry gate

Select one shared offense/defense rating definition, prior and updater from the
approved 60-candidate registry. [02](02-v5-possession-measurement-certification.md)
must have an independently verified eligible manifest. The
[common contract](v5-ratings-successor-roadmap-and-contracts.md) is binding.
No current possession estimator or Kalman implementation is presumed to exist.

The former Phase 3 composite and original Phase 4B manifest cannot substitute
for the required possession parent. Preserve Phase 3 benchmark results with
their historical reconstructed status. This task selects ratings using a common
diagnostic bridge; contract 04 supplies the final uncertainty-bearing candidate.

## Approach, scope, and interfaces

Add possession-specific rating/prior/updater/selection code under
`src/cks_picks_cfb/ratings/`, schema validators under `src/cks_picks_cfb/data/`,
runner/verifier under `scripts/research/`, research configuration, and focused
rating tests. Parent flags: `--measurement-manifest-uri` and
`--repair-manifest-uri`. Stage: `ratings`. Other CLI/manifest rules come from
the common contract. No V4 changes, catalog registration, live forecasts,
market inputs, auxiliary acquisition, or registry expansion.

Explicitly inherit the following sections of the execution-held
[September 8 rating contract](../2026-09-08/phase4a-prior-and-dynamic-rating-selection-v2.md):
Prior registry, deterministic q/r fitting settings, stage definitions,
within-definition selection gates and tie order, and named FCS fallback.
Replace its composite parent/observation, component-information formula,
equivalent-exposure interpretation, and output paths with this possession
contract. This is mathematical inheritance, not permission to execute the old
runner.

## Implementation tasks

### Task 1 — Freeze registry and construct chronological priors

Cross PPP and EPA/possession with six prior families and five updaters. Persist
the complete registry before outer predictions; no outcomes-based pruning.

Priors: neutral `(0,1)`; annual rho=0.60 carryover; carryover plus residual Ridge
on recruiting, returning production, repaired coaching/roster continuity, or all
three blocks. Freeze exactly the inherited block columns and semantic admissions.
Transfers/talent stay rejected; polls/markets never enter. Remove/log constant
training columns. Missing/ambiguous/rejected block inputs trigger carryover for
that team-season, not fabricated mean-imputed preseason observations.

For gap d, use `m0=0.60^d*m_previous` and
`P0=0.60^(2d)*P_previous+1-0.60^(2d)`. No predecessor uses neutral; the
2019→2021 gap has d=2. Standardize each definition/role with preceding-season
team-equal scales and fixed floors/fallbacks; reverse defense so higher is better,
and retain native adjusted measurement units for interpretation.

The learned label is season-terminal possession **measurement quality**, in the
season's preceding-season scale, minus its carryover mean. It is not the
candidate's own fitted posterior relabeled as truth. A season's terminal label
is available for fitting only after that season. Fit offense/defense separately.
Select Ridge alpha `{0.1,1,10,100}` on earlier inner-season residual MAE; within
0.5% prefer larger alpha. Require an eligible inner fold and two earlier fitting
seasons. Use chronological held-out squared residual mean, floor `1e-6`, for
learned-prior variance; absent evidence falls back to carryover mean/variance.

**Acceptance:** Future seasons, post-cutoff coach/roster records, and terminal
labels cannot alter preseason features. Missing blocks preserve every prediction
row. Inner choices, removed columns, calibration counts and fallbacks are logged.

### Task 2 — Implement continuous updates and state attribution

Implement exposure and half-life 2/4/8-game updates with the common contract's
analytic equations and k=8/20 possessions. Recency weights multiply numerator
and denominator; the weighted denominator is information exposure. Preserve the
existing half-life age convention. Missing observations supply no information.

Kalman consumes one adjusted z observation per team/role/source game, information
n equal to eligible possessions usable for that definition:

```text
P_minus = P + q * elapsed_days / 7
R = r / n
K = P_minus / (P_minus + R)
m_new = m + K * (z - m)
P_new = (1 - K) * P_minus
```

Initialize mean/variance at the first scheduled kickoff; forecast before that
game's observation. Advance time through missing observations and byes without
changing the mean. Fit q/r per definition, role and prior family on earlier-season
innovation Gaussian NLL. Inherit bounds q `[0,1]`, r `[1e-6,100]`, starts
`(0.01,1)`, `(0.1,1)`, `(0,1)`, maxiter 1000, ftol `1e-9`, finite convergence and
deterministic objective/tie policy. Insufficient history uses the matching
exposure updater with a cold-start flag; optimizer failure after sufficient
history disqualifies the Kalman candidate. No adaptive volatility.

At every forecast cutoff, replay the certified cutoff-specific source-game
observations once from preseason state. Do not repeatedly assimilate cumulative
snapshots, freeze later opponent information into earlier cutoffs, or perform a
second schedule adjustment. Retain prior/evidence/process contributions and
completed games separately from measurement exposure.

Use the inherited preceding-cohort `fcs_partial_pool` fallback and conservative
variance for an FCS team without a state; an unexplained missing non-FCS state is
a hard error. Preserve no-observation forecasts and explicit quality flags.

**Acceptance:** Finite mean/positive variance, exact prior/no-evidence behavior,
reproducible attribution, one-use observations, correct day advancement, and
same-game/future invariance. Analytic uncertainty does not acquire Kalman process
noise by accident. No assumption that state variance equals score variance.

### Task 3 — Evaluate all candidates with an identical bridge

Use fold-local target Ridge alpha 10 on the four role ratings plus non-neutral
physical-host indicator and unknown-venue indicator, with training-only
standardization floor 0.05 and inherited venue fallback. Fit margin and total
separately; full-game outcomes are labels. This is the common selection bridge
from the prior contract, not the final contract 04 calibration/head search.
It does not introduce candidate-specific context or current-game observations.

Outer seasons: 2018, 2019, 2021–2025; earlier fitting only. Include the entire
scoreable schedule population. Report target/season and completed-game slices,
fallback usage, forecast errors, rating responsiveness and uncertainty behavior.
Cache shared replays/transforms by complete lineage keys; run every structural
candidate or record an explicit validity failure.

**Acceptance:** The only candidate-varying football inputs are the declared
rating design and its fitted parameters. The target bridge, venue policy and
population are identical. No all-season transform, future terminal state, or
same-game context can enter an outer forecast.

### Task 4 — Select within and between definitions

Within each definition, compare challengers to its valid fixed-rho/exposure
reference. A challenger advances either on >=0.5% full-season pooled improvement
with positive paired 90% lower bound, or on the same early-union improvement with
full-season MAE <=1.01 times reference. Require every target-season and pooled
completed-game-stage regression <=5%; missing required reference slice blocks
the gate. Pool the two targets equally, not by treating both as extra games.

Rank passing challengers by full-season pooled MAE. Within 0.5% prefer fewer prior
features, then exposure, half-life 8, half-life 4, half-life 2, Kalman, then lexical
ID. With no passing challenger retain that definition's reference.

Compare the retained EPA winner against the retained PPP winner using the same
paired overall-or-early advancement rules and regression guards. PPP is the
cross-definition reference and tie preference. If EPA does not establish an
admissible gain, retain PPP. Both references must be valid; do not silently drop
a definition on measurement or population failure.

**Acceptance:** An independent implementation reconstructs all metrics,
bootstrap intervals, fallbacks, ties, reference validity, and selected identity.
Historical selection is explicitly development evidence, not a prospective win.

### Task 5 — Materialize and verify the retained design

Output versioned `rating_registry`, `prior`, `noise_fit`, `rating_state`,
`team_state`, `bridge_prediction`, `rating_attribution`, and
`retained_rating_manifest` records. State keys bind candidate/definition,
season/game/team/role/cutoff; records carry native and z means, variance,
prior/evidence/process contributions, exposures, completed games, source refs,
scaling and fallback. Persist fitted parameters and every inner-fit history.

The verifier rereads exact 02/Repair parents and independently reconstructs
priors, selected update trajectories, bridge predictions, and selection. Validate
all retained artifacts and an idempotent rerun. Expose structural design and
fitting recipes so contract 04 can replay them under a bounded fitting window
without reselecting the definition/prior/updater.

## Testing strategy

Run common computational gates plus label/feature chronology, variable-prior
precision, k units, recency denominators, Kalman day/noise/optimizer tests,
constant/missing block fallback, two-year carryover, FCS cohorts, venue handling,
full population, gain/tie/stage logic, and independent selection tests. Perturb
same-game and future data for every feature path, including priors and scaling.

## Risks, definition of done, and amendments

The 60-candidate search is exploratory and must be reported in full. A simple
reference can legitimately win. Insufficient data or an invalid reference cannot
be rescued by removing hard games or calling an old manifest certified.

- [ ] All 60 candidates have results or explicit validity failures.
- [ ] Both reference definitions pass hard validity gates.
- [ ] Selected design, state provenance, uncertainty and independent selection are verified.
- [ ] Committed-code preflight, apply, independent verifier and idempotent rerun pass.
- [ ] Required tests/docs/session log and lifecycle status are complete.

Use the common amendment process. No final forecasting family/window selection
or prospective execution occurs in this contract.

## Execution decomposition (2026-09-16)

The remaining implementation is split into two dependency-ordered contracts
without changing this umbrella contract's architecture, interfaces, registry,
mathematics, gates, or definition of done:

1. [V5-03A: materializer and tournament](../2026-09-16/01-v5-rating-materializer-and-tournament.md)
   completes exact-parent loading, all 60 chronological states, the common
   bridge/selection tournament, and deterministic no-write preflight evidence.
2. [V5-03B: artifact certification](../2026-09-16/02-v5-rating-artifact-certification.md)
   performs evidence-bound immutable materialization, independent reconstruction,
   idempotency, and final Contract 04 eligibility.

03A was explicitly approved by the user on 2026-09-16. 03B remains Draft until
03A has a clean committed SHA and reviewed deterministic preflight evidence.
V5-03 remains In Progress and is not complete after 03A alone.
