# Data Ingestion Workflow (Locked)

Authoritative runbook for pulling past-week results and upcoming-week inputs. All commands **must** read/write to `CFB_MODEL_DATA_ROOT` (external drive); fail if the env var is missing or the drive is unmounted.

## One-shot: Completed Week (plays + finals + closing lines)

Use a single chained command to ingest everything needed for scoring a finished week:

```bash
uv run python scripts/cli.py ingest games --year 2025 --week 14 --season-type regular \
  && uv run python scripts/cli.py ingest plays --year 2025 --week 14 --season-type regular \
  && uv run python scripts/cli.py ingest betting_lines --year 2025 --week 14 --season-type regular
```

- Includes plays, final game results, and closing lines for scoring.
- Adds data under `$CFB_MODEL_DATA_ROOT/raw/*/year=YYYY/`.
- Extend with `--limit-games`/`--limit-teams` only for local debugging.

## One-shot: Upcoming Week (schedule + opening lines + weather forecast)

Use a single chained command to grab everything needed before predictions:

```bash
uv run python scripts/cli.py ingest games --year 2025 --week 15 --season-type regular \
  && uv run python scripts/cli.py ingest betting_lines --year 2025 --week 15 --season-type regular \
  && uv run python scripts/pipeline/ingest_weather.py --years 2025 --data-root "$CFB_MODEL_DATA_ROOT"
```

- Games covers schedule/metadata; betting_lines pulls current market lines.
- Weather script ingests per-game hourly weather aligned to game start (uses Open-Meteo UTC). For true future forecasts, keep start dates current; if a game is far out, rerun closer to kickoff. Use `--weeks 15` to limit weather pulls to the upcoming slate instead of the full season.

## Safety Guards

- Always export `CFB_MODEL_DATA_ROOT` and ensure the drive is mounted before running.
- Do **not** write to `./data/` in project root.
- Season policy is versioned in `conf/training/week0_2026.yaml`: 2022–2024 temporal selection, locked 2025 testing, and a 2021–2025 production refit. 2019 is prior-only for early 2021; 2020 is excluded.
- Production ingestion uses request-level `CFBDSourceAdapter` captures. Each
  request is validated and written to immutable Bronze storage before any
  compatibility projection can change.
- Week `0` is valid; a missing week is a contract failure. Partial multiweek
  responses and serialization failures return nonzero.
- Build Silver, reconciliation, and Gold data only from explicit capture or
  dataset references. See
  `docs/architecture/cfbd_point_in_time_pipeline.md` for the current flow.
- Historical production R2 is configured only through read-only
  `CFB_R2_SOURCE_*` credentials. Run `make inventory-source` before
  `make import-history`.
- `make import-history` is preview-only and resumes per source object and dataset
  step. It rejects 2020, restricts 2019 to prior inputs, and stops when legacy
  market rows lack authentic quote capture timestamps.
