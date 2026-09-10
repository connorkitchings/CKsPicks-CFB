# Session: Investigate 2026 Low Win Rate

## TL;DR
- **Worked On:** Investigated why 2026 V4 model predictions have low win rate (36%) compared to 2025 (51%)
- **Outcome:** Identified root cause - feature mismatch between training and inference pipelines
- **Plan Contract:** `.opencode/plans/2026-09-09-rebuild-2026-predictions.md`
- **Approval / Status:** Draft plan created, awaiting user review
- **Blockers:** None
- **Next:** User reviews plan, then implement the fix

## Context and Decisions

### Problem Statement
User noticed that 2026 V4 model predictions have significantly lower win rates than 2025:
- 2025: 50.9% spread win rate (761 games)
- 2026: 36.0% spread win rate (108 games through week 2)

Week-by-week breakdown showed the issue is most severe in early weeks:
- 2025 week 1: 58.3% (48 games)
- 2026 week 0: 25.0% (8 games)
- 2026 week 1: 38.1% (43 games)

### Investigation Process

1. **Verified no data leakage:** Confirmed 2026 predictions use model trained on 2021-2025 data (not 2026 data)

2. **Compared feature datasets:**
   - 2025 used `point_in_time_matchups_v5` (includes preseason features)
   - 2026 used `point_in_time_matchups` (v4, missing preseason features)

3. **Identified missing features:**
   - V4 model expects 47+ features per route
   - Includes empirical-Bayes shrunk features like `home_shrunk_adj_off_epa_pp`
   - These are computed from base features at inference time
   - At week 1, all teams have 0 completed games, so base features are NaN
   - Model was trained on data where these features had values (weeks 2+)
   - At inference, missing features cause poor predictions

4. **Root cause:** The operational pipeline (`assemble_model_ready_features.py`) supports `--preseason-features-ref-uri` but it's not being used for 2026 predictions. The 2025 benchmark pipeline included this parameter.

### Key Findings

**2025 benchmark dataset:**
- Dataset: `point_in_time_matchups_v5`
- Version: `fe55e75884c7665527e740d3`
- Built from:
  - `point_in_time_matchups_core` (base features)
  - `baseline_predictions_oof` (baseline predictions)
  - `v4_preseason_team_features` version `8c47f6d5ccdced2365e4dfdd` (preseason features) ✅

**2026 operational dataset:**
- Dataset: `point_in_time_matchups`
- Version: `30ac8b5d37719160ff9d751c` (week 1)
- Built from:
  - `point_in_time_matchups_core` (base features)
  - `baseline_predictions_oof` (baseline predictions)
  - ❌ NO preseason features

## Work Completed

1. **Created comprehensive plan:** `.opencode/plans/2026-09-09-rebuild-2026-predictions.md`
   - Root cause analysis
   - Step-by-step remediation
   - Validation criteria
   - Rollback plan

2. **Updated documentation:**
   - `docs/ops/weekly_pipeline.md` - Added "Preseason Features Requirement" section
   - `docs/ops/production_runbook.md` - Added "Troubleshooting: Low Win Rate" section

3. **Validated findings:**
   - Confirmed 2025 and 2026 use different feature datasets
   - Verified preseason features dataset exists in R2
   - Confirmed model bundle expects `point_in_time_matchups_v5`

## Files Modified

- `.opencode/plans/2026-09-09-rebuild-2026-predictions.md` - Created comprehensive plan
- `docs/ops/weekly_pipeline.md` - Added preseason features requirement section
- `docs/ops/production_runbook.md` - Added troubleshooting section for low win rate

## Validation

- [x] Root cause identified and documented
- [x] Plan created with step-by-step remediation
- [x] Documentation updated to prevent future occurrences
- [ ] Plan reviewed by user
- [ ] Plan implemented (pending)
- [ ] 2026 predictions rebuilt with correct features (pending)
- [ ] Win rates validated (pending)

## Handoff Notes

- **Resume at:** User reviews the plan in `.opencode/plans/2026-09-09-rebuild-2026-predictions.md`
- **Watch out for:** The fix requires rebuilding features for weeks 0-2 with `--preseason-features-ref-uri` parameter, then regenerating predictions. This is a multi-step process that requires careful validation.
- **Key insight:** The operational pipeline must always include preseason features when building features for the V4 model. This is now documented in the weekly pipeline guide.

**tags:** ["investigation", "model-performance", "feature-engineering", "documentation"]
