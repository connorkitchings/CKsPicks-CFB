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

## Feature Engineering Source of Truth

The definitive and canonical implementation of all feature engineering logic resides in the Python modules within the `src/cfb_model/data/aggregations/` directory. This includes play-level transformations, aggregations to drives and games, and the point-in-time feature generation required to prevent data leakage.

The `CFB_Functions.ipynb` notebook, which previously contained exploratory work, is now considered deprecated. It should only be used as a historical or conceptual reference. For any development or validation work, the code in the `src` directory is the single source of truth.

---

## Validation & Manifests

- Each processed partition includes a `manifest.json` with row counts and metadata.
- Add a season summary CSV under `reports/metrics/` (e.g., `features_<year>_summary.csv`).

---

## References

- Modeling baseline: `docs/project_org/modeling_baseline.md`
- Feature catalog: `docs/project_org/feature_catalog.md`
- CFBD schemas: `docs/cfbd/schemas.md`
