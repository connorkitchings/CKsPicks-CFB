# Feature Engineering Plan

This note outlines the staged aggregation flow for turning raw CFBD play-by-play into
season-to-date features ready for opponent adjustment.

---

## Goals

- Produce reliable, reproducible team-game and team-season feature sets.
- Follow a staged pipeline with clear inputs/outputs and validation points.
- Stay aligned with `docs/project_org/modeling_baseline.md` and `docs/project_org/feature_catalog.md`.

---

## Staged Aggregation

1. Plays → Enhanced Plays

- Input: Raw plays for a season.
- Transformations: normalize fields (clock → seconds, yardline/possession fields), create boolean
  indicators (rush/pass, success, explosiveness, penalty, sack, turnover, garbage_time flag),
  standardize team columns (`offense`, `defense`).
- Output: CSV partitions under `processed/byplay/year/<YYYY>/...`
- Schema basis: see `docs/cfbd/schemas.md` ("Play Schema").

1. Enhanced Plays → Drives

- Group by continuous possessions to summarize per-drive metrics (plays, yards, points, success
  rate, EPA/PPA totals/means, time of possession, result).
- If a canonical drive table is available, align to that; otherwise reconstruct via possession
  changes and scoring events.
- Output: CSV partitions under `processed/drives/year/<YYYY>/...`

1. Drives → Team-Game

- Aggregate by game and team: tempo, success rates, explosiveness, early/late down splits,
  red zone, penalties, turnovers, special teams, field position, finishing drives.
- Output: CSV partitions under `processed/team_game/year/<YYYY>/...`

1. Team-Game → Team-Season-to-Date

- Cumulative and rolling aggregates through each week (exclude current game when training/predicting).
- Apply recency weights (3/2/1) per `docs/project_org/feature_catalog.md`.
- Output: CSV partitions under `processed/team_season/year/<YYYY>/...`

1. Opponent Adjustment (next phase)

- Iterative opponent adjustment per feature catalog (4 passes, league-mean centering), producing
   opponent-adjusted season features.
- Output: CSV partitions under `processed/team_season_adj/year/<YYYY>/...`

---

## Next Steps: Implementing Point-in-Time Feature Generation

To prevent data leakage during model training, it is critical that features for any given game are calculated using only data from preceding weeks. The current aggregation pipeline creates end-of-season summaries, which are not suitable for direct use in training.

The immediate next step is to implement a weekly, point-in-time feature generation process.

### Plan:

1.  **Adapt Existing Logic**: The logic for this weekly calculation has been located in the `CFB_Functions.ipynb` notebook, specifically within the `calculate_stats_rolling` and `calculate_adjstats_rolling` functions. This code provides a proven template for the required process.

2.  **Integrate into Pipeline**: This logic will be adapted and integrated into the main data pipeline in `src/cfb_model/data/aggregations/`. The goal is to create a new function or modify the existing pipeline to generate a training dataset where each row (a game) is associated with features calculated from the season-to-date data *up to the week of that game*.

3.  **Generate Training Data**: The updated pipeline will be used to generate the complete, leakage-free training dataset, which will then be used for model development.

This replaces the previous next step of defining a play feature schema, as that work has largely been completed in `src/cfb_model/data/aggregations/byplay.py`.

---

## Validation & Manifests

- Each processed partition includes a `manifest.json` with row counts and metadata.
- Add a season summary CSV under `reports/metrics/` (e.g., `features_<year>_summary.csv`).

---

## References

- Modeling baseline: `docs/project_org/modeling_baseline.md`
- Feature catalog: `docs/project_org/feature_catalog.md`
- CFBD schemas: `docs/cfbd/schemas.md`
