# Session: Historical Data Backfill - Betting Lines, Teams, Coaches, Rosters, Returning Production, Venues, Recruiting, Rankings (2015–2025, Skipping 2020)

## TL;DR
- **Worked On:** Ingested complete historical college football data from CFBD across 10 seasons (2025 down to 2015, skipping 2020 per repository guardrails): betting lines, FBS games, FBS teams, head coaches, team rosters, returning production, venues, 247Sports composite recruiting rankings (including 2012–2014 for rolling 4-year averages), and weekly AP/Coaches poll rankings.
- **Outcome:** Successfully captured, cataloged, and partitioned into Cloudflare R2 and Neon catalog:
  - 25,146 betting lines
  - 8,468 FBS regular season games
  - 1,310 FBS team-seasons
  - 1,432 head coaches
  - 152,965 FBS player roster entries
  - 1,304 returning production records (PPA and usage metrics)
  - 1,476 FBS venue entries across all 10 seasons (2015–2019, 2021–2025)
  - 2,752 team recruiting rankings across 13 seasons (2012–2019, 2021–2025)
  - 17,416 weekly AP & Coaches Poll rankings across all 10 seasons (2015–2019, 2021–2025)
  - Added `ReturningProductionIngester` in `src/cks_picks_cfb/data/returning_production.py` and unit test in `tests/test_ingestion_hardening.py`.
- **Plan Contract:** N/A (data ingestion task)
- **Approval / Status:** User authorized full-season backwards collection from 2025 to 2015 using current lake/catalog architecture.
- **Blockers:** None.
- **Next:** Preseason feature generation or Silver normalizations if desired.

## Context and Decisions
- Active storage backend is Cloudflare R2 (`CFB_STORAGE_BACKEND='r2'`) with Neon Postgres catalog.
- Prior state had only 2026 data for betting lines, coaches, rosters, returning production, venues, and recruiting in active R2 and Neon catalog.
- 2020 is strictly excluded per COVID season protocol.
- Executed `TeamsIngester` -> `CoachesIngester` -> `RostersIngester` -> `ReturningProductionIngester`, `GamesIngester` -> `BettingLinesIngester`, `VenuesIngester` (filtered to FBS games index), `RecruitingIngester` (covering 2012–2019 and 2021–2025 for 4-year rolling baselines), and `RankingsIngester` (covering all weeks of 2015–2019, 2021–2025).
- Dual-write preserved immutable Bronze captures with SHA-256 and registered each in `catalog.source_captures` under `provider='cfbd'`.
- Verified that atomic play-by-play data already exists in the `cfb-model-data` source bucket for 2019, 2021–2025 (and 2015/2026 in preview), along with pre-computed `processed/` drive and team-game aggregations.
- Clarified that traditional `game_stats` (box scores) are redundant because all team and drive metrics are aggregated directly from play-by-play data.

## Work Completed

### Summary by Season
| Season | Teams | Coaches | Rosters | Ret. Prod. | Venues | Recruiting | Rankings (Polls) | FBS Games | Betting Lines |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2025** | 136 | 161 | 15,599 | 134 | 148 | 232 | 2,052 | 888 | 2,299 |
| **2024** | 134 | 152 | 16,221 | 133 | 151 | 194 | 2,028 | 874 | 1,678 |
| **2023** | 133 | 143 | 15,918 | 131 | 150 | 177 | 1,902 | 868 | 2,446 |
| **2022** | 131 | 146 | 15,548 | 130 | 144 | 184 | 1,950 | 854 | 3,184 |
| **2021** | 130 | 152 | 15,129 | 128 | 148 | 191 | 1,400 | 849 | 2,869 |
| **2020** | — | — | — | — | — | — | — | — | — |
| **2019** | 130 | 134 | 15,558 | 130 | 144 | 223 | 1,704 | 848 | 3,071 |
| **2018** | 130 | 139 | 14,511 | 130 | 148 | 229 | 1,600 | 845 | 2,887 |
| **2017** | 130 | 139 | 14,757 | 128 | 144 | 233 | 1,600 | 834 | 2,289 |
| **2016** | 128 | 134 | 14,714 | 128 | 148 | 238 | 1,603 | 832 | 2,225 |
| **2015** | 128 | 132 | 15,010 | 128 | 151 | 231 | 1,577 | 829 | 2,198 |
| **2014** | — | — | — | — | — | 231 | — | — | — |
| **2013** | — | — | — | — | — | 210 | — | — | — |
| **2012** | — | — | — | — | — | 183 | — | — | — |
| **TOTAL** | **1,310** | **1,432** | **152,965** | **1,304** | **1,476** | **2,752** | **17,416** | **8,468** | **25,146** |


## Files Modified
- `src/cks_picks_cfb/data/returning_production.py` - canonical ReturningProductionIngester
- `src/cks_picks_cfb/data/__init__.py` - export ReturningProductionIngester
- `scripts/data/ingest_season.py` - add returning_production entity
- `tests/test_ingestion_hardening.py` - unit test for ReturningProductionIngester
- `session_logs/2026-09-06/08-historical-betting-lines-collection.md` - this session log

## Validation
- [x] Verified `catalog.source_captures` entries for all seasons across all entities with state `registered`.
- [x] Verified R2 `raw/teams/year={YYYY}/part-0.parquet` partitions.
- [x] Verified R2 `raw/coaches/year={YYYY}/part-0.parquet` partitions.
- [x] Verified R2 `raw/rosters/year={YYYY}/part-0.parquet` partitions.
- [x] Verified R2 `raw/returning_production/year={YYYY}/part-0.parquet` partitions.
- [x] Verified R2 `raw/venues/year={YYYY}/part-0.parquet` partitions (11 partitions: 2015–2019, 2021–2026).
- [x] Verified R2 `raw/recruiting/year={YYYY}/part-0.parquet` partitions (14 partitions: 2012–2019, 2021–2026).
- [x] Verified R2 `raw/games/year={YYYY}/part-0.parquet` partitions.
- [x] Verified R2 `raw/betting_lines/year={YYYY}/week={W}/part-0.parquet` partitions.
- [x] `PYTHONPATH=. uv run pytest tests/test_ingestion_hardening.py -q` passed (10/10).
- [x] `uv run ruff check` passed cleanly.

**tags:** ["data-ingestion", "betting-lines", "teams", "coaches", "rosters", "returning-production", "venues", "recruiting", "cfbd", "lake-bronze", "catalog"]
