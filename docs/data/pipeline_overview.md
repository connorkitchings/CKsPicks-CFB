# Data Pipeline Overview

This document provides a comprehensive overview of the data ingestion and processing pipeline for the CFB Model. It details how data flows from the CollegeFootballData (CFBD) API through our ingestion layer, into raw storage, and finally through the feature engineering pipeline to produce modeling datasets.

## High-Level Flow

```mermaid
graph TD
    API[CFBD API] -->|Ingest CLI| Raw[Raw Storage (CSV)]
    Raw -->|Aggregate CLI| Pipeline[Feature Pipeline]

    subgraph "Ingestion Layer"
        Raw
    end

    subgraph "Feature Processing"
        Pipeline --> ByPlay[By-Play]
        ByPlay --> Drives[Drives]
        Drives --> TeamGame[Team-Game]
        TeamGame --> TeamSeason[Team-Season]
        TeamSeason --> OppAdj[Opponent Adjustment]
        OppAdj --> TeamSeasonAdj[Team-Season Adj]
        OppAdj --> TeamWeekAdj[Team-Week Adj]
    end

    TeamWeekAdj --> Training[Model Training]
    TeamSeasonAdj --> Inference[Weekly Inference]
```

## 1. Ingestion Layer

The ingestion layer is responsible for fetching data from the CFBD API and storing it in a standardized raw format.

### Entry Point

The primary entry point is the CLI:

```bash
python scripts/cli.py ingest [ENTITY] --year [YEAR]
```

### Key Components

- **CLI (`scripts/cli.py`)**: Handles argument parsing and dispatches tasks based on the `INGESTION_REGISTRY`.
- **Ingesters (`src/data/*.py`)**: Specialized classes (e.g., `GamesIngester`, `PlaysIngester`) that inherit from `BaseIngester`. They handle:
  - API authentication and fetching.
  - Data transformation and normalization.
  - Partitioning logic.
- **Storage (`src/utils/local_storage.py`)**: Manages file I/O, ensuring data is saved in a partitioned structure (e.g., `data/raw/games/year=2024/week=1/`).

### Entities

- **Teams**: Static team info (conference, mascot, etc.).
- **Venues**: Stadium info.
- **Games**: Schedules, scores, and metadata.
- **Plays**: Raw play-by-play data (most granular).
- **Betting Lines**: Historical spreads and totals.
- **Rosters**: Player information.
- **Coaches**: Coaching staff history.

## 2. Feature Processing Layer

The processing layer transforms raw data into rich features suitable for modeling. It is triggered via the CLI:

```bash
python scripts/cli.py aggregate preagg --year [YEAR]
```

### Pipeline Steps (`src/features/pipeline.py`)

1.  **By-Play (`src/features/byplay.py`)**:

    - Enriches raw plays with context (e.g., "passing down", "red zone").
    - Calculates PPA (Predicted Points Added) if not present.
    - Identifies garbage time.

2.  **Drives (`src/features/core.py` -> `aggregate_drives`)**:

    - Aggregates plays into drive-level stats.
    - Metrics: Points per drive, success rate, explosive drive rate, "Eckel" rate (scoring opportunities).

3.  **Team-Game (`src/features/core.py` -> `aggregate_team_game`)**:

    - Aggregates drives and plays into game-level team stats.
    - Metrics: EPA/play, Success Rate, Explosiveness, Special Teams efficiency.
    - Splits: Rushing vs. Passing, Standard vs. Passing Downs.

4.  **Team-Season (`src/features/core.py` -> `aggregate_team_season`)**:

    - Aggregates Team-Game stats into season-to-date averages.
    - **Recency Weighting**: Applies a weighted average (last 3 games weighted 3, 2, 1) to emphasize recent performance.

5.  **Opponent Adjustment (`src/features/core.py` -> `apply_iterative_opponent_adjustment`)**:
    - Iteratively adjusts team stats based on the strength of their opponents.
    - Algorithm: `Adjusted Stat = Raw Stat - (Opponent Avg - League Avg)`.
    - Runs for 4 iterations to converge.

### Output Datasets

All processed data is stored in `data/processed/` with similar partitioning to raw data.

| Dataset           | Description                                    | Usage                                 |
| :---------------- | :--------------------------------------------- | :------------------------------------ |
| `byplay`          | Enriched play-by-play data.                    | Debugging, granular analysis.         |
| `drives`          | Drive-level outcomes.                          | Drive-based modeling (future).        |
| `team_game`       | Single-game performance metrics.               | Post-game analysis.                   |
| `team_season`     | Season-to-date weighted averages (unadjusted). | Reporting, baseline checks.           |
| `team_season_adj` | **Current** opponent-adjusted ratings.         | **Inference** (predicting next week). |
| `team_week_adj`   | **Point-in-time** opponent-adjusted ratings.   | **Training** (historical validation). |

## 3. Feature Loading & Merging (`src/models/features.py`)

This layer bridges the gap between processed data and model training/inference. It handles joining team stats to games, creating differential features, and managing point-in-time correctness.

### Key Functions

- **`load_weekly_team_features`**: Loads `team_week_adj` for a specific week. This is the **gold standard** for training data as it prevents data leakage (uses only data available before the week).
- **`load_point_in_time_data`**: Orchestrates the full dataset creation for a specific week:
  1.  Loads raw games for the week.
  2.  Loads `team_week_adj` for home and away teams.
  3.  Merges them to create a game-level dataset.
  4.  Adds betting lines (optional) for residual calculation.
  5.  Adds style features (tempo contrast, etc.).
- **`build_differential_features`**: Transforms raw home/away stats into matchup features (e.g., `home_off_epa - away_def_epa`).

## 4. Key Files & Locations

- **Ingestion Logic**: `src/data/`
- **Feature Logic**: `src/features/core.py`
- **Pipeline Orchestration**: `src/features/pipeline.py`
- **Persistence & Caching**: `src/features/persist.py`
- **CLI Entry**: `scripts/cli.py`

## 4. Common Workflows

**Full Backfill for a Year:**

```bash
# 1. Ingest Raw Data
python scripts/cli.py ingest games --year 2024
python scripts/cli.py ingest plays --year 2024
python scripts/cli.py ingest betting_lines --year 2024

# 2. Run Feature Pipeline
python scripts/cli.py aggregate preagg --year 2024
```

**Weekly Update:**

```bash
# 1. Ingest latest week
python scripts/cli.py ingest games --year 2024 --week 10
python scripts/cli.py ingest plays --year 2024 --week 10

# 2. Update features
python scripts/cli.py aggregate preagg --year 2024
```
