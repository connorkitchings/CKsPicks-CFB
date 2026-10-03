# Team Stats as the Source of Basic Stats (ratings read team stats)

- **Status:** Draft (Phase 1 implemented 2026-10-02; Phase 2 is superseded as execution scope by Window 2 of the [two-window data-integrity contract](../2026-10-03/04-data-integrity-two-window-implementation.md)).
- **Created:** 2026-10-02
- **Planner:** Sol
- **Approval source:** User direction 2026-10-02: basic stats belong to team stats, and the ratings (any version) should consume them; ratings create only rating-specific stats. Phase 1 plan approved the same day.
- **Implementation log:** `session_logs/2026-10-02/06-punt-play-fix-and-team-stats-ownership.md`
- **Commit policy:** Phase 1 committed on `dev` (`5acd051`, `8065c56`); Phase 2 needs its own approved contract before any rating work.

## Goal

One definition of "a play" and one builder of basic per-team stats, with the ratings consuming them instead of re-deriving the same numbers from Silver play-by-play.

## Why now

A hand-check of Western Kentucky vs New Mexico State found that CFBD's `Punt Return` rows reach Silver with `st == 0` (enrichment's special-teams list omitted that play type), so the V5 play filter counted them as 4th-down scrimmage plays by the punting team (`ppa` 0.0, `turnover` 0, yards = return yards). 2026 Silver has 504 such rows, 465 of them eligible by week 5. Effects:

- **Wrong:** `conv_rate_3rd_4th`, `explosive_rate`, `turnover_rate`, and the V5 companions `epa_per_play` and `plays_per_possession`.
- **Not affected:** `ppp`, `epa_per_possession` (the only measures the ratings fit), pass/rush/early-down PPA, success rate, possession counts.
- Ranks moved materially once fixed (week 1-5 republish: up to 52 places on explosive rate, 30 on conversion rate).

## Phase 1 (implemented)

- `src/cks_picks_cfb/data/play_filters.py` owns the play rules: the V5 legacy filter (definition moved unchanged, so signed V5 artifacts are byte-identical) and `scrimmage_play_mask` (legacy filter minus kicking plays). `ratings/possession_measurements.py` imports from it.
- `team_stats.py` uses `scrimmage_play_mask`, reports `punt_plays_excluded`, and publishes a new `ppa_per_play` metric. The matchup page's PPA/play row reads it (not the V5 `epa_per_play` companion).
- Silver enrichment tags `Punt Return` as special teams (`st_punts`) for future builds. No 2026 Silver or V5 rebuild: the V5 lineage stays pinned to the current Silver versions.
- Tests: filters (`tests/test_play_filters.py`), team stats leak guard over eight metrics (`tests/test_team_stats.py`), enrichment (`tests/test_new_features.py`).

### Deviation from the approved Phase 1 plan (explicit)

The plan also moved `derive_is_drive_play` and `true_drive_points` out of `ratings/observations.py`. **That move is deferred to Phase 2.** `true_drive_points` brings its own result dataclass and `MeasurementContractError`, so moving it now would either keep `data/` importing from `ratings/` or fork the exception type; it belongs with the per-game build below. Consequence: until Phase 2, `team_stats.py` still imports the score-stream reconstruction from `ratings.observations`, and the ratings package remains the owner of drive points.

## Phase 2 (design; built at the planned rating rebuild)

1. **Per-game team stats** (`team_game_stats`, signed lake dataset): one row per game, team, role and metric with numerator and denominator, built from Silver with `scrimmage_play_mask`. Includes the basics V5 derives today (eligible possessions, offensive possession points, PPA sum, scrimmage plays, non-offense points) plus the current play and drive metrics. `team_season_stats` becomes an aggregation of it. The drive-point reconstruction and its error type move here from `ratings/observations.py`.
2. **V5 measurement layer becomes rating-specific:** reads `team_game_stats` for counts and sums; keeps cutoff timing, coverage and usability flags, the final-score reconciliation gate, the opponent adjustment, and the `ppp` / `epa_per_possession` fit inputs.
3. **Rebuild order:** Silver (with the enrichment fix) → `team_game_stats` → V5 measurements → ratings, with a delta report against the served lineage; matchup data re-pins to the new manifests.
4. The older `ratings/observations.py` measurement layer (shadow scripts) is re-pointed at team stats or retired in the same contract.
5. Carry into the contract: the 155 eligible non-punt plays with `ppa == 0` are still inside every per-play mean, including `ppa_per_play`; decide whether to treat them as nulls.
6. Open decision for the contract: whether the rebuild changes any rating (it should not for `ppp` and `epa_per_possession`; confirm with the delta report).

## Production steps (user-run)

> **On hold (2026-10-02, re-pointed 2026-10-03):** the production republish below is bundled into the [unified data fix and matchup rollout](../2026-10-03/01-unified-data-fix-and-matchup-rollout.md) (see [known data issues](../../data/known_issues.md)), so the affected tables are written to production once. Do not run it on its own. The commands stay here for when the batch is ready.

Production `team_season_stats` still holds the pre-fix values for conversion, explosive and turnover rate and has no `ppa_per_play`. Preview was republished 2026-10-02 (11,506 rows, weeks 1-5, hand-check matches exactly). To republish production:

```
PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py --season 2026 --weeks 1-5 --environment production --dry-run --diff
PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py --season 2026 --weeks 1-5 --environment production
PYTHONPATH=src:. uv run python scripts/pipeline/verify_team_stats.py --season 2026 --as-of-week 5 --environment production
```

**Order:** run these before (or in the same window as) releasing the web change, because the page reads `ppa_per_play` and shows "—" for that row until the rows exist. The matchup page is closed in production (`CFB_MATCHUP_ENABLED` unset), so a short gap is not user-visible.

Expected dry-run: 11,506 rows, 1,046 only-new (`ppa_per_play`), 2,291 changed, only conversion, explosive and turnover rates changing.

## Out of scope

Rebuilding 2026 Silver or any V5 artifact now; changing any published rating; the 155 eligible non-punt plays whose `ppa` is exactly 0 (likely CFBD nulls hidden by Silver's `fillna(0)`; logged for the rebuild).
