# Data Ingestion Guide

This is the canonical guide for raw CFBD ingestion in the 2026 R2-backed
workflow. Provider capability and compatibility findings live in the
[2026 CFBD Provider Audit](../cfbd/2026_provider_audit.md).

## Storage and safety

Production raw data, processed features, and durable artifacts belong in the
configured cloud backend:

```dotenv
CFB_STORAGE_BACKEND=r2
CFB_R2_BUCKET=...
CFB_R2_ACCOUNT_ID=...
CFB_R2_ACCESS_KEY=...
CFB_R2_SECRET_KEY=...
CFBD_API_KEY=...
```

R2 is the durable source of truth. Neon is a derived serving store for the web
app. Never create `./data/` as a substitute production data root; local storage
is development-only and requires `CFB_MODEL_DATA_ROOT` to point to an existing
external path.

## Ingestion modules and dependencies

| CFBD entity | Module | R2 entity | Required prior data | Primary consumer |
| --- | --- | --- | --- | --- |
| Teams | `data/teams.py` | `raw/teams` | none | games, rosters, coaches, features |
| Games | `data/games.py` | `raw/games` | none | weekly schedule, scoring, features |
| Venues | `data/venues.py` | `raw/venues` | games | feature persistence |
| Betting lines | `data/betting_lines.py` | `raw/betting_lines` | games | weekly prediction/publish path |
| Plays | `data/plays.py` | `raw/plays` | games | feature persistence and aggregation |
| Game stats | `data/game_stats.py` | `raw/game_stats` | games | raw-stat validation |
| Rosters | `data/rosters.py` | `raw/rosters` | teams | future/preseason research |
| Coaches | `data/coaches.py` | `raw/coaches` | teams | preseason research |
| Recruiting | `data/recruiting.py` | `raw/recruiting` | none | external features |
| Rankings | `data/rankings.py` | `raw/rankings` | none | external features |

Season partitions are overwritten by a successful refresh. Plays, game stats,
and lines are partitioned by season and week. The pipeline deliberately does
not infer that an empty provider response is complete data.

## Commands

Start with a read-only environment check:

```bash
make preflight YEAR=2026 WEEK=1
```

For a season refresh, order entities to satisfy their dependencies:

```bash
PYTHONPATH=.:src uv run python scripts/data/ingest_season.py \
  --year 2026 --entities teams,games,venues,coaches,recruiting
```

For the active slate, target only the required week:

```bash
PYTHONPATH=.:src uv run python scripts/data/ingest_week.py \
  --year 2026 --week 1 --entities betting_lines
```

After completed games are published by CFBD, refresh games, plays, lines, and
game stats for the week before running the feature and scoring path. See the
[weekly runbook](../ops/weekly_pipeline.md) for the mutation sequence.

## Availability and validation

Before a refresh, verify that the source is seasonally available. After a
refresh, validate the affected R2 partition rather than trusting a zero-row
write. In particular:

- schedule envelopes can exist before a sportsbook supplies a usable line;
- roster, talent, returning-production, and ranking feeds may legitimately be
  empty in preseason;
- postgame plays and game stats should be refreshed only after final scores are
  available;
- pregame modeling must use point-in-time inputs and must not consume
  postgame-only metrics or later-season data.

The [2026 CFBD Provider Audit](../cfbd/2026_provider_audit.md) records current
source status, contract-probe results, and the roadmap for improving
availability handling.
