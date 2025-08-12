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

1) Plays → Enhanced Plays

- Input: Raw plays for a season.
- Transformations: normalize fields (clock → seconds, yardline/possession fields), create boolean
  indicators (rush/pass, success, explosiveness, penalty, sack, turnover, garbage_time flag),
  standardize team columns (`offense`, `defense`).
- Output: `features/<year>/plays_enhanced.parquet`
- Schema basis: see `docs/cfbd/schemas.md` ("Play Schema").

2) Enhanced Plays → Drives

- Group by continuous possessions to summarize per-drive metrics (plays, yards, points, success
  rate, EPA/PPA totals/means, time of possession, result).
- If a canonical drive table is available, align to that; otherwise reconstruct via possession
  changes and scoring events.
- Output: `features/<year>/drives.parquet`

3) Drives → Team-Game

- Aggregate by game and team: tempo, success rates, explosiveness, early/late down splits,
  red zone, penalties, turnovers, special teams, field position, finishing drives.
- Output: `features/<year>/team_game.parquet`

4) Team-Game → Team-Season-to-Date

- Cumulative and rolling aggregates through each week (exclude current game when training/predicting).
- Apply recency weights (3/2/1) per `docs/project_org/feature_catalog.md`.
- Output: `features/<year>/team_season_s2d.parquet`

5) Opponent Adjustment (next phase)

- Iterative opponent adjustment per feature catalog (4 passes, league-mean centering), producing
   opponent-adjusted season features.
- Output: `features/<year>/team_season_adj.parquet`

---

## Immediate Next Step: Define Play Feature Schema v0.1

We’ll lock a minimal enhanced-play schema to support downstream aggregation. Start with raw fields
we rely on, plus derived columns.

- Key raw fields (from CFBD Play):
  - `gameId`, `period`, `clock.minutes`, `clock.seconds`, `offense`, `defense`, `down`, `distance`,
  `yardsGained`, `yardline`, `yardsToGoal`, `playType`, `playText`, `ppa`, `scoring`
- Normalized/derived fields:
  - `clock_seconds` (int): period-adjusted seconds remaining in game or per-period (TBD; choose one
  and document)
  - `is_pass`, `is_rush`, `is_penalty`, `is_sack`, `is_turnover`, `is_score`, `is_garbage_time`
  - `success` (bool): define via standard success formula (1st: ≥50% to go; 2nd: ≥70%; 3rd/4th: 100%)
  - `explosive` (bool): yardage threshold by play type (e.g., rush ≥12, pass ≥16)
  - `field_pos_100` (float): normalized field position [0,100]
  - `epa` (float): use `ppa` if available; otherwise placeholder for later EPA calc
  - `offense_team`, `defense_team` (string): canonicalized names/ids

Once agreed, we will codify this as a Pydantic model and write a transform to produce
`plays_enhanced.parquet` per season.

---

## Validation & Manifests

- Each output emits a manifest with row counts and feature coverage stats: `features/<year>/manifest.json`.
- Add summary CSVs under `reports/metrics/` (e.g., `features_<year>_summary.csv`).

---

## References

- Modeling baseline: `docs/project_org/modeling_baseline.md`
- Feature catalog: `docs/project_org/feature_catalog.md`
- CFBD schemas: `docs/cfbd/schemas.md`
