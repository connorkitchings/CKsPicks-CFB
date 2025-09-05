# Time Calculation Fix

**Date:** 2025-09-03  
**Status:** Resolved  
**Impact:** Critical - Fixes data pipeline aggregation

## Problem

The CFB data aggregation pipeline was failing during drive and team-game aggregations due to incorrect time remaining calculations. The `time_remaining_after` field was being calculated incorrectly by concatenating string values instead of properly adding time components mathematically.

## Root Cause

In `src/cfb_model/data/aggregations/byplay.py`, the `calculate_time_features()` function was using string concatenation instead of mathematical addition for computing total time remaining in the game.

**Incorrect calculation:** String concatenation resulted in values like "315" instead of 3600 seconds for "15:00" in Q1.

## Solution

**Fixed Formula:** `time_remaining_after = (4 - quarter) * 15 * 60 + (clock_minutes * 60 + clock_seconds)`

**Logic:**
- For quarters 1-4: Total remaining time = (quarters remaining after current) × 15 minutes + current quarter time remaining
- For overtime: Use clock time directly (no future quarters)

**Examples:**
- Q1 6:32 → `(4-1) × 15 × 60 + (6×60 + 32) = 2700 + 392 = 3092s` ✅
- Q2 13:39 → `(4-2) × 15 × 60 + (13×60 + 39) = 1800 + 819 = 2619s` ✅
- Q4 2:30 → `(4-4) × 15 × 60 + (2×60 + 30) = 0 + 150 = 150s` ✅

## Verification

- **Formula Validation:** Comprehensive test scripts validated calculations across all quarters and overtime scenarios
- **Production Testing:** Successfully processed 2024 Week 1 data (6,746 plays, 39 games, 3,413 drives)
- **Pipeline Integration:** Complete play-to-drive aggregation pipeline now runs without errors

## Impact

- **Data Quality:** Time remaining now ranges correctly from 0s to 3600s
- **Quarter Transitions:** Proper handling of time at quarter boundaries  
- **Downstream Features:** Drive time consumption, pace metrics, and other time-based features now calculate correctly
- **Pipeline Stability:** Aggregation pipeline no longer fails on time calculation errors

## Files Modified

- `src/cfb_model/data/aggregations/byplay.py` - `calculate_time_features()` function
- Added comprehensive code comments documenting the time calculation logic

---

**Resolution:** The time calculation fix is complete and verified. All downstream aggregations now receive properly calculated time features, enabling accurate drive and game-level analytics.
