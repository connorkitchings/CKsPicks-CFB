# Session: Contribution spread for Operational V5

## TL;DR

- **Worked On:** The owner-approved measurement of how much each rating term, bridge coefficient and offset moves Operational V5's historical predictions.
- **Outcome:** Flat totals come from small fitted total coefficients (0.5 to 1.75 points per standard deviation of a rating, against 7 to 11 for margin), with offense-defense cancellation as a secondary cause. Sparse updates, compressed ratings and offsets are ruled out. Venue flags are constant and dropped by the fit.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved on 2026-11-14 ("Yes, measure it"); run on 2026-11-15. Contract stays `Draft`.
- **Blockers:** None.
- **Next:** Owner revises the step 4 experiment list in light of steps 2 and 3.

**tags:** ["model-research", "baseline-audit", "totals", "ratings-lab"]

## Context and Decisions

- Decomposed the 7,318 predictions already scored on 2026-11-14; no new model and no new scoring population.
- Local files only. Nothing pushed; Sunday is the weekly close day.

## Work Completed

- Rebuilt each prediction as intercept plus four rating terms plus offset with the project's design and target functions; the sum equals the stored predictions to 1.4e-14.
- Measured the spread of every term, the bridge coefficients per validation season, and the correlations among terms and with outcomes.

- Next approved step ("Yes, run it"): upstream temporal check. Zero violations across 170,379 contributions in the serving states; prior source seasons all earlier; bridge folds and calibration earlier-only; offsets consistent. A future-data removal test (2024 observations from week 8 on deleted, September inputs) left all 2,264 earlier states unchanged and changed 1,402 of 1,412 later ones.
- Defect found: 415 postseason games carry `week` 1, so they receive no current-season evidence and are forecast from preseason priors alone (all 1,660 serving states). Not a leak. Operational V5 2022 to 2025 margin MAE is 14.32 on the 176 postseason games against 12.84 on regular-season stage 4 games; excluding postseason the pooled figure is 13.713 against 13.742. Recorded, not fixed.

- Owner decision ("Exclude them"): postseason games are excluded from the historical benchmark. Rule verified on every season. Existing predictions filtered, no refit: Operational V5 on 2022 to 2025 regular season is margin MAE 13.7130, total 13.3782 over 3,483 games. The neutral-site finding shrinks (126 regular-season games, margin bias -2.69, not -4.32 over 328); season openers are worse than reported (margin MAE 16.18, bias +5.89).

- Owner approval ("Yes, refit without them"): postseason rows removed from training, calibration and scoring; three baselines refitted with unchanged evaluation code. Benchmark, 2022 to 2025, 3,483 games: Operational V5 margin MAE 13.7151, total 13.3709; Historical V5 14.2960, 13.6062. The refit moves MAE by at most 0.009 and margin bias from +0.43 to +0.19.

- Owner approval ("Yes, start step 3"): baselines, scoring accounting and possession volume on regular-season games. Margin: earlier-season mean 17.47, preseason priors only 14.41, Operational V5 13.72; the 0.70 from in-season updating arrives entirely at stage 4. Total: earlier-season mean 13.65, Operational V5 13.37. Ledger: 93.9% of games reconcile exactly; eligible offense is 86.4% of points and 80.4% of the total's variance. Possessions correlate +0.065 with the final total and points per possession +0.772; the pregame possession average correlates about +0.02 to +0.05 with the total. Possession volume is not the missing totals input, which contradicts the interpretation recorded earlier the same day.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — contribution section, next scope
- `docs/plans/index.md` — state line
- Outside the repository: `~/cfb_ratings_lab_v6/output/operational-v5-historical-2026-11-14/contribution_spread.json`

## Validation

- [x] Decomposition check against stored predictions (largest difference 1.4e-14)
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** "Next executable scope" item 8 in the contract.
- **Watch out for:** the reading that totals need inputs the bridge lacks is an interpretation; step 3 tests it. The home-offense asymmetry in total coefficients is unexplained.
