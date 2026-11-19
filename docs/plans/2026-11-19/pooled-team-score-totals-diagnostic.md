# Pooled team-score totals diagnostic

- **Status:** Draft (nothing is approved to run; execution waits until after the 2026-12-13 final close and an explicit owner go-ahead)
- **Created:** 2026-11-19
- **Planner:** Sol
- **Approval source:** Owner decision of 2026-11-19 (chat): draft only, no model candidate before 2026-12-13. This file is not an authorization to run.
- **Implementation log:** none yet. Drafted in `session_logs/2026-11-19/01-v6-methodology-research.md`.
- **Commit policy:** Local research changes on `dev`; no push without owner instruction.

## Why this exists, and what it does not repeat

The [V6 methodology survey](../../research/v6-methodology-survey-2026-11.md) proposed a team-score formulation for totals. Two earlier results bound what is still untested, and this contract is limited to the remainder:

- **Step 4C (run 2026-11-15)** tested shrinkage (ridge alpha 1 to 1000) and two linear feature forms of the **same four ratings** (F1: one combined offense-minus-defense feature; F2: offense sum and defense sum) in a single **total-regression** head. No form gained more than 0.02 total MAE against a declared 0.20; the predictions' correlation with actual totals is +0.13 to +0.18, only 0.07 to 0.09 MAE better than a constant. 4C concluded the flat total is a signal limit, not an over-shrinking or cancellation defect. **This contract does not re-run shrinkage or the sum forms.**
- **Step 4D (run 2026-11-15)** tested the stored neutral-site flag on the **margin** head (neutral-site bias overshot from -1.50 to +2.53 on 80 FBS-vs-FBS games; low power). **This contract does not re-test a neutral-site flag.**
- The [totals drive-sample declaration](../../modeling/offseason_totals_drive_sample.md) builds new upstream inputs (scoring-opportunity creation, finishing, starting field position). That is the rating-state input path. This contract uses **no new inputs**.

What 4C did not test: a **pooled symmetric team-score** model (one coefficient set for both teams, each team's points from its own offense and the opponent's defense) and a **multiplicative / log-link** form. 4C's head regressed the game total on home and away terms with separate coefficients. The question below is whether the structure, not the shrinkage, was the limit.

## Experiment declaration

| Field | Content |
|---|---|
| Question | Does a pooled symmetric team-score model, `team_pts ~ own_off + opp_def + role`, or its multiplicative log-link form, carry more game-total signal from the existing Operational V5 rating states than the baseline four-term total bridge? |
| Changes | Total head only. Rows are team-games (two per game). **S1 (additive):** identity link, features own offense, opponent defense and a role term (+1 home team, -1 away team, so one coefficient set serves both roles). **S2 (multiplicative):** log link on the same features, penalized with the equivalent of the baseline's alpha 10. Predicted total = predicted home points + predicted away points in both arms. No neutral-site flag (it exists locally for 2021 to 2025 only, and 4D found no effect). |
| Frozen | Ratings and rating states, offsets, the margin head and its predictions, interval construction and calibration, earlier-only fitting, the regular-season corpus (postseason removed), and the pre-declared population definition. |
| Refitted | The total head only, earlier-only for each validation season (fitted on strictly earlier seasons, same recipe as the baseline bridge), per arm. The baseline total predictions are rebuilt from the serving states and must reproduce the stored Operational V5 totals with a largest difference of 0.0 before anything is scored. A training-mean total is reported as a sanity check. |
| Population | Regular-season FBS-vs-FBS (headline), FBS-vs-FCS reported separately. Selection seasons 2018, 2019 and 2021 (pooled); 2022 to 2025 reported once. 2026 is **not** scored (holdout rule; scored once after the final close under the protocol). |
| Cannot show | That no better total exists (the ratings may simply not carry it); anything about margin; anything about new inputs (opportunity creation, finishing, field position, weather); a clean out-of-sample result (2022 to 2025 are examined seasons, not independent confirmation); any 2027 behavior. |

## Declared outcome reading (proposed thresholds, for owner approval before the run)

- **Material gain:** best arm beats baseline total MAE by at least 0.20 on the selection seasons and on 2022 to 2025, with the two-sided 95% paired block interval (amendment 2, season/week blocks, game-level interval reported alongside) above zero. This is the same bar 4C used.
- **Signal reading (diagnostic, not adoption):** report predicted-total SD, correlation with actual totals, and MAE against the training mean, for the baseline, S1 and S2, pooled and by season. "No new signal" means gain under 0.05 on both windows and correlation within 0.03 of the baseline.
- **If there is no new signal:** the structure is ruled out, and the totals fix moves **upstream to rating-state inputs**, i.e. the drive-sample path (scoring opportunities, finishing, starting field position) and weather, each under its own declaration. No further totals-head structure is run.
- **If there is signal below the bar:** record it as a diagnostic and let the owner decide whether to pre-declare a larger design. It is not adopted.
- Adoption of anything still requires the existing adoption block in the protocol.

## Execution gates

1. Not before the 2026-12-13 final close, and not without an explicit owner go-ahead recorded here.
2. Before running: freeze the script and record its SHA-256 and the rebuild-root and input hashes; add the scoring run to the ledger; confirm the baseline reproduces to 0.0.
3. The run is read-only against existing local research outputs; no production, schema, web or live-pipeline path is touched.
4. No 2026 game is scored.

## Acceptance (for the later run, not for this draft)

- The baseline reproduces the stored Operational V5 totals exactly; counts match (3,483 regular-season games per target; FBS-vs-FBS 2,998).
- Every table above is reported with games per cell, and the result class (material gain, signal below the bar, no new signal) is recorded in the audit contract's results section.
