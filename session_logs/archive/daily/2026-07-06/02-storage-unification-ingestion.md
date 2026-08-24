# Session: 2026 Storage Unification + Ingestion Pipeline

## TL;DR
- **Worked On:** Full storage backend unification, rewired all ingesters for R2 cloud, ingested 2026 preseason data, built CLI ingestion scripts, backfilled 2025
- **Completed:** All 7 phases — storage layer unified, 2026 data in R2, CLI + Makefile targets operational, 2025 backfilled
- **Blockers:** None
- **Next:** Deploy to Vercel (add DATABASE_URL env var); retrain/validate models before 2026 season; start weekly pipeline Aug 29

## What Changed (45 files total)

### Phase 1-3: Storage Unification (~25 files)
- **`data/storage.py`** — added `StorageError` class; 3 new ABC methods (`list_partitions`, `partition_exists`, `describe`) + implementations in LocalStorage, R2Storage, S3Storage
- **`utils/base.py`** — converted to re-export shim from `data/storage.py` (Partition, StorageBackend, StorageError)
- **`utils/local_storage.py`** — converted to backward-compatible shim (extends `data/storage.py:LocalStorage`, preserves old constructor signature)
- **`data/base.py`** — auto-detects `CFB_STORAGE_BACKEND` env var; uses `get_storage()` for cloud, `data/storage.py:LocalStorage` for local
- **`data/games.py`** — entity_name → `"raw/games"`; `root()` call at :205 refactored to `read_index()`
- **`data/plays.py`** — entity_name → `"raw/plays"`; `root()` call at :96 refactored to `list_partitions()`; 2 bare `read_index("games")` → `"raw/games"`
- **`data/betting_lines.py`** — entity_name → `"raw/betting_lines"`; week-filter in read_index removed (games are year-level files)
- **`data/game_stats.py`** — entity_name → `"raw/game_stats"`; `root()` call at :79 refactored to `list_partitions()`
- **`data/teams.py`, `data/venues.py`, `data/coaches.py`, `data/rosters.py`, `data/rankings.py`, `data/recruiting.py`** — entity_name → `"raw/..."` prefix
- **`data/external_ratings.py`** — entity_name → `"raw/external_ratings"`; `_get_manual_dir` updated
- **`data/venues.py`** — game lookup entity name → `"raw/games"`
- **`features/persist.py`** — 4 `storage.root()` log messages → `storage.describe()`

### Phase 4: CLI Scripts + Makefile (3 new files)
- **`scripts/data/ingest_season.py`** — ingest all entities for a year from CFBD API → R2
- **`scripts/data/ingest_week.py`** — ingest plays + betting_lines for a specific week
- **`Makefile`** — `make ingest-season`, `make ingest-week`, `make weekly` targets added

### Phase 5: 2026 Preseason Data in R2
- **`raw/games/year=2026/`** — 888 FBS games (weeks 1-16), ingested from CFBD API
- **`raw/teams/year=2026/`** — 138 FBS teams
- **`raw/venues/year=2026/`** — 150 venues used by FBS games

### Phase 6: 2025 Backfill
- **`raw/plays/year=2025/week=16/`** — 140 plays (Army vs Navy, bowl games)
- **`raw/betting_lines/year=2025/week=15/`** — 36 lines
- **`raw/betting_lines/year=2025/week=16/`** — 4 lines

### Phase 7: Docs
- **`.codex/QUICKSTART.md`** — updated ingestion + weekly pipeline sections
- **`AGENTS.md`, `README.md`, `Makefile`** — earlier session updates confirmed correct
- **`tests/conftest.py`** — sets `CFB_STORAGE_BACKEND=local` as test default
- **`tests/test_external_ratings.py`** — entity_name assertion updated

## Testing
- [x] Python: 187 tests pass
- [x] Ruff: clean on all touched files (11 pre-existing errors in test_mlp.py)
- [x] Web: lint + typecheck + build all clean
- [x] Live ingestion verified: 2026 games/teams/venues in R2; 2025 backfill complete

## Key Architecture Decisions

1. **Single canonical ABC:** `data/storage.py:StorageBackend` — `utils/base.py:StorageBackend` is now a re-export shim
2. **Entity name convention:** All entity names include tier prefix (`"raw/games"`, `"raw/plays"`). LocalStorage no longer prepends `data_type` to root — entity name IS the full path.
3. **Cloud auto-detection:** `BaseIngester.__init__` reads `CFB_STORAGE_BACKEND` env var; `'r2'` → `get_storage()` returns R2Storage
4. **Data layout compatibility:** Existing R2 data at `raw/games/year=YYYY/` matches new entity_name `"raw/games"` → no migration needed
5. **Partition discovery:** New `list_partitions()`, `partition_exists()`, `describe()` methods replace all `storage.root() / ...` path operations

## 2026 Weekly Workflow (ready to use)

```bash
# Preseason (done):
make ingest-season YEAR=2026

# Each week starting Aug 29:
make weekly YEAR=2026 WEEK=1    # ingest → preagg → predict → publish to Neon

# Or step by step:
make ingest-week YEAR=2026 WEEK=1   # CFBD → R2
PYTHONPATH=.:src uv run python scripts/pipeline/run_pipeline_generic.py --year 2026  # raw → processed
PYTHONPATH=.:src uv run python scripts/pipeline/generate_weekly_bets.py --year 2026 --week 1  # model → CSV
make db-publish YEAR=2026 WEEK=1    # CSV → Neon → Vercel
```

## Notes for Next Session

- **Model retrain decision:** Current `linear_spread_target.joblib` / `linear_total_target.joblib` were trained on 2019-2023 with 2024 holdout. Now that 2025 is complete (weeks 1-16 + bowls backfilled), retraining on 2019-2025 is possible. Model is at break-even anyway.
- **Vercel deploy:** Set `DATABASE_URL` env var in Vercel project settings, Root Directory → `web/`. Already tested locally with real data.
- **2026 betting lines:** Won't appear in CFBD API until sportsbooks post them (1-2 weeks before kickoff). The pipeline handles missing lines gracefully (nullable columns).
- **Pre-aggregation testing:** Not yet tested with 2026 data since there are no plays (season hasn't started). Will work once week 1 plays are ingested.

**tags:** ["storage", "refactor", "r2", "cloud", "ingestion", "backfill", "2026-season", "cli"]
