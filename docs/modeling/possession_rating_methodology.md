# Possession-Based Rating Methodology

> **Status (2026-09-22):** R6 possession measurements are superseded historical
> evidence. The historical V5 lane is complete and accepted: all four audit
> findings are closed, Contract 07 is Implemented with 157 certified live 2026
> games through Week 3, and Contract 08 is the immediate task. Contract 08 is
> followed by the Week 4 refresh, Contract 09 live readiness, Contract 06's
> six-slate prospective evaluation, and a conditional Phase 7 promotion review.
> V4 remains the production champion. The
> [September 11 specification](../plans/2026-09-11/possession-rating-methodology-specification.md)
> remains an Implemented documentation milestone. Current execution authority is
> the [V5 common contract and 00–06 package](../plans/2026-09-13/v5-ratings-successor-roadmap-and-contracts.md).
> Semantic authority is this page and [rating-system requirements](rating_system_requirements.md);
> detailed status is the [data-first roadmap](../planning/data-first-football-forecasting-roadmap.md).

## Purpose

The **V5 ratings successor** represents expected **scoring efficiency per
possession** against an average opponent under standard conditions with one
offense and one defense rating per team, each carrying uncertainty. PPP describes
scoring; EPA describes added expected value and must not be substituted directly
for literal points in a score equation. Keep native units and source/version
metadata when available. V5 ratings successor is distinct from V4 feature schema
v5, the independent operational diagnostic.

Repair v2 and Phase 3 v2 are certified historical evidence. Its
`quality_core_epa_split` selection is benchmark evidence, not a definition or
automatic possession parent. R6 is superseded by r9; r9 measurements, 11B
ratings, the 11C through-2025 final fit, and 11D verification complete the
accepted historical V5 lane. See the
[data-first roadmap](../planning/data-first-football-forecasting-roadmap.md).
The original Phase 4B retained manifest remains prohibited as a forecasting parent.

Retain the September 11 choices of two definitions, six priors, five updaters,
OT exclusion from rating evidence, and separate non-offense scoring. The September
13 amendment adds scoring accounting, fixed constants, exact precision equations,
bridge-first forecasts and a bounded fitting-history comparison. Passing,
rushing, explosiveness, finishing, field position, turnovers and volume remain
diagnostics rather than additional first-generation rating states.

## Rating definitions (D1)

- **Definition A — true points per possession (PPP):** Sum attributable offensive
  drive points over eligible possessions and divide by that possession count.
  Defense receives the corresponding opponent-offense numerator and denominator.
- **Definition B — EPA per possession:** Sum eligible-play PPA over the same
  possession set and divide by that possession count, for both roles.

These are team-game measurements with explicit numerator, denominator, usable
exposure, source timing and quality reasons. The existing score-stream machinery
is reusable evidence; contract 02 must independently certify its new unit/event
attribution before it supplies PPP. Historical certification of points per
scoring opportunity does not certify points per possession.

## Possession eligibility (D2)

A regulation possession is a drive with at least one eligible scrimmage play:
`st == 0`, `penalty == 0`, `twopoint == 0`, not an existing dead-ball marker,
and `garbage == 0`. Include one-play drives. Exclude kickoff-only and
special-teams-only drives. No clock-ending special case is introduced.
The two definitions use the same possession denominator.

For a drive qualifying through at least one eligible play, PPP uses its full
attributable offensive points while EPA uses only eligible-play PPA. Report
mixed-eligibility drives explicitly. Any missing/nonfinite eligible PPA makes
that team-game EPA measurement unusable; never fill it with zero or silently
reduce its denominator. Keep actual possession counts separate from usable
measurement exposure. Zero possessions means null efficiency with a reason.

## Scoring attribution and accounting (D3)

Use chronological score increments with stable team identity and verified source
score timing. Assign conversions to their originating scoring event. Field goals
ending eligible offensive possessions contribute offensive drive points; defensive
and return touchdowns, defensive two-point returns, and safeties belong to
non-offense scoring. A defensive score can occur during a drive that contained an
eligible scrimmage play; drive membership alone does not prove offensive credit.

Partition each team's scoring into mutually exclusive categories:

1. Eligible regulation offensive possession points.
2. Excluded regulation offensive possession points.
3. Regulation non-offense points.
4. Overtime points, retaining unit-category diagnostics.
5. Unresolved scoring increments.

Category sums reconcile to the score stream, then independently to the final
outcome. Do not invent a balancing event or derive offense from unexplained final
score residuals. Unresolved attribution cannot supply certified PPP/non-offense
evidence. Preserve integral, nonnegative and [0,8] offensive-drive checks, >=94%
season final-score reconciliation, and paired offense/defense quarantine.
Separately valid EPA may remain usable; every forecast-eligible game stays in
the schedule population.

The **non-offense scoring translation state** uses prior reconciled regulation
non-offense points for/against, shrunk with four equivalent games toward the
preceding eligible season's league mean. It is explicitly not a third rating.
Contract 04 averages own scoring and opponent allowing expectations for each
side, subtracts the pregame target offset during fitting and adds it at prediction.
Missing team evidence uses the declared prior; missing required league evidence
blocks the fold. The first corpus season has a flagged training-only zero-offset
bootstrap. Never use realized same-game non-offense points as a pregame offset.

## Overtime (D4)

Quarter >=5 is overtime and is excluded from rating evidence and efficiency
exposure. Missing or contradictory period evidence cannot be assumed to be
regulation. Overtime remains in full-game margin and total labels and in its
own scoring-ledger category. Excluded offensive scoring is not mislabeled as
non-offense scoring.

## Field position (D5)

No field-position normalization or new context family enters the first bridge.
"Standard conditions" means opponent-adjusted through D6 without starting-field-
position conditioning. Field position remains a diagnostic and later challenger.

## Opponent adjustment (D6)

Reuse the four-pass, league-centered additive adjustment on both definitions
and roles, retaining iterations 0 and 4. Validate the new measurement replay
independently. Per-game observations, cutoff-specific adjusted history, pregame
snapshots and terminal states are different consumer roles. Never add a second
schedule-strength adjustment in the rating filter.

## Scale and standardization (D7)

Use preceding-season team-equal terminal measurement centers/scales per definition
and role, the existing neutral fallback center, and the fixed floor/fallback table
below. Reverse defense z so higher is better; retain native adjusted values.
Preserve the explicit 2019→2021 predecessor relationship.

No 2015–2019 global constant-fitting step is allowed: it would overlap 2018/2019
outer validation and earlier inner folds. The published values are fixed
first-generation settings, not empirically certified optima. Report flooring,
fallbacks and concerns; later tuning needs a new version with an earlier-only
fitting rule. No transform is fitted on its validation season.

## Preseason priors (D8)

Contract 03 carries the explicitly inherited six-prior registry onto each
definition: neutral; fixed rho=0.60 carryover; and carryover plus residual Ridge
using recruiting, returning production, repaired coaching/roster continuity,
or all three blocks. For calendar gap d:

```text
m0 = 0.60^d * previous_terminal_mean
P0 = 0.60^(2d) * previous_terminal_variance + 1 - 0.60^(2d)
```

No predecessor uses neutral `(0,1)`; 2019→2021 has d=2. The learned label is
season-terminal possession measurement quality in the preceding-season scale,
minus carryover mean, not the candidate's own posterior presented as truth.
The terminal label is available for fitting only after that season completes;
preseason features and carryover are built before the target season.

Use only repaired admitted feature blocks. Constant columns are removed/logged;
missing or ambiguous block inputs use carryover. Transfers/talent remain rejected;
polls and markets are diagnostic-only. Ridge alpha `{0.1,1,10,100}` uses earlier
inner-season residual MAE with the 0.5% larger-alpha preference. Require an
eligible inner fold and two earlier fitting seasons. Learned-prior variance is
chronological held-out squared residual mean (floor `1e-6`); absent calibration
means carryover mean/variance fallback.

## State updates (D9)

Cross each definition/prior with exposure, recency half-lives 2/4/8 games, and
local-level Kalman: **60 structural candidates**. For the analytic reference,
with prior m0/P0, usable observation z, exposure n and equivalent exposure k:

```text
I = n / k
P = 1 / (1/P0 + I)
m = P * (m0/P0 + I*z)
evidence_weight = I / (1/P0 + I)
```

No usable observation means I=0 and the prior is retained. The shorthand
`n/(n+k)` is valid only when P0 equals one. Recency weights multiply numerator
and denominator; the weighted denominator enters this same posterior. Preserve
the inherited half-life age convention, not a new effective-sample-size formula.

Kalman is net-new implementation under contract 03. Each source game supplies
one adjusted z per role with usable possession information n: `R=r/n`,
`P_minus=P+q*elapsed_days/7`, `K=P_minus/(P_minus+R)`,
`m_new=m+K*(z-m)`, `P_new=(1-K)*P_minus`. Fit q/r per definition/role/prior family
on preceding-season innovation Gaussian NLL with the contract's deterministic
optimizer bounds and starts. No adaptive volatility. Byes/missing updates grow
variance through elapsed time without changing the mean.

At each cutoff replay admissible source-game observations once from preseason
state; do not repeatedly assimilate cumulative snapshots. Initialize before the
first kickoff and forecast before observing that game. Retain prior/evidence/
process attribution and count completed games separately from usable exposure.

## Uncertainty (D10)

State uncertainty is posterior rating variance. Outcome uncertainty for each
Ridge target is mean squared earlier rolling-origin prediction error (floor
`1e-6`), with at least one eligible prior residual season. Do not add rating
variance again to empirical outcome-error variance, use training-fit residuals,
or calibrate on the current validation season.

Emit Gaussian marginal target distributions, analytical CRPS and central
50/80/95% intervals. Report coverage, width, bias and sample counts. Separate
margin/total heads do not claim a coherent joint team-score distribution.

## Possession volume diagnostics (D11)

Contract 02 retains eligible possessions and plays per possession for both roles.
Plays per drive measures drive length, not clock tempo. The first bridge does
not require a learned possession-volume model. Clock reconstruction and the
previously proposed plays-per-drive volume regression remain later challengers,
along with possession arithmetic and an explicit EPA-to-points conversion.
Their absence does not block a verified bridge candidate from shadow evaluation.

## Forecast bridge and fitting history (D12)

The first release is **bridge-first**. Contract 03 compares ratings with identical
fold-local alpha-10 Ridge heads from four role ratings plus physical-host and
unknown-venue indicators to full-game margin/total. Contract 04 adds the fixed
prior-only non-offense offset and compares alpha-10 reference heads with
inner-selected alpha `{0.1,1,10,100}` heads. Venue/preprocessing policies are
identical across candidates. Current-game context never enters.

After structural rating selection, compare expanding fitting history with the
latest five eligible completed seasons at each nested fit. Apply the horizon to
learned prior/noise parameters, heads and calibration; preserve continuous state
carryover and preceding-season scaling. Compare identical 2022–2025 games and
retain one shared horizon for both targets. Adopt latest-five only with >=0.5%
pooled MAE improvement, positive paired 90% lower bound, each target's MAE/CRPS
within 1% of expanding history, and <=5% season/stage regression. Otherwise retain
expanding history. Report earlier-era and 2021 transition results separately.

The selected design is refit unchanged through 2025 for 2026; preseason/noise/
head/calibration parameters stay fixed while declared prior-game state and offset
updates proceed. NB2, residual ML, field-position normalization, new context,
clock tempo and arithmetic require a separately frozen later challenger.

## FCS coverage and missing evidence (D13)

Retain all FBS-involving games, including FBS-FCS. A missing FCS state uses the
inherited preceding-cohort `fcs_partial_pool` fallback and conservative variance;
an unexplained missing non-FCS state is a hard error. Missing measurements remain
null with reasons and zero usable exposure, not invented observations. The
scoreable schedule population never depends on successful measurement joins.

## Evaluation (D14)

Use 2015–2019 and 2021–2025 as development history; exclude 2020 everywhere and
2026 outcomes from development selection. Outer seasons are 2018, 2019,
2021–2025; inner validation starts in 2017 with at least two earlier fitting
seasons. No validation outcomes fit transforms, priors, noise, heads or calibration.

Within each definition, reference fixed-rho/exposure. Retain a valid reference
when no challenger passes overall-or-early >=0.5% improvement with positive paired
90% lower bound, the early-only full-season 1% parity condition, and <=5%
target-season/stage guards. Compare the retained EPA winner against retained PPP
under the same rules; prefer PPP without an admissible EPA gain. Invalid
references block advancement. Contract 04 supplies its separate head/window gates.

Bootstrap: 2,000 paired season/week replicates, seed 20260908, 90% intervals.
Historical model/window selection remains development evidence. Contract 05
separates engineering completion from authentic live readiness. Contract 06
requires six qualifying paired normal-coverage slates, >=40 games, T−2h target/
T−1h hard freeze, and >=24h final-outcome stabilization. Week 0 and retrospective
replays do not count. Changed designs reset the protected window. Market
comparison follows football evaluation; promotion needs a separate contract.

## Fixed first-generation settings

| Setting | PPP | EPA/possession | Policy |
| --- | --- | --- | --- |
| Scale floor | 0.30 | 0.50 | Fixed; empirical seasonal scales use preceding terminal measurements |
| Fallback scale | 1.00 | 1.50 | Fixed; preserve explicit fallback reasons |
| Equivalent prior exposure k | 8 possessions | 20 possessions | Fixed analytic-posterior information units |
| Non-offense equivalent exposure | 4 games | 4 games | Translation only; preceding-season league prior |

These settings are not empirically certified optima. Global 2015–2019 fitting,
post-result tuning, and adding a new grid to rescue a failure are not allowed.
There is no first-release arithmetic shrink lambda, league-HFA constant, or
volume-Ridge fitting prerequisite; venue effects are in the bridge.

## Timing classes

Every possession row carries a `timing_class` recording how its evidence
availability is substantiated:

- `historically_reconstructed`: all rows of the 2015–2019 and 2021–2025
  development corpus. Captures post-date the games; pre-kickoff availability
  is proven by kickoff-ordered replay, not by capture time. Historical
  datasets, configs, runners, and verifiers require this class exclusively —
  a non-reconstructed row in historical scope fails closed.
- `live`: 2026-season rows only, admitted under Contract 07. Availability is
  substantiated by source-capture timestamps and effective times recorded by
  the weekly pipeline before kickoff. `live` rows never enter historical
  datasets, configs, or selections.

Season 2020 is forbidden in every class. Timing admission is enforced at three
independent layers: dataset schemas admit a class per dataset family, the
producer and validator functions require the exact class per run scope, and
the independent verifiers reconstruct and compare per scope. Sealed season
pins, parent run-IDs, and reconciliation counts are amended explicitly per
layer; the historical r9 configuration and its 8936/8935 counts are untouched.

## Data gaps and certification limits

Possession counting, unit scoring attribution and OT filtering are specified
but not yet certified. Existing drive `points`/`points_on_opps` are defective
numerators. Score-stream final reconciliation alone does not prove unit attribution.
Missing source period/PPA or unresolved scoring must remain visible. Clock fields
survive in raw/Silver data but not the current byplay representation. Source model
version/coverage differences limit historical comparability and must be reported.

Phase 3's `quality_core_epa_split` implementation used equal-weight composites;
its earlier weighted-design description is not the executable truth. Keep that
benchmark's immutable identity and meaning separate from these new measurements.

## Follow-on contract interfaces

- [02: possession certification](../plans/2026-09-13/02-v5-possession-measurement-certification.md): population, scoring/possession ledgers, both role measurements, cutoff replay, independent certification; no catalog registration.
- [03: rating estimation](../plans/2026-09-13/03-v5-possession-rating-estimation.md): 60 structural candidates, inherited prior/updater mathematics, fixed bridge comparison and verified selected states.
- [04: forecast bridge and fitting windows](../plans/2026-09-13/04-v5-forecast-bridge-and-fitting-window.md): non-offense offsets, bounded Ridge/head-window comparison, outcome calibration and candidate freeze.
- [05: readiness and shadow tooling](../plans/2026-09-13/05-v5-prospective-readiness-and-shadow-tooling.md): independently verified rehearsal and separate authentic live-readiness result.
- [06: prospective evidence](../plans/2026-09-13/06-v5-prospective-evidence-and-recommendation.md): immutable six-slate ledger and recommendation; no automatic promotion.
