# Session: Contribution spread for Operational V5

## TL;DR

- **Worked On:** The owner-approved measurement of how much each rating term, bridge coefficient and offset moves Operational V5's historical predictions.
- **Outcome:** Flat totals come from small fitted total coefficients (0.5 to 1.75 points per standard deviation of a rating, against 7 to 11 for margin), with offense-defense cancellation as a secondary cause. Sparse updates, compressed ratings and offsets are ruled out. Venue flags are constant and dropped by the fit.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved on 2026-11-14 ("Yes, measure it"); run on 2026-11-15. Contract stays `Draft`.
- **Blockers:** None.
- **Next:** Owner decides on the upstream temporal check, then work-order step 3.

**tags:** ["model-research", "baseline-audit", "totals", "ratings-lab"]

## Context and Decisions

- Decomposed the 7,318 predictions already scored on 2026-11-14; no new model and no new scoring population.
- Local files only. Nothing pushed; Sunday is the weekly close day.

## Work Completed

- Rebuilt each prediction as intercept plus four rating terms plus offset with the project's design and target functions; the sum equals the stored predictions to 1.4e-14.
- Measured the spread of every term, the bridge coefficients per validation season, and the correlations among terms and with outcomes.

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
