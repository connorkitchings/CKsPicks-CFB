# Session: External Data Feature Engineering (Phase 2+3)

## TL;DR
- **Worked On:** Integrating external data sources into the modeling pipeline to find market edge beyond public efficiency metrics
- **Completed:** All Phase 2+3 tasks — Elo exposure, SP+/FPI/SRS ratings, recruiting composite, AP/Coaches rankings, and enhanced situational features (timezone, elevation, dome, rest×travel)
- **Blockers:** None
- **Next:** Run CV on 2022 fold with `extended_v1` feature config to measure improvement vs. baseline

## Changes Made

- **`src/cks_picks_cfb/features/external.py`** *(new)*: Three merge functions for external data:
  - `merge_external_ratings()` → `home/away_sp_rating`, `home/away_fpi`, `home/away_srs` + diffs
  - `merge_recruiting_composite(n_years=4)` → `home/away_talent_composite` + `talent_diff`
  - `merge_rankings()` → `home/away_rank`, `rank_diff`, `is_ranked_home/away` (unranked=26)
  - All gracefully no-op when data is missing; accept optional storage parameter

- **`src/cks_picks_cfb/features/situational.py`**: Added Part 3 to `merge_situational_features()`:
  - `timezone_diff`: game venue tz offset − home venue tz offset (0 for home team)
  - `eastward_travel`: binary flag when away team travels east
  - `altitude_diff`: game elevation − home elevation (0 for home team)
  - `is_dome_game`: binary flag from venue dome column
  - `rest_travel_fatigue`: `travel_distance_km / (days_of_rest + 1)` interaction
  - `_TZ_OFFSET` lookup dict at module level (IANA tz strings → UTC hour offset)

- **`src/cks_picks_cfb/features/v2_recency.py`**: `_merge_for_training()` now:
  - Computes `elo_diff = home_pregame_elo − away_pregame_elo`
  - Calls all three external merge functions automatically

- **`scripts/pipeline/generate_weekly_bets.py`**: Removed `home_pregame_elo`, `away_pregame_elo` from `drop_cols` (postgame elo still dropped — it's future data)

- **`conf/features/extended_v1.yaml`** *(new)*: Full feature config combining matchup_v2 core with all new external + situational features

- **`tests/test_external_features.py`** *(new)*: 19 unit tests covering all three merge functions with mock storage

## Testing
- [x] `ruff format .` — clean
- [x] `ruff check .` — clean
- [x] 19 new tests pass; 160 total pass, 0 regressions

## Technical Details

**Storage pattern for external.py:** All merge functions call `_get_storage(storage)` which defaults to `get_storage()` (data.storage, uses `raw/{entity}` path prefix). Compatible with both R2 and local backends.

**Venue feature lookup:** Uses `venues_df.set_index("id").to_dict("index")` + `.map(dict)` instead of merges to avoid column name collision issues from the double venues_locations merge in Part 2.

**Game venue ID column:** After Part 2's double venues_locations merge, the game venue ID may be renamed to `venue_id_game` due to suffix collision. Part 3 checks for both: `"venue_id_game" if "venue_id_game" in merged_df.columns else "venue_id"`.

**Rankings averaging:** AP Top 25 + Coaches Poll ranks are averaged per team per week, rounded to nearest integer. Unranked teams get value 26.

## Notes for Next Session

**Resume at:** CV test — run single fold (2022) with `extended_v1` feature config

**To run CV fold:**
```bash
uv run python scripts/cross_validation.py \
  --config conf/experiment/v2_recency.yaml \
  --features conf/features/extended_v1.yaml \
  --fold 2022
```

**Key context:**
- All new features are already in the data pipeline via `_merge_for_training()` — no separate ingest step needed (data already in storage from prior ingestion)
- External ratings, recruiting, rankings are season-level data → no issue with data leakage for in-season predictions
- Elo is pregame (available before game) → safe to use as feature
- `venues_df` must have `timezone`/`elevation`/`dome` columns for Part 3 to activate — verify with a smoke test

**Watch out for:**
- SP+/FPI data may not exist for all years (especially FPI pre-2021) → merge functions return matchup_df unchanged if data missing
- Rankings are week-level; the matchup `week` must be normalized (postseason weeks +15) for correct join
- Talent composite for unranked/small programs may be NaN → model imputer should handle

**Next steps:**
1. Run CV fold 2022 with `extended_v1` config, compare ROI/AUC vs. baseline `matchup_v2`
2. Check feature importance — which external features actually move the needle?
3. If CV still negative: consider walk-forward CV (not LOSO) for better temporal integrity
4. If CV positive: expand to full 4-fold CV before declaring victory

**tags:** ["features", "external-data", "situational", "elo", "recruiting", "rankings", "pipeline"]
