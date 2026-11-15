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

- Owner approved the two read-only checks. Cache holds 1,975 stage 0 to 3 regular-season games for 2015 to 2019 and 2021 (enough to tune); Operational V5 predictions for those seasons must be recomputed. Paired bootstrap spread of the MAE difference: 0.10 (intercept-sized change), 0.23 (large change). Recorded in the B declaration.

- Owner confirmed the thresholds and approved running 4B. Baseline rebuilt from serving states and reproduced the stored predictions exactly. Result: no candidate selected under the declared tuning rule; B2 adds nothing; per-stage intercept (B1s) gains 0.54 stage 0 to 3 MAE on 2022 to 2025 and fixes stage 4 bias but worsens balanced matchups. Owner decision pending (accept, amend rule, forward test, or B3).

- Owner accepted the recommendation (forward test) and asked to test B3 further. Pulled team membership for 2015 to 2019 (hashed), ran B3: 2022 to 2025 stage 0 to 3 MAE 15.01 to 14.09, better in all four seasons and all five tuning seasons; fixes lopsided-matchup bias without B1s's balanced-game cost; fails only the declared early-bias condition on tuning (2016 and 2017). Declared a 2026 holdout test, noting 2026 early weeks are already played so it is a holdout, not forward.

- Owner approved fetching the 2026 pregame states and forecast files from the Preview bucket (read credential; the 2026 data are not local) and ran the declared holdout on 293 stage 0 to 3 games of 2026. B3 gains 0.62 MAE (stage 0 15.40 to 14.20) but over-corrects bias (-2.75 against +0.41) and stage 4 (36 games) is 0.60 worse; B1s gains nothing. Neither passes the declared condition. Zero offsets were used for all arms because 2026 offsets are not in the files.

- Output collision: another session working on the same contract wrote different results to `step4a_results.json` and `step4b_results.json` in the same folders while this session ran, overwriting this session's files. Its files were left in place; this session's results were regenerated from the saved scripts under the names `step4a_attribution_results.json` and `step4b_variants_results.json` and reproduce the recorded figures exactly. That session's work is not in this repository and was not verified, apart from its FBS-vs-FBS stage 0 to 3 figures, which match.

- Owner decision: FBS-vs-FBS is the headline population (confirmed in `docs/status.md`: the release universe excludes FBS-vs-FCS), FBS-vs-FCS secondary. Side-by-side by stage added to the contract. FBS-vs-FBS: Operational V5 margin MAE 13.35 over 2,998 games, early bias +0.84, priors alone match or beat V5 through stage 1. FBS-vs-FCS: correlation +0.39 but mis-levelled (bias +8.86); earlier-only linear recalibration gives MAE 14.24 against 16.00 raw and 15.53 constant.

- Rescored the 4B candidates on FBS-vs-FBS only (owner-approved, no refit): B1s no gain (0.02), B1 worse, B3 gain 0.75 over stages 0 to 3 (every season, tuning and 2026 holdout), early bias over-corrected. The bridge intercept (7.4) blends FBS-vs-FBS games (4.1) and FBS-vs-FCS blowouts (29), about 3 points high for published games.

- Owner accepted the recommendation: declared (not run) a population-aware bridge in the contract: P1 FBS-vs-FCS indicator, P2 FBS-only fit, P3 and P4 the same with the B3 tier terms. Selection on 2018, 2019 and 2021 only, then 2022 to 2025 and the 2026 holdout once each; proposed thresholds await the owner.

## Files Modified

- `docs/plans/2026-11-14/01-v5-baseline-audit-and-analysis-framework.md` — Step 4A results section
- `docs/plans/index.md` — state line
- Outside the repository: `~/cfb_ratings_lab_v6/output/step4b-2026-11-15/step4b_variants_results.json`, `step4b_b3_results.json`, `step4b_holdout_2026_results.json`, `step4a_population_split_results.json`, `step4b_fbs_vs_fbs_rescore.json`, `~/cfb_ratings_lab_v6/source/preview-2026-11-15/`, `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/teams_2015..2019.json`, `~/cfb_ratings_lab_v6/output/step4a-2026-11-15/step4a_attribution_results.json`, `~/cfb_ratings_lab_v6/source/cfbd-2026-11-15/`

## Validation

- [x] Recomputed MAE and counts match the benchmark
- [x] `uv run mkdocs build --strict`
- [x] `git diff --check`

## Amendments and Blockers

- None.
