# Current V5 ratings: workflow audit and mathematical explanation

Read-only audit on 2026-09-28 at repository commit `71b27be`. Production
rating evidence ends at **2026-09-27 14:15 UTC, after Week 4**. No model,
source artifact, serving row, publication, or selection was changed.

## Conclusions

- The accepted V5 model is built, verified, accepted, and serving production.
  Its broader product-transformation contract is still **In Progress**:
  the implemented weekly operator is manual, automatic scheduling is excluded,
  and V4 execution remains available for rollback. Model completion does not
  mean every original product/retirement objective is closed.
- The recent ratings-history work works on current production data. All six
  history tabs contain 138 teams, with preseason backfill where appropriate.
  A latent default-view label/data mismatch remains during projection before
  selection, described below. Therefore this is not an unconditional
  “every future workflow is ready” sign-off.
- South Carolina is #11 at **1.439034**; Alabama is #12 at **1.432711**.
  The gap is only **0.006323**, not a meaningful large separation. Rounded to
  two decimals these are 1.44 and 1.43. Alabama's 49–18 win is included.
- Explicit preseason weight is about **29% for South Carolina** and
  **21% for Alabama**, separately estimated for offense and defense. The
  remaining weight is current-season evidence, but that evidence is a
  weighted history of **cumulative adjusted snapshots**, not independent
  single-game performances. This distinction deserves a separate mathematical
  review before another rating-design decision.

## Review of recent changes and live state

Reviewed the last eight commits, including the sealed-input changes in
`597b1c3`, the history serving changes in `9a77ee1`, and closure commits
`6c49436`/`71b27be`; also reviewed the preceding ratings lifecycle changes
`83607c2` and `7ba4582`. Started on clean `main`; reviewed September 26–27
session summaries and the detailed implementation/verification logs.

Verified now:

- GitHub CI succeeded on both latest closure commits and the implementation
  commits `9a77ee1` and `597b1c3`. Earlier canceled runs are not failures;
  the old documentation assertion failure was followed by successful runs.
- 203 focused Python tests passed across lifecycle, sealed inputs, ratings,
  ops state machine, weekly cycle, release, serving, and readiness/verifier
  behavior. All 29 web publication tests passed. These are scoped checks;
  this audit did not rerun the complete model tournament or mutate a live cycle.
- Production's V5 provenance CHECK is present and validated. Current selection
  is `2026w5-5d436e58c072`, still `published`, with public health `ok` and
  56 expected / 56 predicted / 56 lined games. This checks the published
  snapshot, not whether today's provider quotes are unchanged.
- Five `current` generations have respectively 16, 94, 137, 138, and 138
  distinct teams and exactly one source manifest per cutoff. Public HTTP
  readback found 138 distinct team links on Preseason, Post-Week 0–4, and
  the default/current view. This is content verification, not a new visual
  browser test.
- Rebuilt all 138 current team states from the certified R2 parents using
  the production state builder. Maximum absolute difference from Neon across
  all offense and defense means: **0.0**. This is a serving/reconstruction
  check, not independent proof that the estimator's statistical assumptions
  are correct.

### Findings requiring follow-up

**P2 — Default ratings metadata can get ahead of selected data.**
[`getWeeklyRatings`](../../web/src/lib/v5.ts) returns the newest projected
generation's metadata but obtains default rows from `getCurrentRatings`,
which is pinned to the latest selected forecast's rating manifest. Project
Week 5 ratings before selecting Week 6 forecasts, or roll selection back,
and the default view can label older rows with the newer cutoff. The existing
default-return branch was executed with stubbed new-generation metadata and
old selected rows and reproduced this mismatch. Current production is aligned,
so today's South Carolina ordering is not caused by this defect. Fix should
bind label and rows to the same selected generation and cover projection-before-
selection and rollback with behavioral tests. The existing ratings test mostly
checks source text and does not exercise these query relationships.

**P2 — “Frozen” early-tab fallback is still selection-dependent.**
`getPreseasonPriors` resolves the currently selected source, even when used
to fill a historical cutoff. The current frozen design produces identical
priors across these generations, so no current numerical discrepancy was found.
However, a rollback to a source lacking the full cohort, a missing source, or
a future authorized prior revision can change historical backfill. Historical
fallback needs an explicit immutable baseline identity if permanent history
is the contract. Likewise, duplicate generations at one cutoff are currently
resolved by newest row, not rejected by the page query; none exist today.

**Documentation drift.** The methodology header and documentation home still
said V4 served production; the methodology also said possession certification
was unfinished. These statements were corrected with this audit. The broader
product contract remains In Progress intentionally: the manual-operator
contract explicitly required it to remain open. Do not silently close it or
infer automatic weekly scheduling from green CI.

The next operational gate is still a fresh full-slate market reconciliation
and reviewed freeze before the 2026-10-02 00:00 UTC first kickoff, respecting
the T−2h target / T−1h hard lead. This audit does not perform that operation.

## What the rating numbers mean

The chosen identity is `ppp__rho_0_60__exposure`. It won the accepted selection
process; the learned recruiting/returning-production/coaching priors, EPA
definition, recency updaters, and Kalman challenger are **not** the selected
production method.

Offense and defense are standardized opponent-adjusted offensive points per
eligible possession. Defense reverses sign, so larger is better for both.
Overall is `(offense + defense) / 2`; it is not a point spread, win/loss
standing, head-to-head ranking rule, or a separately fitted power rating.
The displayed uncertainty is the square root of rating variance; overall
variance is `(offense_variance + defense_variance) / 4`, without a covariance
term. It is not the calibrated uncertainty of a game score forecast.

Actual 2026 scaling is fixed from 2025 team-equal terminal measurements:

| Role | Native PPP center | Native PPP scale | Standardized value |
| --- | ---: | ---: | --- |
| Offense | 1.623348 | 0.947456 | `(adjusted PPP − center) / scale` |
| Defense | 2.647380 | 1.194142 | `(center − adjusted allowed PPP) / scale` |

These role-specific centers need not be identical. Zero is the relevant
preceding-season reference center, not a claim that today's displayed
population has mean zero. The fixed PPP scale floor is 0.30.

### From plays to opponent-adjusted measurements

1. A regulation drive counts if it contains at least one eligible scrimmage
   play: no special-teams-only, penalty-only, two-point-only, dead-ball-only,
   or garbage-only possession. Overtime is excluded. One-play drives count.
2. PPP uses the full attributable offensive points of a qualifying drive,
   including its field goal or attached conversion. Defensive/return scores
   and safeties belong to separate non-offense accounting. A final scoreboard
   total is consequently not the PPP numerator.
3. Existing garbage flags use a margin of at least 35 in the third quarter
   or 27 in the fourth. A drive with both eligible and excluded plays can
   still count. This can make the usable exposure of a blowout quite small.
4. At each eligible cutoff, aggregate points divided by possessions by team
   and role, then perform four additive opponent-adjustment passes. Each
   pass subtracts the possession-weighted opponent-role deviation from that
   role's exposure-weighted league center, starting again from raw team PPP.
   There is no additional schedule-strength correction in the rating updater.
5. Historical observations are admitted with kickoff-plus-six-hours and
   later-week boundaries. The selected updater has no explicit recency decay;
   byes with no newly usable evidence do not automatically reduce prior weight.

See [`possession_measurements.py`](../../src/cks_picks_cfb/ratings/possession_measurements.py)
and [`possession_live_replay.py`](../../src/cks_picks_cfb/ratings/possession_live_replay.py).

### Preseason prior and weekly weights

For the live 2026 path, the prior starts from the team's standardized **2025
terminal measurement**, not its win/loss record and not a recruiting model:

```text
previous_variance = 1 / (1 + 2025_usable_possessions / 8)
m0 = 0.60 × standardized_2025_terminal_measurement
P0 = 0.36 × previous_variance + 0.64
```

Missing/invalid predecessors fall back to mean 0, variance 1 with a reason.
The 0.60 is offseason carryover of the mean; it does **not** mean ratings
remain 60% prior during the season. General historical carryover uses
`0.60^calendar_gap`, including the two-year 2019→2021 gap.

With usable cumulative exposure `N`, base constant `k=8`, and the updater's
possession-weighted standardized observation average `zbar`:

```text
I = N / 8
P = 1 / (1/P0 + I)
prior_weight = P/P0 = 8 / (8 + P0 × N)
evidence_weight = 1 − prior_weight
rating = prior_weight × m0 + evidence_weight × zbar
```

Offense and defense have separate exposure and variance. With typical
`P0≈0.66`, the prior is equivalent to about **12.1 possessions**, not eight
literal possessions and not eight games. At 0/10/20/30/40/50 usable possessions,
the illustrative prior shares are 100/54.8/37.7/28.8/23.3/19.5 percent.
Weeks and completed games are not the weighting unit.

Actual percentages below are **prior / current-season evidence**. These
are explicit linear coefficients, not percentages of predictive accuracy or
claims that the cumulative evidence observations are independent.

| Cutoff | Alabama offense | Alabama defense | South Carolina offense | South Carolina defense |
| --- | ---: | ---: | ---: | ---: |
| Preseason / Post-Week 0 (both idle) | 100 / 0 | 100 / 0 | 100 / 0 | 100 / 0 |
| Post-Week 1 | 57.4 / 42.6 | 54.9 / 45.1 | 66.7 / 33.3 | 66.9 / 33.1 |
| Post-Week 2 | 37.7 / 62.3 | 36.7 / 63.3 | 66.7 / 33.3 | 66.9 / 33.1 |
| Post-Week 3 | 26.9 / 73.1 | 26.9 / 73.1 | 40.1 / 59.9 | 38.9 / 61.1 |
| Post-Week 4 | 21.6 / 78.4 | 21.3 / 78.7 | 28.6 / 71.4 | 28.8 / 71.2 |

Across teams with current rows, median offense/defense prior shares are
51.4/51.4% after Week 0, 54.7/54.7% after Week 1, 50.2/50.2% after Week 2,
35.5/34.5% after Week 3, and 27.5/27.1% after Week 4. Cohorts differ
(16/94/137/138/138 teams); idle teams backfilled from preseason are excluded
from these medians. The early median increase is a cohort effect.

## Why South Carolina is still just above Alabama

| Period | Alabama overall | South Carolina overall |
| --- | ---: | ---: |
| Preseason | 0.715701 | 0.439406 |
| Post-Week 1 | 1.123651 | 1.429604 |
| Post-Week 2 | 1.301173 | 1.429604 |
| Post-Week 3 | 1.366138 | 1.579139 |
| Post-Week 4 | 1.432711 | 1.439034 |

The prior favors Alabama overall. The reversal originates in the current-season
evidence, particularly South Carolina's Kent State opener, not an unusually
high South Carolina preseason prior. South Carolina's Week 2 bye preserves its
Week 1 state. Its later losses reduce the gap from 0.213002 to 0.006323 after
the Alabama game.

Certified eligible offensive measurements:

| Team | Opponent | Week | Eligible offensive points / possessions |
| --- | --- | ---: | ---: |
| Alabama | East Carolina | 1 | 31 / 9 |
| Alabama | Kentucky | 2 | 37 / 11 |
| Alabama | Florida State | 3 | 50 / 13 |
| Alabama | South Carolina | 4 | 42 / 11 |
| South Carolina | Kent State | 1 | 36 / 6 |
| South Carolina | Mississippi State | 3 | 34 / 12 |
| South Carolina | Alabama | 4 | 18 / 12 |

The head-to-head game (`401856696`) is recorded as Alabama 49–18; eligible
offensive scoring is 42–18. The scoring categories, not an assumed score
correction, explain why final score and eligible numerator differ. This audit
checked certified aggregate inputs; it did not independently re-adjudicate
every scoring event from video or source play descriptions.

South Carolina now has offense 1.893284 and defense 0.984784; Alabama has
offense 1.818290 and defense 1.047132. South Carolina's 0.074994 offensive
advantage narrowly exceeds Alabama's 0.062349 defensive advantage. Their
overall rating standard deviations are approximately 0.308 and 0.266.
The 0.0063 gap is tiny relative to those marginal uncertainties; these
variances alone do not supply a calibrated head-to-head win probability.

### The cumulative-snapshot issue

`_streams` gives each game the team's cumulative iteration-four adjusted
snapshot at its first eligible later-week team boundary, weighted by that
game's own possessions. For the most recent game without such a boundary,
`build_current_team_states` uses the current cumulative terminal value.
Thus the effective inputs are snapshots **after game 1, after games 1–2,
after games 1–3**, and so on—not separately adjusted game 1, game 2, game 3.

For South Carolina offense the actual terms are:

| Assigned source game | Cumulative adjusted z | Possession weight | Contribution to current offense |
| --- | ---: | ---: | ---: |
| Kent State | 4.619373 | 6 | 0.659513 |
| Mississippi State | 2.501779 | 12 | 0.714363 |
| Alabama | 1.647672 | 12 | 0.470480 |
| Preseason prior | 0.170990 | 28.614% coefficient | 0.048928 |
| **Sum** | | | **1.893284** |

The z assigned to Alabama is South Carolina's cumulative season measurement,
not its 18/12 game efficiency. The Kent State result also remains inside the
later cumulative values. Exposure is counted once numerically, but performance
information overlaps across those values. Consequently, “71% current season”
does not mean “71% an ordinary possession-weighted season average.”

With three equally sized games and no changing opponent adjustment, averaging
the successive cumulative means gives raw games effective weights of
**61.1%, 27.8%, and 11.1%** within the evidence component, rather than one
third each. Actual weights differ with exposure and opponent updates, but
this illustrates the built-in preference for earlier games even though the
selected updater is called `exposure`, not a recency filter.

This construction predates the last eight commits and is explicit in the
historical materializer as well as the live replay. It is not a history-tab
regression or evidence that the head-to-head result was omitted. It is a
material semantic tension with the methodology's “do not repeatedly
assimilate cumulative snapshots” instruction. Independent reconstruction can
confirm the same design faithfully while leaving that statistical concern
unresolved. Correlated cumulative observations also warrant review of the
rating-variance interpretation. No claim is made here that a replacement
would improve out-of-sample forecasting.

## What should happen next

First resolve and test the default label/selection issue as a separate scoped
implementation. Then commission a bounded model audit distinguishing three
estimators: the existing snapshot stream, a single cumulative adjusted estimate
shrunk once, and genuinely game-specific adjusted observations assimilated once.
Prove the influence weights and timing on small hand-computable schedules before
evaluating any challenger chronologically. Also test sensitivity to sparse early
opponent networks, garbage-time exposure, prior strength, and uncertainty.

Do not select a change because it puts Alabama above South Carolina. Keep 2026
observations diagnostic/prospective, preserve accepted artifacts, and require a
new contract for any estimator change or promotion. Ratings are a sensible next
focus, but they are not the only possible future improvement: measurements,
the forecast bridge, non-offense offsets, and calibration remain distinct
places where predictive errors can arise.

## Reproduction and authority

- Rating run: `possession-v1-rating-replay-20260927-w4`; raw manifest SHA
  `75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0`.
- Measurement run: `possession-v1-measurements-20260927-w4`; raw manifest SHA
  `c43f66206973e94b27c6cb23fcc5462aff2fc00b7c1f0eaa1a20fdeaace20a4f`.
- Saved [numerical decomposition](2026-09-28-current-v5-ratings-evidence.json)
  records scales, source-game exposure, cumulative z values, prior terms,
  terminal values, and exact serving reconstruction difference.
- Read R2 through configured Preview storage; credentials and `r2` backend
  verified without printing secrets. Database queries used
  `default_transaction_read_only=on`.
- [Current V5 status](../modeling/v5_status.md),
  [methodology](../modeling/possession_rating_methodology.md),
  [manual operator contract](../plans/2026-09-24/02-v5-weekly-operator-and-release-gates.md),
  [product transformation](../plans/2026-09-23/01-v5-product-transformation.md),
  [history replay contract](../plans/2026-09-27/05-weekly-ratings-history-replay.md).
