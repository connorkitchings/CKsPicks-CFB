# Feature Catalog

This catalog defines the engineered features and fields used by the MVP modeling pipeline.
It complements `docs/project_org/modeling_baseline.md` and the runbook in
`docs/operations/weekly_pipeline.md`.

## Conventions

- Level: team-season, team-week, game-level, or team-game.
- Types: numeric (int/float), categorical, boolean, datetime, string.
- Naming: snake_case; prefixes encouraged (e.g., `off_`, `def_`, `adj_`).
- All features should be reproducible from source Parquet and deterministic given a seed.

## 1) Team-season aggregates (offense/defense)

<!-- markdownlint-disable MD013 -->
| feature_name | level       | dtype  | definition                                         | inputs                                   | transform                                 | notes |
|--------------|-------------|--------|----------------------------------------------------|------------------------------------------|--------------------------------------------|-------|
| off_epa_pp   | team-season | float  | Season-to-date offensive EPA per play              | plays.parquet (offense team, EPA)        | sum(EPA)/n_plays                           | pace-aware |
| def_epa_pp   | team-season | float  | Season-to-date defensive EPA per play              | plays.parquet (defense team, EPA)        | sum(EPA_allowed)/n_plays_defended          | pace-aware |
| off_sr       | team-season | float  | Offensive success rate                             | plays.parquet                            | mean(success_bool)                         | by CFBD defn |
| def_sr       | team-season | float  | Defensive success rate allowed                     | plays.parquet                            | mean(success_bool_allowed)                 | by CFBD defn |

Add additional per-play and per-possession metrics (yards/play, explosiveness, etc.).

## 2) Opponent-adjusted features (iterative averaging)

- Procedure: 4 iterations of opponent adjustment over team-season rates.
- Last-3 weighting: recent games receive extra weight in the season aggregate.

| feature_name  | base_feature | level       | dtype | definition                               | transform/notes                                |
|---------------|--------------|-------------|------|------------------------------------------|------------------------------------------------|
| adj_off_epa_pp| off_epa_pp   | team-season | float| Opponent-adjusted offensive EPA/play     | 4-iter opponent matrix; weighted last-3 games  |
| adj_def_epa_pp| def_epa_pp   | team-season | float| Opponent-adjusted defensive EPA/play     | same as above                                   |

Document any additional adjusted stats (success rate, explosiveness, etc.).

## 3) Pace and possession-aware features

| feature_name     | level       | dtype | definition                                  | inputs                 | transform |
|------------------|-------------|------|---------------------------------------------|------------------------|-----------|

<!-- markdownlint-enable MD013 -->

Include additional per-possession rates as needed.

## 4) Game-level merge and keys

- Primary keys: `game_id`, `season`, `week`.
- Team identifiers: `home_team`, `away_team`, `team` (normalized casing).
- Join rules documented in feature build script (home/away control added at modeling stage).

## 5) Targets (reference)

- Spread target: `home_final_points - away_final_points` (final margin).
- Total target: `home_final_points + away_final_points` (total points).
- See `docs/project_org/modeling_baseline.md` → Targets.

## 6) Validation checks

- Row counts per season and per team are within expected ranges.
- No nulls in required fields; types are correct.
- Spot-check distributions (EPA, SR) season over season.

## 7) Change management

- Any material change to feature definitions must be recorded in
  `docs/decisions/decision_log.md` with rationale and effective date.
- Keep this catalog up to date alongside code changes in `src/cfb_model/features/`.
