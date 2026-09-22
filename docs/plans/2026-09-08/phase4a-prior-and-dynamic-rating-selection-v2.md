# Phase 4A: Prior and Dynamic Rating Selection v2

- **Status:** Superseded
- **Created:** 2026-09-08
- **Planner:** Astra
- **Approval source:** User approved the full replacement plan on 2026-09-08, including early-season advancement at full-season parity and a Kalman challenger without adaptive volatility.
- **Implementation log:** Pending repaired Phase 3 and separate Phase 4A task
- **Commit policy:** Separate code/evidence checkpoints; user executes Git.

> **Superseded (2026-09-13):** Execution authority is [03: possession rating estimation](../../archive/v5-contracts/2026-09-13/03-v5-possession-rating-estimation.md).
> Preserve the original approval, historical hold notice, and mathematical record
> below. Only sections explicitly inherited by the
> [V5 common contract](../../archive/v5-contracts/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md)
> carry forward. This does not authorize executing old runners or consuming the
> original Phase 4B retained manifest as a forecasting parent.

> **Execution hold (2026-09-10):** This remains an Approved historical record
> with its original approval source. Do not execute it until a verified Phase 3
> benchmark and the possession-based methodology review produce a replacement or
> explicit reaffirmation.

## Goal, parents, and interfaces

Select one shared offense/defense rating from six prior families crossed with
five updaters. The [common contract](transformation-review-and-authority-reset.md)
is binding. Inputs: `--phase3-retained-uri`, `--repair-manifest-uri`; require the
same repaired lineage and a verified selected core. Do not hardcode EPA-only or
the historical v1 winning candidate. Polls, markets, direct-model substitution,
adaptive volatility and production are excluded.

## Prior registry

Use neutral `(mean=0, variance=1)` and fixed annual rho 0.60 carryover references,
plus carryover residual Ridge with recruiting, returning production,
coaching/roster continuity, or all three blocks. Carryover for calendar gap d:
`m0 = 0.60^d * previous_terminal_mean`,
`P0 = 0.60^(2d) * previous_terminal_variance + 1 - 0.60^(2d)`.
No predecessor means neutral fallback; 2019→2021 has d=2.

Learn offense and defense separately. For each historical target season S,
construct preseason features and carryover strictly before S; label the
residual `terminal_core_quality(S) - carryover_mean(S)`. Terminal core quality
uses the selected component weights and preceding-season scaling, with defense
reversed. It is a training label only after S is completed, never a feature for S.
Exclude missing terminal labels; retain all prediction rows with fallback.

Freeze block columns from repaired schemas before fitting:

- Recruiting: current, available-class average/count/span, and current-minus-
  available-average trend. Strict four-class value remains a coverage diagnostic.
- Returning production: `return_total_ppa`, `return_passing_ppa`,
  `return_rushing_ppa`, `return_receiving_ppa`, `return_percent_ppa`,
  `return_passing_usage`, `return_rushing_usage` only if semantically admitted.
- Continuity: tenure lower bound, tenure-censor flag, new-coach flag, same-team
  returning share and returning-QB count. Incoming experience is separately
  reported and is not another candidate block in this registry.

Missing required block inputs, ambiguous identity or rejected family means
carryover fallback for that team-season. Fit on complete, admitted historical
rows only; do not interpret mean imputation as an observed preseason fact.
Centers/scales use training rows, with scale floor 0.05. Constant columns are
removed and logged; a block with no usable variation is ineligible.

Ridge alpha `{0.1,1,10,100}` is selected by earlier-season inner validation of
terminal-residual MAE; within 0.5% of best prefer larger alpha. At least one
eligible inner validation season and two earlier fitting seasons are required;
otherwise use carryover. Refit chosen alpha using all preceding eligible seasons.
Prior mean is carryover plus the learned residual. Learned-prior variance is
chronological held-out squared residual mean (floor `1e-6`), not training-fit
error; absent calibration evidence means carryover mean/variance fallback.

## Updaters and noise estimation

Cross all six prior families with exposure, half-lives 2/4/8 games, and Kalman:
30 named structural candidates. Inner-selected alpha/noise are recorded fitted
parameters, not extra outer candidates. Preserve the established analytic
posterior and equivalent-exposure rules for exposure/recency references.

Kalman processes one scalar selected-core observation per team/role/source game.
Construct core z observations from certified per-game adjusted measurements with
the retained component weights and season-preceding scales. Reuse Phase 3's
missing-component contract; missing core evidence cannot become a fabricated
zero observation. Effective information in prior-equivalent units is
`n_eff = 1 / sum(weight_j^2 / information_j)` over required usable components;
`information_j` is native exposure divided by the existing component's
equivalent-exposure constant. Missing required information means no update.

For elapsed calendar days Δ from the previous state timestamp:

```text
P_minus = P + q * Δ / 7
R = r / n_eff
K = P_minus / (P_minus + R)
m_new = m + K * (z - m)
P_new = (1 - K) * P_minus
```

Initialize from the candidate's preseason mean/variance at the first scheduled
season kickoff; forecast without assimilating that game's observation. Advance
time to each forecast cutoff and valid observation timestamp. With missing
observations, time still increases variance but mean does not change. Byes can
increase uncertainty; surprise-dependent volatility is explicitly excluded.

Fit q/r separately per role and prior family on preceding-season innovation
Gaussian negative log likelihood. Deterministic L-BFGS-B: q in `[0,1]`, r in
`[1e-6,100]`, starts `(0.01,1)`, `(0.1,1)`, `(0,1)`, maxiter 1000, ftol `1e-9`;
select lowest finite converged objective, lexical start order for exact ties.
Reject a candidate if no start converges. No calibration on current validation
outcomes. With insufficient earlier seasons, use the corresponding exposure
updater with an explicit cold-start fallback, consistently in all replays.

At each cutoff, replay the certified cutoff-specific per-game observations once
from preseason state; do not assimilate cumulative snapshots repeatedly. Preserve
per-observation prior/evidence weights and process variance attribution. Never
apply opponent adjustment in the filter. Preserve existing named FCS and
preceding-FBS–FCS cohort fallback, variance and reasons; no future FCS cohort.

## Fixed bridge and selection

Use fold-local Ridge alpha 10 with four role ratings and a non-neutral home-host
indicator; a neutral game has zero home advantage. Unknown venue status has a
training-only imputed value and a separate unknown indicator. Use the same
bridge, scale floor 0.05, venue/fallback columns and populations for every candidate.

Reference: fixed-rho/exposure. Advancement routes:

1. Full-season pooled gain >=0.5% and paired 90% lower bound >0; or
2. Early-game pooled gain >=0.5% and paired 90% lower bound >0, with full-season
   pooled MAE <=1.01 × reference.

Both require equal population, every target-season regression <=5%, and every
pooled completed-game-stage regression <=5%. Stage membership is team-specific
0/1/2/3/4+ completed games, counted from finalized schedule history independently
of usable observations. A game can appear in both teams' diagnostic stages but
is counted once in the early union (either side has 0–3) and once per pooled
stage. Report asymmetric experience explicitly. Missing reference evidence for a
required stage blocks that gate, rather than silently passing it.

Rank passing candidates by full-season pooled MAE; within 0.5% prefer fewer prior
features, then exposure, half-life 8, half-life 4, half-life 2, Kalman, then lexical
ID. Always report whether advancement used overall or early evidence. No passing
challenger means retain valid fixed-rho/exposure.

## Outputs, tests and done

Stage `phase4a/v2`; schemas: `phase4a_prior`, `phase4a_noise_fit`,
`phase4a_rating_state`, `phase4a_team_state`, `phase4a_prediction`,
`phase4a_attribution`, `phase4a_retained_rating`. State keys include candidate,
season/game/team/role/cutoff; records include mean/variance, prior/evidence/process
contributions, exposure, completed-game count, source lineage and fallback.
Manifest records exact selected core, admitted feature list, fitted parameter
policy, alpha/noise history, stage reports and retained candidate.

Verify chronological target construction, early-versus-overall gates, larger-
alpha ties, empty/constant blocks, changing neutral-site status, sparse/FCS teams,
two-year gap, Kalman one-use assimilation, uncertainty growth through byes,
missing updates, deterministic optimization, noise fitting before validation,
full population and independent selection. Common validation is mandatory.
Done requires an independently verified eligible rating and complete artifacts,
docs/log. Any registry, uncertainty or threshold change uses common amendments.
