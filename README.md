# CKsPicks-CFB

College-football spread and total prediction system: Python pipeline, immutable
Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Research checkpoint (2026-09-13)

**V4 remains the live production champion.** The **V5 ratings successor** is
isolated research, distinct from **feature schema v5**, the separate V4 diagnostic.
Repair v2 is verified and Phase 3 v2 is certified (2026-09-11). The possession
methodology is specified and amended; possession measurements remain uncertified.
The next ratings task is **02: possession measurement certification**; contract 01
is the independent diagnostic closure. The [data-first roadmap](docs/planning/data-first-football-forecasting-roadmap.md)
is the canonical status and execution-queue authority.

The original Phase 4B retained manifest remains prohibited as a forecasting
parent. Earlier candidate results keep their historical audit limits. New research
uses 2015–2019 and 2021–2025 as development evidence, excludes 2020, and requires
future pre-kickoff freezes for independent evidence. Production operations remain
under their existing runbooks.

## 2026 posture

The live production champion is the V4 ten-route model bundle
`week0-2026-v4-strict-20260818-r2`. It remains the stable, fail-closed
production and rollback system for the 2026 season.

New research follows the approved data-first football forecasting architecture:

```text
audited football data → validated measurements → opponent adjustment
→ offense/defense team state + uncertainty → spread/total forecast
→ prospective evaluation → timestamped line comparison
```

The program uses 2015–2019 and 2021–2025 as development evidence and excludes
2020. It starts by preserving and clarifying repository architecture, auditing
and repairing data, then testing measurements, preseason priors, team ratings
and rating-based forecasts. Research cannot alter V4 bundles, Neon activation,
or public publication. Future frozen forecasts provide independent evidence. Market lines
are comparison evidence only; betting decisions are deferred.

## Documentation

- [Documentation home](docs/index.md)
- [2026 roadmap](docs/planning/roadmap.md)
- [Data-first football forecasting roadmap](docs/planning/data-first-football-forecasting-roadmap.md)
- [Rating-system requirements](docs/modeling/rating_system_requirements.md)
- [Measurement catalog](docs/modeling/measurement_catalog.md)
- [V4 regime contract](docs/modeling/early_season_regimes.md)
- [Evaluation policy](docs/modeling/evaluation.md)
- [Weekly pipeline](docs/ops/weekly_pipeline.md)
- [Production runbook](docs/ops/production_runbook.md)
- [AI assistant guide](AGENTS.md)

## Local setup

```bash
uv sync --extra dev
uv run pytest -q
uv run mkdocs build --strict
```

Production data uses `CFB_STORAGE_BACKEND=r2` and immutable R2 lineage. The
local backend requires `CFB_STORAGE_BACKEND=local` and an external
`CFB_MODEL_DATA_ROOT`; never create or use repository-local `./data/`.

The web app is isolated in `web/`; see [its README](web/README.md) for local
development and publication boundaries.
