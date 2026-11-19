# Data-First Research Commands

New executable commands for the data-first football forecasting program live
in this directory.

- Put reusable measurements, ratings, forecasting, and evaluation logic in
  `src/cks_picks_cfb/`.
- Put executable research orchestration in `scripts/research/`.
- Keep supported production workflows in `scripts/pipeline/`.

Production modules and commands must not import from `scripts/research/`.
Research commands may call reusable library code through explicit
interfaces, but they cannot publish, freeze, close, migrate, deploy, or otherwise
activate production state.

Existing rating and successor scripts remain at their current paths as named
benchmark compatibility entry points. New program commands must use the
`artifacts/research/data-first-football-v1/` artifact namespace and the
`conf/research/data_first_football_v1/` configuration root.

## 2026 weather pilot

Capture a slate with `python scripts/research/capture_weather_pilot.py capture
--week 13 --output <new-evidence-directory>`. The script uses `CFBD_API_KEY`
from the environment or dotenv. An isolated worktree can point
`CFB_WEATHER_ENV_FILE` at the existing project dotenv. The output directory
holds a receipt and raw NWS response bodies.

Once the initial weekly revision is available, run
`python scripts/research/capture_weather_pilot.py report <receipt.json> <revision.json>`
to classify forecast coverage at its certified cutoff. See the
[model preparation contract](../../docs/plans/2026-11-19/model-head-start.md)
for the two capture dates and the archive check.
