# Possession-Based Rating Methodology

> **Status (2026-09-11):** Specified — decision-complete for the first
> generation. Every measurement on this page remains **uncertified** until the
> possession measurement certification contract passes. Execution authority is
> the [approved specification contract]
> (../plans/2026-09-11/possession-rating-methodology-specification.md);
> semantic authority is this page and
> [rating-system requirements](rating_system_requirements.md).

## Purpose

One offense and one defense rating per team estimate **expected scoring
efficiency per possession against an average opponent under standard
conditions**, each with explicit uncertainty. Passing, rushing, explosiveness,
finishing, field position, pace, and turnover measurements are supporting
diagnostics that explain ratings; they are not rating states in the first
generation. Possession volume is modeled separately when translating unit
efficiency into expected scores, margins, and totals.

The four user decisions of 2026-09-11: compete both rating definitions; carry
the full Phase 4A v2 prior/updater grid; use the plays-per-drive volume proxy
in v1; exclude overtime possessions from rating evidence and route
non-offense scoring to a translation-only state.

## Rating definitions (D1)

Two definitions compete; the rating-estimation tournament's gates decide.

- **Definition A — true points per possession (PPP).** Offense: true drive
  points (certified score-stream reconstruction, `ratings/observations.py:70-218`)
  summed over eligible offensive possessions, divided by that possession
  count. Defense: the same points attributed to the defending team, divided by
  eligible possessions defended.
- **Definition B — EPA per possession.** Offense: sum of eligible-play PPA
  over eligible offensive possessions, divided by that possession count.
  Defense: same for possessions defended.

Both are per team-game measurements with possession exposure, produced for
both roles of every population game.

## Possession eligibility (D2)

A possession is a drive with at least one eligible scrimmage play. Eligible
play = `st == 0`, `penalty == 0`, `twopoint == 0`, play type not a dead-ball
marker, and `garbage == 0` (existing eligibility in `ratings/observations.py`).
Kickoff-only and special-teams-only drives are excluded from both numerator
and denominator (zero eligible plays). One-play drives are included. Clock is
not modeled in v1, so no clock-ending special case exists. The same possession
set denominates both definitions and the volume layer.

## Scoring attribution (D3)

Offensive possessions carry their true drive points to the possessing offense
and the defending defense. Defensive touchdowns, kick/punt/field-goal return
touchdowns, and defensive two-point conversions are excluded from unit
ratings; they occur outside eligible offensive possessions and the
score-stream reconstruction already excludes them from drive points. They feed
a separate **non-offense scoring translation state**: per-team points scored
and allowed off non-offensive plays, per game, accumulated with game-exposure
shrinkage toward league mean (provisional equivalent prior exposure: 4 games).
This state belongs to the translation layer only; it is explicitly not a third rating.

## Overtime (D4)

Overtime drives are excluded from rating evidence and efficiency exposure
(non-standard conditions: fixed starting field position, alternating
possession rules). Overtime points remain in game targets (full-game margin
and total) exactly as played.

## Field position (D5)

No field-position normalization in v1. `average_start_field_position` remains
a certified context-only, unadjusted measurement that translation-layer
challengers may consume; the primary closed-form translation may not.
"Standard conditions" means opponent-adjusted through D6 with no
starting-field-position conditioning. Field-position-normalized efficiency is
a documented future challenger.

## Opponent adjustment (D6)

The certified iterative additive league-centered four-pass adjustment
(iterations 0 and 4 retained) is applied to per-game possession measurements
(both definitions, both roles) exactly as to the six existing adjusted
components. No schedule-strength adjustment occurs at the rating layer; this
prevents double-counting per the approved architecture.

## Scale and standardization (D7)

Per definition × role: preceding-season team-equal standardization (prior
season terminal snapshot pooled mean and standard deviation with frozen floors
and fallbacks, `ratings/states.py:31-61`) produces z-space states; defense z is
reversed so higher is better. Native adjusted values (points per possession or
expected points per possession) are carried alongside for interpretability and
for the closed-form translation. Provisional floors/fallbacks are in the
constants table and must be frozen by the measurement-certification contract
from 2015–2019 representative pooled standard deviations.

## Preseason priors (D8)

The execution-held Phase 4A v2 prior grid is reaffirmed and carried onto both
possession rating definitions: (1) neutral; (2) fixed ρ = 0.60 carryover with
`d = 2` for the 2019→2021 gap (`states.py:257-261`); (3–6) carryover plus
Ridge residual prior on the recruiting block, the returning-production block,
the repaired continuity block, and all three combined. The learned label is
`terminal_possession_rating(S) − carryover_mean(S)` built strictly before
season S. Ridge alpha selection `{0.1, 1, 10, 100}` by inner validation with
the 0.5% simplicity preference, fallback rules, and held-out-residual prior
variance follow the held contract unchanged. Only repaired feature blocks are
eligible (constant columns removed and logged; same-team continuity; censored
tenure lower bound with censor flag; new-coach flag), restricted to
Preview-admitted reconstructed evidence (returning production, recruiting,
coaching). Transfers and talent data remain rejected.

## State updates (D9)

1. Exposure analytic posterior (the reference): credibility `n/(n+k)`
   (`states.py:64-89`) with possession-denominated equivalent prior exposure
   (provisional k in the constants table).
2–4. Recency half-life {2, 4, 8} games: half-life weights applied to numerator
   and denominator (`ratings/phase3.py:402-416`); the weighted denominator
   becomes effective exposure in the same posterior.
5. Local-level Kalman challenger (net-new code): one scalar observation per
   team/role/game equal to that game's adjusted z; observation information is
   that game's eligible possession count (`R = r / n`); process variance grows
   with elapsed days (`P⁻ = P + q·Δ/7`); `K = P⁻/(P⁻+R)`; `m⁺ = m + K(z−m)`;
   `P⁺ = (1−K)P⁻`; preseason mean/variance initialization at first kickoff;
   byes grow variance; q and r fitted per role × prior family on
   preceding-season innovation Gaussian NLL via deterministic L-BFGS-B with
   the held contract's bounds and rejection rules. No adaptive-volatility
   mechanism.

## Uncertainty (D10)

Every state carries posterior variance from its updater (analytic or Kalman).
Game forecasts use Gaussian moment-based target distributions evaluated by
CRPS and 50/80/95% interval coverage with rolling-origin calibration per
[evaluation](evaluation.md). Rating variance is not outcome variance; the
translation layer separates them.

## Possession volume, v1 proxy (D11)

Expected eligible possessions per team per game come from a small Ridge on
`[log own plays_per_drive, log opponent plays_per_drive]` predicting log
possessions, fit on preceding seasons and frozen for the validation season.
The certified `plays_per_drive` pace proxy is the only v1 volume input.
Clock-based tempo reconstruction (Silver plays retains clock fields; byplay
would need extension) is a documented later challenger, out of scope for v1.

## Score translation (D12)

- **Primary closed form.** Expected team points = expected possessions ×
  [league base efficiency + λ·(off_dev + def_dev)] + expected non-offense
  points + frozen league home-field-advantage constant, where deviations are
  the two states' native adjusted values relative to league mean (defense
  signed so lower-allowed is favorable) and λ is a single shrink coefficient
  calibrated once on preceding seasons (reported; expected near 1). Margin and
  total follow by summation.
- **Challenger bridge.** Fold-local Ridge (α = 10) on the four role ratings
  plus a non-neutral home-host indicator and an unknown-venue indicator —
  identical bridge across candidates, per the held Phase 4A design. The
  non-offense expectation enters both paths as an additive offset.

Both paths emit margin and total forecasts; the forecasting contract's gates
decide.

## FCS coverage and missing evidence (D13)

FBS-FCS games remain in the population with existing coverage gates. FCS teams
without their own state use the `fcs_partial_pool` fallback (preceding named
FCS cohort shrunk toward neutral with maximum cohort SD,
`ratings/phase4a.py:317-337`); a missing non-FCS state is a hard error.
Missing measurements stay null with quality reasons. True-points validity
gates are inherited: integral values, [0, 8] drive points, ≥94% season
reconciliation, paired offense-and-defense quarantine on score-stream
violations.

## Evaluation (D14)

Development corpus 2015–2019 and 2021–2025; 2020 excluded from every input,
label, prior, and fold. Outer validation seasons 2018, 2019, 2021–2025; inner
fitting strictly preceding from 2017 with at least two prior training seasons;
no transform fitted on validation. Evaluation is layered and ordered: (1)
rating quality — point-in-time correctness, stable season-long meaning,
responsiveness, uncertainty behavior, attribution, lineage; (2) prediction
quality — ≥0.5% early-game improvement with positive paired 90% lower bound
and full-season MAE within 1% of reference, with ≤5% regression guards per
validation season and per completed-game stage; (3) market comparison only
afterward, per the [roadmap](../planning/data-first-football-forecasting-roadmap.md).
The reference for definition-level comparison is fixed-ρ/exposure on the same
definition; definitions A and B compete under identical grids. Bootstrap:
2,000 replicates, paired season/week blocks, seed 20260908, 90% intervals. The
six-slate prospective policy and promotion rules are unchanged.

## Provisional constants (to freeze, never tune post hoc)

| Constant | Provisional | Frozen by |
| --- | --- | --- |
| PPP standardization floor / fallback | 0.30 / 1.00 pts per possession | Measurement certification |
| EPA/possession standardization floor / fallback | 0.50 / 1.50 expected pts per possession | Measurement certification |
| PPP equivalent prior exposure k | 8 possessions | Rating estimation |
| EPA/possession equivalent prior exposure k | 20 possessions | Rating estimation |
| Non-offense state equivalent prior exposure | 4 games | Score forecasting |
| Translation shrink λ, league HFA, volume Ridge | calibrated on preceding seasons, frozen per validation season | Score forecasting |

## Data-gap inventory (why v1 is shaped this way)

- No possession-count measurement exists yet; drives with ≥1 eligible play are
  the possession proxy, consistent with existing exposure machinery.
- Clock/tempo fields survive only in raw/Silver plays; byplay dropped them, so
  v1 volume uses the plays-per-drive proxy.
- Overtime appears only as `quarter >= 5` and is currently included in every
  measurement; this specification excludes it from rating evidence.
- Defensive and special-teams scores are identifiable play-by-play but were
  previously attributed to no unit; this specification routes them to the
  non-offense translation state.
- The drives dataset `points`/`points_on_opps` columns are Boolean-sum
  defective; only the certified score-stream reconstruction is valid.

A spec-versus-code lesson carried forward from Phase 3: the
`quality_core_epa_split` design document described weighted composites while
the sealed implementation used equal weights — this specification always
states the executable truth.

## Follow-on contract interfaces

- **A. Possession measurement certification.** Produce per-team-game eligible
  possession counts, true offensive drive points, PPP and EPA/possession for
  both roles, and non-offense points for/against; freeze floors, fallbacks,
  and exposure equivalents from 2015–2019 representative data; inherit
  validity gates; publish immutable Preview research artifacts. No catalog
  registration.
- **B. Rating estimation tournament.** Both definitions × the 6-prior ×
  5-updater grid; layer-1 rating gates then bridge-evaluated prediction gates
  per D14; reference fixed-ρ/exposure per definition; implement the Kalman
  challenger (net-new code) to the held contract's specification.
- **C. Score forecasting.** Closed form and bridge challengers with the volume
  proxy and non-offense state; freeze λ, HFA, and volume coefficients per
  validation season.
- **D. Prospective evaluation.** Unchanged six-slate policy; frozen
  pre-kickoff predictions only.
