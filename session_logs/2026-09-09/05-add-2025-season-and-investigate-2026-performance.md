# Session: Add 2025 Season to Web App and Investigate 2026 Low Win Rate

## TL;DR
- **Worked On:** Added 2025 season support to the web app and investigated why 2026 V4 model predictions have low win rate (36%) compared to 2025 (51%)
- **Outcome:** Successfully added 2025 season support with V4 predictions (50.9% spread win rate, 52.6% total win rate). Identified root cause of 2026 performance issue: feature mismatch between training and inference pipelines.
- **Plan Contract:** `.opencode/plans/2026-09-09-rebuild-2026-predictions.md` (Draft)
- **Approval / Status:** Web app changes complete and tested locally. 2026 fix plan created and documented, awaiting user review.
- **Blockers:** None
- **Next:** User reviews the 2026 rebuild plan, then implements the fix by rebuilding 2026 features with `--preseason-features-ref-uri` parameter.

## Context and Decisions

### Part 1: Add 2025 Season to Web App

**Goal:** Allow users to view 2025 season predictions on the web app to demonstrate the V4 model's >50% win rate.

**Approach:**
1. Add multi-season support to the web app (2025 and 2026)
2. Publish V4 predictions for 2025 to the database
3. Test locally before production deployment

**Key Decisions:**
- Use existing V4 benchmark predictions from `rating_v4_historical_predictions` dataset
- These predictions are already point-in-time correct (trained on 2021-2024, tested on 2025)
- Fetch missing betting lines for weeks 14-16 from CFBD
- Backfill missing week 1 game results from schedule data

### Part 2: Investigate 2026 Low Win Rate

**Problem:** 2026 V4 model predictions have 36% spread win rate vs 51% in 2025.

**Investigation:**
1. Verified no data leakage (2026 model trained on 2021-2025 data)
2. Compared feature datasets used for 2025 vs 2026 predictions
3. Identified feature mismatch: 2025 used `point_in_time_matchups_v5` (with preseason features), 2026 used `point_in_time_matchups` (v4, missing preseason features)

**Root Cause:**
- V4 model was trained on features that include empirical-Bayes shrunk features
- These features are computed from base features at inference time
- At week 1, all teams have 0 completed games, so base features are NaN
- The operational pipeline doesn't include `--preseason-features-ref-uri` parameter
- Without preseason features, the model performs poorly in early weeks

## Work Completed

### Web App Changes
1. Added multi-season support to `web/src/lib/publication.ts`
   - Added `ALLOWED_SEASONS = [2025, 2026]`
   - Added `isAllowedSeason()` helper function
   - Updated `publicationScope` to expose `allowedSeasons`

2. Updated `web/src/app/page.tsx` to respect season URL parameter
   - Read `season` from URL params
   - Validate against allowed seasons
   - Historical seasons (2025) show all available weeks
   - Current season (2026) respects `CFB_PUBLICATION_WEEKS` filter

3. Created `web/src/components/SeasonSelector.tsx` component
   - Dropdown to switch between 2025 and 2026
   - Updates URL with `?season=` parameter
   - Resets week when changing seasons

4. Updated `web/src/components/Header.tsx` to include season selector
   - Added `allowedSeasons` prop
   - Shows season selector when multiple seasons available

### Database Changes
1. Fetched missing betting lines for 2025 weeks 14-16 from CFBD
2. Published V4 predictions for 2025 (761 games, weeks 1-15)
3. Created prediction runs with proper V4 model_id
4. Scored predictions against actual results
5. Backfilled missing week 1 game results from schedule data
6. Updated games table with V4 model_id

### Documentation
1. Created comprehensive plan: `.opencode/plans/2026-09-09-rebuild-2026-predictions.md`
2. Updated `docs/ops/weekly_pipeline.md` with preseason features requirement
3. Updated `docs/ops/production_runbook.md` with troubleshooting section
4. Updated `docs/plans/index.md` to reference new plan
5. Created session logs documenting the investigation

## Files Modified

### Web App (6 files)
- `web/src/lib/publication.ts` - Added multi-season support
- `web/src/app/page.tsx` - Updated season resolution logic
- `web/src/components/Header.tsx` - Integrated season selector
- `web/src/components/SeasonSelector.tsx` - New component (untracked)
- `web/.env` - Added publication config for local testing

### Documentation (4 files)
- `docs/ops/weekly_pipeline.md` - Added preseason features requirement section
- `docs/ops/production_runbook.md` - Added troubleshooting section for low win rate
- `docs/plans/index.md` - Added reference to new plan
- `docs/plans/2026-09-09/rebuild-2026-predictions.md` - New plan (untracked)

### Session Logs (2 files)
- `session_logs/2026-09-09/04-investigate-2026-low-win-rate.md` - Investigation log
- `session_logs/2026-09-09/05-add-2025-season-and-investigate-2026-performance.md` - This log

## Validation

### Web App
- [x] `git diff --check` - No trailing whitespace or merge conflicts
- [x] `uv run mkdocs build --quiet` - Documentation builds successfully
- [x] `npm run lint` - No linting errors
- [x] `npm run typecheck` - No TypeScript errors
- [x] `npm run build` - Production build succeeds

### Database
- [x] 2025 V4 predictions published (761 games)
- [x] All 2025 weeks have game results
- [x] Win rates calculated correctly (50.9% spread, 52.6% total)
- [x] Web app displays 2025 predictions correctly

### Documentation
- [x] Plan created with step-by-step remediation
- [x] Weekly pipeline documentation updated
- [x] Production runbook updated with troubleshooting guide
- [x] Plan index updated

## 2025 V4 Model Performance

| Metric | Record | Win Rate |
|--------|--------|----------|
| **Spread** | 379-366-16 | **50.9%** ✅ |
| **Total** | 398-358-5 | **52.6%** ✅ |

### Per-Week Spread Results
| Week | Record | Win % | Games |
|------|--------|-------|-------|
| 1 | 28-20-0 | 58% | 48 |
| 2 | 26-22-2 | 54% | 50 |
| 3 | 25-22-0 | 53% | 47 |
| 4 | 22-27-1 | 45% | 50 |
| 5 | 24-25-2 | 49% | 51 |
| 6 | 24-25-1 | 49% | 50 |
| 7 | 28-25-3 | 53% | 56 |
| 8 | 30-29-0 | 51% | 59 |
| 9 | 28-23-2 | 55% | 53 |
| 10 | 25-27-0 | 48% | 52 |
| 11 | 31-20-0 | 61% | 51 |
| 12 | 28-30-0 | 48% | 58 |
| 13 | 26-33-1 | 44% | 60 |
| 14 | 30-33-4 | 48% | 67 |
| 15 | 4-5-0 | 44% | 9 |

## 2026 Performance Issue

### Current State
- Week 0: 25% (8 games)
- Week 1: 38.1% (43 games)
- Week 2: TBD (49 games)

### Root Cause
Feature mismatch between training and inference:
- **Training:** `point_in_time_matchups_v5` (with preseason features)
- **Inference:** `point_in_time_matchups` (v4, missing preseason features)

### Solution
Rebuild 2026 features with `--preseason-features-ref-uri` parameter pointing to the correct preseason features dataset.

## Handoff Notes

- **Resume at:** User reviews the plan in `.opencode/plans/2026-09-09-rebuild-2026-predictions.md`
- **Watch out for:** The fix requires rebuilding features for weeks 0-2 with `--preseason-features-ref-uri` parameter, then regenerating predictions. This is a multi-step process that requires careful validation.
- **Key insight:** The operational pipeline must always include preseason features when building features for the V4 model. This is now documented in the weekly pipeline guide.

## Proposed Commit

**Commit message:**
```
feat(web): add 2025 season support and document 2026 feature mismatch

- Add multi-season support (2025/2026) to web app with season selector
- Publish V4 predictions for 2025 (50.9% spread, 52.6% total win rate)
- Document root cause of 2026 low win rate (feature mismatch)
- Update weekly pipeline and production runbook with preseason features requirement
- Add troubleshooting guide for low win rate in production runbook
```

**Files to include:**
- `web/src/lib/publication.ts`
- `web/src/app/page.tsx`
- `web/src/components/Header.tsx`
- `web/src/components/SeasonSelector.tsx`
- `docs/ops/weekly_pipeline.md`
- `docs/ops/production_runbook.md`
- `docs/plans/index.md`
- `docs/plans/2026-09-09/rebuild-2026-predictions.md`
- `session_logs/2026-09-09/04-investigate-2026-low-win-rate.md`
- `session_logs/2026-09-09/05-add-2025-season-and-investigate-2026-performance.md`

**tags:** ["web-app", "2025-season", "investigation", "model-performance", "feature-engineering", "documentation"]
