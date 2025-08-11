# CFBD Data Ingestion Guide

This document outlines the approach for ingesting data from the CollegeFootballData API into our
local Parquet storage (partitioned by entity/year) using the project's storage backend abstraction.

## Data Filtering Strategy

### FBS Only

- We focus exclusively on FBS (Football Bowl Subdivision) teams to reduce data volume and focus on
  major college football
- FBS teams are filtered after fetching from the API using the `classification` field
- As of 2024, there are 134 FBS teams across 11 conferences

### Historical Data Scope

- **Time Period**: The project ingests data for seasons from 2015 through 2024 (inclusive).
- **2020 Season**: Included; note reduced games and potential sparsity due to the pandemic.

### Year-Specific Data

- All data is ingested with year specificity since team information (conferences, classifications)
  changes over time
- Scripts support a `year` parameter to fetch data for a specific season.
- Each table includes a `year` field to track temporal changes

## Ingestion Modules

Data ingestion has been reorganized into reusable modules in `src/cfb_model/data/ingestion/` with a
shared base class for common functionality.

### Teams (`src/cfb_model/data/ingestion/teams.py`)

- **Status**: ✅ Complete
- **Records**: 134 FBS teams for 2024
- **Key fields**: school, conference, classification, mascot, colors, logos
- **Usage**: `python scripts/ingest_cli.py teams --year 2024`
- **Module**: `TeamsIngester`

### Venues (`src/cfb_model/data/ingestion/venues.py`)

- **Status**: ✅ Complete
- **Records**: 150 venues used by FBS games in 2024
- **Key fields**: name, capacity, city, state, coordinates, surface type
- **Usage**: `python scripts/ingest_cli.py venues --year 2024`
- **Module**: `VenuesIngester`
- **Note**: Automatically filters to venues used by FBS games only

### Games (`src/cfb_model/data/ingestion/games.py`)

- **Status**: ✅ Complete
- **Records**: 753 FBS regular season games for 2024
- **Key fields**: teams, scores, venue, date, ELO ratings, line scores
- **Usage**: `python scripts/ingest_cli.py games --year 2024`
- **Module**: `GamesIngester`
- **Dependencies**: Requires venues table to be populated first

### Plays (`src/cfb_model/data/ingestion/plays.py`)

- **Status**: ✅ Complete (Rewritten)
- **Records**: Play-by-play data for FBS games
- **Key fields**: down/distance, yardage, play type, clock, teams
- **Usage**: `python scripts/ingest_cli.py plays --year 2024 --limit-games 5`
- **Module**: `PlaysIngester`
- **Dependencies**: Requires games table to be populated first

### Betting Lines (`src/cfb_model/data/ingestion/betting_lines.py`)

- **Status**: ✅ Complete
- **Records**: Sportsbook betting lines for FBS games
- **Key fields**: spread, over/under, moneylines by provider
- **Usage**: `python scripts/ingest_cli.py betting_lines --year 2024 --limit-games 10`
- **Module**: `BettingLinesIngester`
- **Dependencies**: Requires games table to be populated first

### Rosters (`src/cfb_model/data/ingestion/rosters.py`)

- **Status**: ✅ Complete
- **Records**: Player roster data for FBS teams
- **Key fields**: player info, position, physical stats, hometown
- **Usage**: `python scripts/ingest_cli.py rosters --year 2024 --limit-teams 3`
- **Module**: `RostersIngester`
- **Dependencies**: Requires teams table to be populated first

### Coaches (`src/cfb_model/data/ingestion/coaches.py`)

- **Status**: ✅ Complete
- **Records**: Coaching staff data for FBS teams
- **Key fields**: coach info, hire date, season records
- **Usage**: `python scripts/ingest_cli.py coaches --year 2024 --limit-teams 3`
- **Module**: `CoachesIngester`
- **Dependencies**: Requires teams table to be populated first
- Betting Lines: Sportsbook data for FBS games
- Rosters: Player information for FBS teams

## API Authentication

All scripts use the CFBD API with Bearer token authentication:

- API key stored in `.env` file as `CFBD_API_KEY`
- Uses official `cfbd` Python library with `access_token` parameter

## CFBD 101 (Endpoints and Formats)

- Endpoints used (typical): teams, venues, games, plays, lines (betting lines), rosters, coaches
- Key parameters: `year`, `seasonType` (regular/postseason), `week`, `team`, `gameId`
- Pagination/limits: library handles paging; respect provider limits; batch per-week when possible
- Common fields:
  - Teams: `school`, `conference`, `classification`
  - Games: `id`, `season`, `week`, `home_team`, `away_team`, scores, `venue`
  - Plays: `game_id`, `offense`, `defense`, `down`, `distance`, `yards_gained`, `play_type`
  - Lines: `game_id`, provider, `spread`, `over_under`, timestamps
- Quick checks (recommended):
  - Pull a few games for a known week and print keys per record
  - Verify FBS-only filtering by `classification`
  - Validate row counts vs manifests after write

## Data Quality Notes

- All optional fields handled with `getattr()` for safety
- Dataset is partitioned by `entity` and `year` for efficient access (e.g., `data/raw/games/year=2024/`)
- Each partition includes a `manifest.json` with row counts and metadata to enable validation
- Referential integrity between entities is validated using utilities in `src/cfb_model/data/validation.py`
- Idempotent writes: partitions are atomically overwritten to avoid partial writes and duplicates
- Duplicates are detected and removed prior to write when applicable

## CLI Flags

All ingestion commands support a common set of flags:

- `--data-root`: Base directory for the Parquet dataset (default: `./data/raw`)
- `--season_type`: Season type (`regular`, `postseason`) when applicable
- `--workers`: Parallel worker count for API calls
- `--exclude-seasons`: Comma-separated years to skip (optional; default: none)
