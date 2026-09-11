# Plan: Add 2025 Season as Viewable Historical Data

**Status:** Draft  
**Created:** 2026-09-09  
**Scope:** Web app only (no pipeline or database changes)

---

## Objective

Enable the web app to display 2025 season games with the same functionality as 2026, allowing users to view the model's 2025 performance (which achieved >50% win rate). This provides transparency into historical picks.

---

## Current State

### Architecture
- **Database:** Already season-agnostic. `games`, `prediction_runs`, and `predictions` tables all have `season` columns with indexes.
- **Web app:** Currently hardcoded to show only 2026 via `publicationScope.season` in `web/src/lib/publication.ts`.
- **URL structure:** Already supports `?season=` parameter, but `resolveTarget()` in `page.tsx` ignores it and always uses `publicationScope.season`.
- **Week navigation:** `WeekNav` component already sets season in URL params.

### Data Availability
- 2025 data exists in the database (referenced in test fixtures as `comparisonSeason: 2025`).
- 2025 was the "locked test" season for V4 model evaluation.
- All 2025 weeks should be viewable (historical data, no future leakage concern).

---

## Implementation Plan

### Phase 1: Update Publication Scope (publication.ts)

**File:** `web/src/lib/publication.ts`

**Changes:**
1. Replace single `DEFAULT_SEASON` with `ALLOWED_SEASONS` array: `[2025, 2026]`
2. Update `publicationScope` to expose:
   - `allowedSeasons: number[]` - list of viewable seasons
   - `defaultSeason: number` - fallback season (2026 for current production)
   - Keep existing `season`, `weeks`, `mode` for backward compatibility
3. Add helper function `isAllowedSeason(season: number): boolean`
4. Update `parseSeason()` to validate against allowed seasons

**Rationale:** Maintains backward compatibility while enabling multi-season support. The env var `CFB_PUBLICATION_SEASON` still controls the default, but users can navigate to other allowed seasons.

---

### Phase 2: Update Page Resolution Logic (page.tsx)

**File:** `web/src/app/page.tsx`

**Changes to `resolveTarget()`:**
1. Read `season` from URL params (already in `SearchParams` type)
2. Validate requested season is in `publicationScope.allowedSeasons`
3. If invalid or missing, fall back to `publicationScope.season` (default)
4. For 2025 (historical): show all available weeks (no `publicationScope.weeks` filter)
5. For 2026 (current): apply `publicationScope.weeks` filter as before
6. Update `getAvailableWeeks()` call to use the resolved season

**Changes to main component:**
1. Pass resolved season to all child components
2. Ensure `getGamesForWeek()`, `getSystemStatsThroughWeek()`, and `getHistoricalModelContext()` receive the correct season

**Rationale:** Allows URL-driven season selection while maintaining publication controls for the current season.

---

### Phase 3: Create Season Selector Component

**File:** `web/src/components/SeasonSelector.tsx` (new)

**Design:**
- Dropdown or segmented control showing allowed seasons (2025, 2026)
- Similar styling to `WeekNav` for consistency
- Updates URL with `?season=` parameter
- Highlights current/active season
- Shows "Historical" badge for 2025

**Integration:**
- Add to header or as a standalone navigation element
- Position: Above or beside `WeekNav` when multiple seasons are available
- Only render if `publicationScope.allowedSeasons.length > 1`

---

### Phase 4: Update Header Component

**File:** `web/src/components/Header.tsx`

**Changes:**
1. Accept `allowedSeasons` prop
2. Display selected season prominently
3. Add visual indicator for historical vs. current season (optional)

---

### Phase 5: Testing and Validation

**Local Testing:**
1. Set `CFB_PUBLICATION_SEASON=2026` in `.env.local`
2. Run `npm run dev` in `web/` directory
3. Verify:
   - Default view shows 2026 (current season)
   - Can navigate to 2025 via URL: `?season=2025`
   - 2025 shows all available weeks
   - Week navigation works for both seasons
   - Season selector updates URL correctly
   - Stats and records calculate correctly for 2025
   - Historical context banner shows 2024 comparison for 2025

**Edge Cases:**
- Invalid season in URL (e.g., `?season=2024`) → falls back to default
- Missing 2025 data → shows "No games loaded" message
- Week navigation across season boundary → resets to first available week

---

## Files to Modify

1. `web/src/lib/publication.ts` - Multi-season support
2. `web/src/app/page.tsx` - Season resolution logic
3. `web/src/components/SeasonSelector.tsx` - New component
4. `web/src/components/Header.tsx` - Display selected season
5. `web/.env.example` - Document new env var (optional)

---

## Database Impact

**None.** The database already supports multiple seasons. No migrations or data changes required.

---

## Backward Compatibility

- Existing URLs without `?season=` continue to work (default to 2026)
- `CFB_PUBLICATION_SEASON` env var still controls default season
- `CFB_PUBLICATION_WEEKS` still filters current season weeks
- Test mode (`CFB_UI_TEST_MODE`) behavior unchanged

---

## Rollout Strategy

1. **Local testing:** User tests with `.env.local` configuration
2. **Preview deployment:** Deploy to Vercel preview with `CFB_PUBLICATION_SEASON=2026`
3. **Production:** Merge to main after validation

---

## Success Criteria

- ✅ Users can view 2025 season games by selecting 2025 or navigating to `?season=2025`
- ✅ 2025 shows all available weeks (not filtered by `CFB_PUBLICATION_WEEKS`)
- ✅ Week navigation works independently for each season
- ✅ Stats and records calculate correctly for 2025
- ✅ No regression in 2026 functionality
- ✅ Local testing passes all validation checks

---

## Open Questions

1. **Season selector placement:** Header vs. standalone navigation bar?
2. **2025 week filtering:** Show all weeks or only weeks with published predictions?
3. **Historical context:** Should 2025 show a "historical data" banner?

---

## Next Steps

1. Review and approve this plan
2. Implement Phase 1-4
3. Local testing
4. Iterate on UI/UX based on feedback
5. Deploy to production
