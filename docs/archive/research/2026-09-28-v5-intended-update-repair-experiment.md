# V5 intended-update repair experiment

**Status:** Research completed 2026-09-28. No production rating, forecast,
selection, R2 artifact, or Neon state changed. This report follows the
[implementation contract](../plans/2026-09-28/v5-estimator-three-way-review.md)
and its cutoff-specific amendment.

## What the experiment establishes

The accepted historical V5 estimator was reproduced across **35,740 pregame
team-role states**: maximum absolute mean error `8.88e-16`, variance error
`2.22e-16`, and exposure error `0`. Its refitted bridge reproduces all **7,318
frozen V5 prediction rows** to `2.84e-14`. The comparison therefore starts from
an exact historical control, rather than a similarly named approximation.

The principal finding is larger than the originally suspected repeated-snapshot
weighting. The historical materializer assigns each source game to the earliest
later-week forecast boundary, then looks for the *source team's* adjusted value
in a snapshot that contains only the **target game's two teams**. Most source
games have no such value. Across 2015–2019 and 2021–2025, only **330** usable
source-game-role observations are in the certified V5 stream. Just **1,926 of
35,740** pregame team-role states (5.4%) have current-season exposure. The
game-specific and single-cumulative arms have exposure in **29,376 states
(82.2%)**. This difference in historical evidence coverage dominates a simple
interpretation of the forecast results as an isolated correction of
double-counting. The 2026 live replay has a separate team-boundary and terminal
path; the Alabama/South Carolina live ratings do contain their played games.

## Fixed design and arms

All arms use the accepted historical population, possession definition, PPP
measurements, preseason priors, `0.60` annual carryover including the
2019→2021 two-year gap, previous-season scales, exposure constant `k=8`,
offsets, eligible prediction keys, and separately refitted alpha-10 Ridge
bridges. No bookmaker data enters rating inputs. A source game enters only a
later week once its kickoff is at least six hours old. The four-pass adjustment
uses the graph available at each forecast cutoff and excludes the game being
forecast. Where opponent context is absent, the source game's raw PPP is used
with an explicit reason; this fallback was not invoked in the accepted corpus.

| Arm | Evidence entering the update |
| --- | --- |
| Certified V5 replica | Cumulative adjusted team value frozen at the source game's first qualifying *historical* boundary, weighted by that game's possessions; the certified missing-snapshot behavior is retained. |
| Game-specific at cutoff | Each prior source game's own adjusted PPP at the current cutoff, with its possessions once. This is the requested repair. |
| Single cumulative | The certified adjusted cumulative snapshot at the cutoff, with all source possessions, shrunk toward the same prior once. |
| Game-specific at first boundary | Each source game's own adjusted PPP frozen at first qualifying boundary; a timing sensitivity, not a candidate selected for promotion. |

For three equal-exposure games and fixed opponent adjustment, the V5
snapshot-stream evidence component weights the underlying games
`11/18`, `5/18`, `1/9` (61.1%, 27.8%, 11.1%). The repaired game-specific arm
weights them one third each. With a unit-variance prior and three eight-possession
games, the prior share is `1/4` in both; the single cumulative arm shrinks the
one 24-possession adjusted average by that same share. These exact identities,
same-week exclusion, the six-hour delay, future-result invariance, missing
opponent context, and 2020 rejection have focused tests.

## Historical forecast results

The headline set is 2022–2025, **3,659 identical games per target**. Each arm
has its own chronological Ridge refit and earlier-only residual calibration.
CRPS and 90% interval results describe the separately calibrated forecast
distribution, not calibration of the rating posterior variance.

| Arm | Margin MAE | Margin RMSE | Margin CRPS | Margin 90% coverage | Total MAE | Total RMSE | Total CRPS | Total 90% coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Certified V5 replica | 14.320 | 18.140 | 10.222 | 91.1% | 13.662 | 17.001 | 9.612 | 91.8% |
| Game-specific at cutoff | **13.744** | **17.442** | **9.788** | 91.5% | **13.507** | **16.817** | **9.506** | 92.3% |
| Single cumulative | 13.744 | 17.442 | 9.788 | 91.5% | 13.507 | 16.817 | 9.506 | 92.3% |
| Game-specific at first boundary | 14.115 | 17.885 | 10.046 | 91.2% | 13.502 | 16.816 | 9.505 | 92.1% |

Margin bias (actual minus prediction) changes from `+0.047` in the control to
`+0.193` in the repair; total bias changes from `-2.615` to `-2.387`.
Average 90% interval widths change from `62.32` to `59.47` margin points and
`58.91` to `58.36` total points. The machine-readable report includes bias,
width, RMSE, CRPS, coverage, and row counts for every arm, season, and
completed-game stage.

Paired season/week block bootstrap (2,000 replicates, seed `20260928`) puts the
cutoff-specific repair's MAE gain over historical V5 at **0.575 margin points**
(90% interval `0.307`–`0.858`) and **0.156 total points** (`0.115`–`0.201`).
Against the first-boundary game-specific arm, the cutoff-specific arm gains
`0.371` margin points (`0.281`–`0.471`) and changes total MAE by `-0.005`
(`-0.017`–`0.007`). The single-cumulative arm and cutoff-specific game arm
have **zero states differing above `1e-10`**; maximum absolute difference is
`4.88e-15`. No observed source game lacked the opponent context needed for the
weighted game values to equal the certified cumulative snapshot. Sparse graphs
remain an explicit tested fallback, but did not distinguish these arms here.

The margin result is concentrated in the established 4+ completed-games route:

| Completed-game stage | Games | V5 margin MAE | Repaired margin MAE | V5 total MAE | Repaired total MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 573 | 15.92 | 16.14 | 13.29 | 13.19 |
| 1 | 301 | 14.28 | 14.42 | 13.38 | 13.20 |
| 2 | 244 | 14.99 | 15.11 | 12.92 | 12.61 |
| 3 | 253 | 13.00 | 13.17 | 13.68 | 13.50 |
| 4+ | 2,288 | 14.00 | 12.97 | 13.87 | 13.72 |

The repaired arm's margin MAE is worse in stages 0–3 and better in 4+. The
2022–2025 margin MAEs, V5 then repair, are `14.64→14.08`, `13.85→13.82`,
`14.64→13.93`, and `14.16→13.16`; total MAEs are `14.09→13.87`,
`13.90→13.70`, `13.32→13.25`, and `13.36→13.22`. Separate 2018, 2019,
and 2021 diagnostics are in the machine-readable report. In those seasons the
repair also improves margin MAE, but they were not combined into the headline
selection set.

## 2026 South Carolina–Alabama diagnostic

Using the pinned, read-only Week 4 measurement and rating parents, we rebuilt
the four-pass terminal graph after all Week 4 results and applied the same
prior and `k=8` to each prior game once. The terminal cumulative values match
the certified live measurement. This is a **postgame diagnostic**, not a frozen
pregame forecast or a selection criterion.

| Team / role | Same preseason share | Accepted V5 mean | Game-specific diagnostic mean |
| --- | ---: | ---: | ---: |
| Alabama offense | 21.6% | 1.818 | 2.002 |
| Alabama defense | 21.3% | 1.047 | 0.982 |
| South Carolina offense | 28.6% | 1.893 | 1.225 |
| South Carolina defense | 28.8% | 0.985 | 0.536 |

The resulting illustrative overall values are Alabama `1.492` and South
Carolina `0.880`, compared with accepted V5's `1.433` and `1.439`. For South
Carolina offense, Kent State contributes `0.435` rather than V5's `0.660`,
Mississippi State `0.539` rather than `0.714`, and the Alabama game `0.203`
rather than `0.470`; the unchanged prior contributes `0.049`. The detailed
source-game IDs, adjusted values, possession weights, and contributions are in
the linked diagnostic JSON. Reversing the ordering is not evidence of better
forecast skill on its own.

## Interpretation and reproducibility

The historical V5 replica and its bridge are exact, but the sparse historical
boundary path and fuller live 2026 path have different evidence semantics.
Thus the paired historical gains cannot be read as a clean expected benefit
from replacing the *live* estimator. The first-boundary sensitivity separates
the value-timing effect from the dominant historical coverage change. Neither
the reported 90% forecast intervals nor the analytic rating variance proves
that correlated cumulative snapshots yield well-calibrated team uncertainty.
No production promotion is authorized by this result.

The research run used read-only Preview R2 parents and wrote local output only.
Parent SHA-256 values are in the [machine-readable report](2026-09-28-v5-intended-update-results.json):
measurement `10b380d6…`, rating `9d00e635…`, forecast `186f4dc1…`, verifier
`ba60166b…`, and repair `b55af0dd…`. The 2026 diagnostic pins measurement
`c43f6620…` and rating `75e016e1…` in its
[source-game decomposition](2026-09-28-v5-intended-update-live-diagnostic.json).
The implementation lives in `src/cks_picks_cfb/ratings_lab/` and can be run
with `scripts/research/v5_intended_update_review.py --local-output <outside-repo-path>`;
`scripts/research/v5_intended_update_live_diagnostic.py` repeats the 2026
diagnostic. The local historical result manifest SHA-256 is recorded in the
implementation session log. The separate V6 R2 bucket was not required.
