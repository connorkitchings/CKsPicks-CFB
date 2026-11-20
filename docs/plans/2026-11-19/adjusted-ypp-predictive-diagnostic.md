# Adjusted YPP predictive diagnostic

- **Status:** Draft (nothing is approved to run; execution waits for the 2026-12-13 final close and an explicit owner go-ahead under the offseason protocol)
- **Created:** 2026-11-19
- **Approval source:** Owner decision of 2026-11-19 (chat): do both the display and this diagnostic, display first. This file is not an authorization to run.
- **Implementation log:** none yet. Drafted in `session_logs/2026-11-19/02-ypp-display-planning.md`.
- **Related:** [Yards per play display](yards-per-play-display.md), which supplies the estimator.
- **Commit policy:** Local research changes on `dev`; no push without owner instruction.

## Why this exists

Indiana ranks #5 in opponent-adjusted yards per play (YPP) but #39 in the V5 offense rating, and across teams the two rank-correlate at 0.86. V5's offense rating uses only opponent-adjusted points per possession. The Indiana case shows the gap: strong in yards, adjusted EPA per play and explosive rate, weak in points per scoring opportunity (#84) and red-zone success (36% against 43%).

**Hypothesis:** finishing (points per scoring opportunity) is noisier than play-level efficiency, so an offense state informed by YPP or EPA per play predicts future scoring better than points per possession alone.

## Stage A: diagnostic (no model change)

- **Seasons:** 2015-2019 and 2021-2025 (no 2020), point-in-time.
- **Comparison:** for each team-season and week, compare season-to-date adjusted points per possession, adjusted EPA per play, adjusted YPP and success rate on how well each predicts rest-of-season adjusted points per possession, using correlation and out-of-sample R squared.
- **Stability:** measure week-to-week stability of points per scoring opportunity against YPP.
- **Data:** the historical Silver play-by-play the ratings lab already reads, and the estimator from the display contract.

## Stage B: only if Stage A shows incremental information

One ratings-lab candidate adds an adjusted-YPP-implied scoring term to the offense and defense evidence. It is scored by `scripts/research/run_v6_tournament.py` against Operational V5. Adoption uses the protocol's two-sided 95% paired block interval and the 0.20 MAE material-gain bar. 2026 stays the one-shot holdout.

## Cannot show

- Causal claims.
- Anything about market edge.
- 2027 behavior.

## Execution gates

1. Not before the 2026-12-13 final close, and not without an explicit owner go-ahead recorded here.
2. Before running: freeze the script and record its SHA-256 and the input hashes.
3. Stage A is read-only against existing local research outputs; no production, schema, web or live-pipeline path is touched.
4. No 2026 game is scored before the protocol's one-shot holdout step.
