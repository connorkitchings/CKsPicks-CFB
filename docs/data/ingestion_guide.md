# CFBD Data Ingestion Guide

This document outlines the approach for ingesting data from the CollegeFootballData API into our
local CSV storage for both raw and processed data using the project's storage backend abstraction.

## Data Filtering Strategy

### FBS Only

- We focus exclusively on FBS (Football Bowl Subdivision) teams to reduce data volume and focus on
  major college football
- FBS teams are filtered after fetching from the API using the `classification` field
- As of 2024, there are 134 FBS teams across 11 conferences

### Historical Data Scope

- **Time Period (ingested today)**: Seasons 2014 through 2024 (inclusive, excluding 2020).
- **2020 Season**: Excluded due to data sparsity and pandemic-related inconsistencies.
- **Modeling training window**: 2014–2024, excluding 2020. 2014 ingestion backfill is tracked in
  `docs/planning/roadmap.md` backlog (ID 18) and will be added in a future sprint.

### Year-Specific Data

- All data is ingested with year specificity since team information (conferences, classifications)
  changes over time
- Scripts support a `year` parameter to fetch data for a specific season.
- Each table includes a `year` field to track temporal changes

## Ingestion Modules

Data ingestion has been reorganized into reusable modules in `src/data/` with a
shared base class for common functionality.

### Teams (`src/data/teams.py`)

- **Status**: ✅ Complete
- **Records**: 134 FBS teams for 2024
- **Key fields**: school, conference, classification, mascot, colors, logos
- **Usage**: `python scripts/ingest_cli.py teams --year 2024`
- **Module**: `TeamsIngester`

### Venues (`src/data/venues.py`)

- **Status**: ✅ Complete
- **Records**: 150 venues used by FBS games in 2024
- **Key fields**: name, capacity, city, state, coordinates, surface type
- **Usage**: `python scripts/ingest_cli.py venues --year 2024`
- **Module**: `VenuesIngester`
- **Note**: Automatically filters to venues used by FBS games only

### Games (`src/data/games.py`)

- **Status**: ✅ Complete
- **Records**: 753 FBS regular season games for 2024
- **Key fields**: teams, scores, venue, date, ELO ratings, line scores
- **Usage**: `python scripts/ingest_cli.py games --year 2024`
- **Module**: `GamesIngester`
- **Dependencies**: Requires venues table to be populated first

### Plays (`src/data/plays.py`)

- **Status**: ✅ Complete (Rewritten)
- **Records**: Play-by-play data for FBS games
- **Key fields**: down/distance, yardage, play type, clock, teams
- **Usage**: `python scripts/ingest_cli.py plays --year 2024 --limit-games 5`
- **Module**: `PlaysIngester`
- **Dependencies**: Requires games table to be populated first

### Betting Lines (`src/data/betting_lines.py`)

- **Status**: ✅ Complete
- **Records**: Sportsbook betting lines for FBS games
- **Key fields**: spread, over/under, moneylines by provider
- **Usage**: `python scripts/ingest_cli.py betting_lines --year 2024 --limit-games 10`
- **Module**: `BettingLinesIngester`
- **Dependencies**: Requires games table to be populated first

### Rosters (`src/data/rosters.py`)

- **Status**: ✅ Complete
- **Records**: Player roster data for FBS teams
- **Key fields**: player info, position, physical stats, hometown
- **Usage**: `python scripts/ingest_cli.py rosters --year 2024 --limit-teams 3`
- **Module**: `RostersIngester`
- **Dependencies**: Requires teams table to be populated first

### Coaches (`src/data/coaches.py`)

- **Status**: ✅ Complete
- **Records**: Coaching staff data for FBS teams
- **Key fields**: coach info, hire date, season records
- **Usage**: `python scripts/ingest_cli.py coaches --year 2024 --limit-teams 3`
- **Module**: `CoachesIngester`
- **Dependencies**: Requires teams table to be populated first

### Game Stats (Raw) (`src/data/game_stats.py`)

- **Status**: 🟡 In Progress
- **Records**: Raw advanced box score JSON objects for each FBS game.
- **Purpose**: Used for validating the play-by-play aggregation pipeline against an official source.
- **Usage**: `uv run python scripts/ingest_cli.py game_stats_raw --year 2023`
- **Module**: `GameStatsIngester`
- **Dependencies**: Requires games table to be populated first

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
- Raw dataset is partitioned by `entity/year/week/game_id` for plays and `entity/year` for other
  entities. Processed aggregations (CSV) layout:
  - byplay: `processed/byplay/year/<YYYY>/week/<WW>/game/<GAME_ID>/`
  - drives: `processed/drives/year/<YYYY>/week/<WW>/game/<GAME_ID>/` (rows are per drive)
  - team_game: `processed/team_game/year/<YYYY>/week/<WW>/team/<TEAM>/`
  - team_season: `processed/team_season/year/<YYYY>/team/<TEAM>/side/<offense|defense>/`
  - team_season_adj: `processed/team_season_adj/year/<YYYY>/team/<TEAM>/side/<offense|defense>/`
- Each partition includes a `manifest.json` with row counts and metadata to enable validation
- Referential integrity between entities is validated using utilities in `src/utils/validation.py`
- Idempotent writes: partitions are atomically overwritten to avoid partial writes and duplicates

### Validation gates (ingestion)

- Schema checks: required columns present; dtypes are consistent with `docs/cfbd/schemas.md`
- Nulls/ranges: no nulls in key fields; basic range checks on week, period, scores, yard lines
- Referential integrity: `plays.gameId` present in `games`; team names/IDs resolve against `teams`
- Manifests: row counts recorded per partition; totals reconciled against expected per season/week

## Minimizing API Usage

We treat API calls as a constrained resource. The ingestion layer includes safeguards to avoid
redundant fetches and to scope pulls tightly:

- Week targeting for games/plays: pass `--week` to ingest a single week instead of the full season.
- Skip-if-present logic:
  - Plays: if raw partitions already exist for `plays/year=<YYYY>/week=<WW>/game_id=*` covering all
    FBS games in that week (based on the local games index), the week is skipped with a log message.
  - Game stats: if `game_stats_raw/year=<YYYY>/week=<WW>/game_id=*` is complete, the week is skipped.
  - Betting lines: if local storage already has lines for all FBS games in the year, the yearly API
    call is skipped entirely.

These checks ensure you can re-run ingestion safely without re-hitting the API when the local cache is
complete.

## CLI Flags

All ingestion commands support a common set of flags:

- `--data-root`: Base directory for the data (default: `./data/raw` for raw data, `./data/processed`
  for processed data)
- `--season_type`: Season type (`regular`, `postseason`) when applicable
- `--week`: Optional specific week to ingest (supported for `games` and `plays`)
- `--workers`: Parallel worker count for API calls
- `--exclude-seasons`: Comma-separated years to skip (optional; default: none)
- `ingest-year` diagnostics:
  - `--only` / `--skip` let you tailor which ingestion tasks run (e.g., `--only games --only plays`).
  - `--dry-run` prints the resolved ingestion plan without executing it—useful for verifying order before a long run.

### Examples

- Single week of games and plays (development-friendly):

```bash
python scripts/cli.py ingest games --year 2024 --season-type regular --week 5 --data-root "/path/to/root"
python scripts/cli.py ingest plays --year 2024 --season-type regular --week 5 --data-root "/path/to/root"
```

- Betting lines (will be skipped if already complete for the year):

```bash
python scripts/cli.py ingest betting_lines --year 2024 --season-type regular --data-root "/path/to/root"
```
