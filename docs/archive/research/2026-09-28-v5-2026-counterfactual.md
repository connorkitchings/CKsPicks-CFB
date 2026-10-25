# 2026 V5 intended-update counterfactual

**Status:** Completed as local research on 2026-09-28. No production rating,
forecast, public pick, R2 object, or Neon row was changed. The concrete
[pregame team-role ratings](2026-09-28-v5-repaired-2026-pregame-ratings.csv),
[three-arm forecasts](2026-09-28-v5-repaired-2026-predictions.csv), and
[machine-readable results](2026-09-28-v5-repaired-2026-results.json) are saved
with this report. The ratings CSV has one row for each team and role at each
forecast cutoff, including its preseason prior, variance, usable possessions,
and source-game IDs. The full source-game contribution explanations remain in
the reproducible local Parquet output.

## Answer

Yes: the repaired 2026 ratings improve the *retrospective* margin forecasts on
the current completed 215-game sample. Replacing only the 2026 rating inputs
while keeping the accepted bridge fixed lowers margin MAE from **15.91 to
15.38**. Refitting the same alpha-10 Ridge bridge on repaired 2015–2019 and
2021–2025 ratings lowers it further to **14.51**. Total MAE moves from 12.21
to 12.20 and 12.12, respectively. This is a concrete positive result for
spread prediction; the total changes are too small to establish a gain.

| Arm | 2026 rating evidence | Through-2025 bridge | Margin MAE | Margin RMSE | Total MAE | Total RMSE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Accepted V5 control | Certified live rating replay | Frozen accepted fit | 15.909 | 19.537 | 12.209 | 15.277 |
| Rating-only repair | One adjusted value per source game at cutoff | Frozen accepted fit | 15.376 | 18.810 | 12.199 | 15.272 |
| Full repaired counterfactual | Same one-game-one-observation update | Refit on repaired historical ratings | **14.512** | **17.888** | 12.123 | 15.198 |

For the paired 215 games, a 2,000-replicate game bootstrap stratified within
completed week gives a 90% interval of **0.07–1.01** margin MAE points gained
for the rating-only arm and **0.75–2.00** for the refitted arm. The corresponding
total intervals span zero (`-0.04–0.06` and `-0.03–0.20`). These intervals
describe variation in this five-week sample; they do not turn a reconstructed
backtest into prospective evidence. Week 1 margin MAE is worse in the refitted
arm and unchanged in the rating-only arm, so the improvement is not uniform
across slates.

## What was held fixed

The three arms use the same 215 completed Week 0–4 game keys, actual scores,
offsets, host/venue features, completed-game stages, six-hour and earlier-week
evidence rule, prior means and variances, 2025-derived scales, 0.60 carryover,
PPP possession definition, four-pass adjustment, and exposure constant `k=8`.
The 2026 repair recalculates each prior game's opponent adjustment on the graph
available at each forecast cutoff and gives that game its own possessions once.
Only the full counterfactual refits the bridge; it keeps the accepted feature
set, alpha, training seasons, and 0.05 scaling floor. No 2026 outcome is used
to fit either bridge.

The control fit reproduced the certified exported-bridge predictions for all
430 completed-game target rows within `7.11e-15` and all 112 frozen Week 5
target rows within `7.11e-15`. The repaired replay generated **1,084 pregame
team-role states** (271 games × two teams × two roles) and complete predictions
for the same 271 games. The 2026 offense and defense scales recomputed from
the pinned 2025 terminal values match the accepted scale exactly.

## Week 5 predictions

Week 5 has **56 games, 112 target predictions**, and no outcome score in this
evaluation. The fully repaired margin predictions differ from the frozen V5
predictions by 7.60 points on average in absolute value (maximum 34.88); the
rating-only arm differs by 6.65 points on average. For totals those figures are
1.09 and 0.57 points. These are genuine changes in model predictions, but
there is no Week 5 skill result yet. As a ratings example at the Week 5 cutoff,
Alabama has repaired offense/defense means `2.002/0.982` and South Carolina
`1.225/0.536`. Their ordering is illustrative, not a selection criterion.

## Interpretation and limits

This evaluation uses a Week 4 certified measurement capture and 2026 schedule
read after those games, then reconstructs earlier pregame states with strict
cutoffs. It is **retrospective** for Weeks 0–4, even though each forecast
calculation excludes its own and later games. It must not be counted as 215
prospectively frozen picks. The Week 5 counterfactual was made before the slate
was scored, but these research predictions were not activated or published.

The historical V5 control had unusually sparse evidence because of the
documented boundary-assignment defect. Consequently, the larger full-arm gain
includes the effect of retraining on a much richer historical rating signal;
the rating-only arm is the cleaner measure of what changing the live 2026
ratings alone does. The repaired 2026 priors remain the certified V5 priors, so
this experiment does not revise the preseason lineage. The early-week sample
is small, and calibration and betting performance were not evaluated here.
The result supports continuing research and collecting prospective paired
slates. It is not a production promotion decision.

## 2025 dependency and production decision

**Redoing 2025 rating updates is already part of the full refit arm.** Its
through-2025 bridge training frame replaces every historical pregame rating
state, including 2025, with the repaired version. The rating-only arm leaves
that bridge untouched, which is why the two arms answer different questions.

The existing **2026 preseason priors do not consume 2025 final ratings**. The
live prior builder reads each team's 2025 terminal opponent-adjusted PPP and
2025 usable possession count, standardizes against the 2025 team distribution,
and applies the `0.60` carryover. Recomputing this formula from the pinned
terminal measurements reproduced all 276 certified 2026 prior rows exactly
(maximum mean and variance difference `0`). Changing the 2025 rating update
alone would therefore not alter these priors. Changing the underlying 2025
terminal measurements, possession definition, or prior formula would be a
different experiment and could alter them.

**Recommendation: keep accepted V5 selected in production for now.** The
2026 retrospective margin result is strong enough to justify the repaired
candidate as a shadow successor, but it is not a release decision: the early
games were rebuilt after the fact, the current Week 5 paired forecasts remain
unscored, and total gains have no clear evidence. A production successor should
first have its complete 2025/2026 lineage and prediction intervals independently
verified, then be judged against prospectively frozen paired slates under a
separate exact release contract. Six slates are not a fixed gate; the decision
should use the amount and quality of evidence actually available.

## Reproduction

The pinned Week 4 measurement manifest is `c43f6620…`, rating manifest
`75e016e1…`, inference bundle `f80b63ef…`, and frozen Week 5 forecast manifest
`799fecfc…`. Full parent and local-frame hashes are in the machine-readable
result. `scripts/research/v5_2026_source_import.py` imports the 2026 frames
through read-only Preview R2 access into a caller-selected local cache.
`scripts/research/v5_2026_counterfactual.py` consumes that cache, the pinned
historical cache from the [V5 intended-update experiment](2026-09-28-v5-intended-update-repair-experiment.md),
and its historical repaired-state Parquet; it writes full rating explanations,
all three prediction arms, paired deltas, and scorecard to a local output path
outside repository `./data/`. The CSVs linked above are exact exports of that
run. The implementation is isolated in the research lab and does not change
the production V5 estimator or inference path.
