# Session: Game Card Redesign - Regime Chip Removal & Team Records

**Date:** 2026-09-02  
**Duration:** ~2 hours  
**Type:** Feature implementation

## Summary

Redesigned game cards to remove the regime marker chip and add team season records next to team names. Records are computed point-in-time (as-of each game's kickoff) to ensure historical accuracy.

## Changes Made

### 1. Removed Regime Chip
- Removed `REGIME_LABEL` constant from `GameRow.tsx`
- Removed regime chip rendering from meta row (kept high-confidence star)
- Regime field remains on Game type (used by ModelAccuracyPanel)

### 2. Added Team Records
- Added `homeRecord` and `awayRecord` fields to `BaseGame` type in `queries.ts`
- Implemented `getSeasonRecordTimeline()` helper to fetch completed games
- Implemented `withRecords()` helper to attach records to game objects
- Records computed by walking through completed games in kickoff order
- Point-in-time correctness: each game's record reflects only games completed before its kickoff
- Records display as "(W-L)" next to team names, hidden when 0-0

### 3. Updated Fixtures
- Added `homeRecord` and `awayRecord` fields to test fixtures
- Set sample records for visual testing (Ohio State "1-0", Texas null)

## Technical Details

### Record Computation
```typescript
// Fetch all completed games for the season, ordered by kickoff
const getSeasonRecordTimeline = cache(async (season: number) => {
  // Query games joined with game_results where completion_state = 'completed'
  // Return array of { startDate, homeTeam, awayTeam, homePoints, awayPoints }
});

// Attach records to games by walking timeline
function withRecords(games, completed) {
  // For each game, advance through completed games with startDate < game.startDate
  // Update running W-L records for each team
  // Snapshot records at game's kickoff
}
```

### Display Logic
```typescript
// TeamLine component
{record && (
  <span className="text-xs tabular-nums text-ink-faint">({record})</span>
)}
```

### Point-in-Time Correctness
- Records computed per-game based on kickoff timestamp
- Historical week pages show accurate records as-of that week
- No leakage of future game results into past records

## Verification

### Local Testing
- Started dev server with production publication settings
- Verified 43 Week 1 games render with correct records
- Confirmed regime chips removed
- Confirmed records display for teams that played Week 0:
  - Eastern Michigan (1-0), San José State (0-1)
  - Stanford (1-0), USC (1-0), Memphis (1-0)
  - Hawai'i (0-1), UNLV (0-1)
  - Florida State (1-0)

### Quality Gates
- `npm run lint` ✓
- `npm run typecheck` ✓
- `npm run build` ✓

## Files Modified

1. `web/src/components/GameRow.tsx`
   - Removed regime chip rendering
   - Added record prop to TeamLine component
   - Updated both predictions and market mode cards

2. `web/src/lib/queries.ts`
   - Added homeRecord/awayRecord to BaseGame type
   - Added getSeasonRecordTimeline() helper
   - Added withRecords() helper
   - Wired into getGamesForWeek() and getMarketGamesForWeek()

3. `web/src/test/fixtures/publication.ts`
   - Added homeRecord/awayRecord fields to fixture base

## User Feedback

User requested:
- Remove regime marker chip ("doesn't really tell us anything")
- Add team records next to team names (e.g., "TCU (1-0)")
- Keep everything else the same

Implementation matches request exactly.

## Next Steps

- Deploy to production when ready
- Monitor for any edge cases (ties, canceled games, etc.)
- Consider adding record display to other views if needed

## Notes

- Records hidden when 0-0 to reduce visual noise
- Record format: "W-L" (e.g., "1-0", "0-1", "2-3")
- Ties not handled (CFB doesn't have ties in regular season)
- Canceled games excluded from record computation (completion_state filter)
