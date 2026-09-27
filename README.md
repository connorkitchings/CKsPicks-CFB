# CKsPicks-CFB

College-football spread and total prediction system: Python pipeline, immutable
Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## V5 checkpoint (2026-09-27)

[V5 model development is complete and accepted](docs/modeling/v5_status.md). The public site serves V5 best-quote replay for Weeks 0–4 and the authorized Week 5 live run `2026w5-d6366e59fd43` (56 predicted games, 34 with lines at release). Week 4 is scored. V4 frozen runs remain selectable for rollback. V5 ratings successor is distinct from the V4 feature schema v5 diagnostic.

Six slates are not a launch prerequisite; prospective paired-slate results continue as monitoring.

## 2026 posture

V5 is the selected public model family for 2026 Weeks 0–5. The V4
ten-route bundle `week0-2026-v4-strict-20260818-r2` and its frozen runs remain
the tested rollback path. Follow the [weekly pipeline](docs/ops/weekly_pipeline.md)
and the [V5 operator](docs/ops/v5_weekly_operator.md) for current commands.

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
