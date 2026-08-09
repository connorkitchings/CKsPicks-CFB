# CollegeFootballData.com (CFBD) Quickstart

This repository uses the official CFBD REST API as a raw-data provider. The
current contract audit is the source of truth for provider behavior, access,
and compatibility: [2026 Provider Audit](2026_provider_audit.md).

## Current baseline

- **REST base and interactive documentation:** <https://api.collegefootballdata.com>
- **Installed Python client:** `cfbd` 5.16.0
- **Live REST catalog observed on 2026-08-04:** 5.17.0
- **Configured account:** Patreon Tier 2 (30,000 monthly calls)
- **Storage path:** R2 is the production source of truth; Neon serves the web
  app. Do not create a project-local `data/` tree for production ingestion.

`apinext.collegefootballdata.com` and the local-CSV workflow shown in older
project material are not operational references for this repository.

## Authentication

Set the key only in the local `.env` file:

```dotenv
CFBD_API_KEY=...
CFB_STORAGE_BACKEND=r2
CFB_R2_BUCKET=...
CFB_R2_ACCOUNT_ID=...
CFB_R2_ACCESS_KEY=...
CFB_R2_SECRET_KEY=...
```

The client authenticates with a bearer token:

```python
import os

import cfbd

client = cfbd.ApiClient(
    cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"])
)
games = cfbd.GamesApi(client).get_games(
    year=2026, week=1, season_type="regular", classification="fbs"
)
```

Never print, commit, or send the API key to a client application.

## Operational commands

All write commands use the configured R2 backend. Run a preflight before a
weekly operation:

```bash
make preflight YEAR=2026 WEEK=1
```

Refresh only the raw entity that is needed:

```bash
# Season-level data. Order matters when an entity has a dependency.
PYTHONPATH=.:src uv run python scripts/data/ingest_season.py \
  --year 2026 --entities teams,games,venues,coaches,recruiting

# Week-level market data.
PYTHONPATH=.:src uv run python scripts/data/ingest_week.py \
  --year 2026 --week 1 --entities betting_lines
```

`make publish-week` is intentionally broader: it refreshes schedule and
lines, generates a prediction artifact, and writes to Neon. Do not use it for
a raw-data-only refresh. It also now fails before publication when any
scheduled FBS game lacks a sportsbook line.

## Access and availability

Tier 2 supports REST, historical data, advanced metrics, weather, the live
scoreboard, and live play-by-play. GraphQL queries and subscriptions require
Tier 3 or above and are not part of this deployment. The provider can return a
valid empty collection before a seasonal feed is published; treat that as an
availability state rather than a successful data refresh.

On 2026-08-08, CFBD had the full 2026 schedule, Week 1 line envelopes, rosters
(15,171 FBS players), and returning production (136 teams). Rosters and the
preseason Coaches Poll were ingested to R2 on that date. Talent remains empty
and still gates the immutable preseason snapshot. See the audit for the current
availability matrix and the explicit line-coverage caveat.

## References

- [2026 Provider Audit](2026_provider_audit.md)
- [Weekly operating runbook](../ops/weekly_pipeline.md)
- [Canonical ingestion guide](../data/ingestion_guide.md)
- [REST API documentation](https://api.collegefootballdata.com/)
- [CFBD API tiers](https://collegefootballdata.com/api-tiers)
