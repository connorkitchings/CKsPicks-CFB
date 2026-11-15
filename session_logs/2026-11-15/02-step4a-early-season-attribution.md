# Session: Step 4A early-season error attribution

## TL;DR

- **Worked On:** Step 4A of the V5 baseline audit: where the stage 0 to 3 error of Operational V5 comes from (prior quality, bridge intercept or update speed).
- **Outcome:** No single factor dominates. The stage 0 margin bias (+7.16) is stable by season but is not a constant offset: it reverses to -2.08 at stage 4 while the intercept stays 7.1 to 7.3, and removing it entirely would cut stage 0 MAE by only 0.91. It depends on the matchup (Power 4 hosts against FCS and G5 teams under-predicted by +12.00 and +13.28). Priors alone show the same pattern, and in-season updating does not help before stage 4. Totals show no early-season problem.
- **Plan Contract:** [`docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md`](../../docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md)
- **Approval / Status:** Owner approved running step 4A and the CFBD pull. Contract stays `Draft`. Committed locally on `dev`, not pushed.
- **Blockers:** None.
- **Next:** Owner decides whether to declare a step 4B variant (rating-gap or tier-dependent home margin looks more promising than a stage intercept).

**tags:** ["model-research", "baseline-audit", "early-season", "ratings-lab"]

## Context and Decisions

- Diagnostic only; nothing refitted, no market data. Analysis script was ad hoc, outside the repository.
- Deviation from the plan: the net prior is offense plus defense, because the defense rating is higher-is-better (correlation with margin +0.56 against +0.10 for the difference).
- Bias is actual minus prediction, matching earlier sections (an initial run had the sign reversed and was corrected before any figures were recorded).

## Work Completed

- Pulled returning production and team membership for 2021 to 2025 from CFBD into `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/` with SHA-256 values. Captured today, so historical availability is unverified.
- Joined both prediction sets to prior rank quartile, prior source, returning-production tercile and conference tier; split margin and total error by stage and group with game counts (cells under 30 flagged).
- Compared each season's bridge intercept with stage mean outcomes; computed a constant-shift counterfactual.
- Verified: 3,483 games per target; stage counts 573/301/244/253/2,112; Operational V5 MAE 13.7151 and 13.3709; priors-only 14.4125.

- Owner accepted the recommendation: drafted the step 4B declaration in the contract (candidates B1, B1s, B2, conditional B3; pass condition; tuning on 2015 to 2021, 2022 to 2025 reported once). Not approved to run.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — Step 4A results section
- `docs/plans/index.md` — state line
- Outside the repository: `~/cfb_ratings_lab_v6/output/step4a-2026-11-15/step4a_results.json`, `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/`

## Validation

- [x] Recomputed MAE and counts match the benchmark
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.
