# CKsPicks-CFB

College-football spread and total prediction system: Python pipeline, immutable
Cloudflare R2 data lake, Neon serving state, and a Vercel web app.

## 2026 posture

The live production champion is the V4 ten-route model bundle
`week0-2026-v4-strict-20260818-r2`. It remains the stable, fail-closed
production and rollback system for the 2026 season.

The approved successor is a rating-centric hybrid architecture:

```text
football measurements → measurement-level opponent adjustment
→ offense/defense/overall team state + uncertainty
→ structured game prediction → optional ML residual → probabilistic output
→ timestamped market decision
```

The successor research track now expands historical football evidence through
2015–2019 and 2021–2025 (2020 is excluded) before freezing candidate v2. V4
remains isolated from research, Neon activation, and public publication. Frozen
candidate v1 may collect diagnostic evidence only; candidate v2 needs its own
six-slate prospective lane and promotion contract.

## Documentation

- [Documentation home](docs/index.md)
- [2026 roadmap](docs/planning/roadmap.md)
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
