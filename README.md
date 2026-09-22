# CKsPicks-CFB

College-football spread and total prediction system: Python pipeline, immutable
Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## Research checkpoint (2026-09-22)

**V4 remains the live production champion.** The **V5 ratings successor** is
isolated Preview research and is distinct from **feature schema v5**, the separate
V4 diagnostic. Its historical development and verification lane is complete and
accepted: all four historical audit findings are closed. Contract 07 is
Implemented with 157 certified live 2026 games through Week 3. Contract 08 is
the immediate research task, followed by the Week 4 refresh, Contract 09 live
readiness, Contract 06's six-slate prospective evaluation, and a conditional
Phase 7 promotion review. The
[data-first roadmap](docs/planning/data-first-football-forecasting-roadmap.md)
is the detailed status and execution authority.

Repair v2 and Phase 3 v2 remain certified historical evidence; R6 is a
superseded historical measurement lineage. The original Phase 4B retained
manifest remains prohibited as a forecasting parent. New research uses
2015–2019 and 2021–2025 as development evidence, excludes 2020, and never uses
2026 outcomes to choose or tune V5. Production operations remain under their
existing runbooks.

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
