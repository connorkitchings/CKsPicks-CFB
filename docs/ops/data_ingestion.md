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
- Season split policy (Train: 2019, 2021-2023; Test: 2024; Deploy: 2025) is fixed unless explicitly overridden.
