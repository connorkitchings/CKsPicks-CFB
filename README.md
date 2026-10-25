# Crest CFB

College-football spread and total forecasts from a Python V5 season engine, an immutable Cloudflare R2 lake, Neon Postgres and a Vercel web app.

## Current status and operations

See [`docs/status.md`](docs/status.md) for the active release, week state and published scoreboard. [V5 model development is complete and accepted](docs/modeling/v5_status.md). The 2026 record is one continuous point-in-time V5 record from Week 0 ([record methodology](docs/modeling/record_methodology.md)); six slates are not a prelaunch requirement. V4 is historical evidence, documented in the [V4 retrospective](docs/modeling/v4_retrospective.md), and is no longer an operational model.

The [weekly runbook](docs/ops/weekly_runbook.md) is the sole operational authority. `build_season_revision.py` produces pinned inputs; `run_season.py prepare` recomputes and verifies the season; `run_season.py release` stages and atomically activates its serving projections. Preview rehearsal is mandatory before Production activation. Rollback reactivates a prior verified V5 season release through the owner credential. Legacy publish/freeze/close commands refuse execution.

Revision manifests and score exceptions must be committed before preparing from a clean tree. Do not commit between prepare and the last release: release requires the exact prepared commit. Production activation and all git commits remain owner-controlled.

## Modeling and research

```text
verified football data → validated measurements → opponent adjustment
→ continuous team ratings/state → spread/total forecast
→ point-in-time evaluation → timestamped line comparison
```

V5 Blitzkrieg is the only operational model. Research uses 2015–2019 and 2021–2025 as development evidence and excludes 2020. Market lines enter only after football forecasting. Research remains isolated from serving and publication until separately promoted; betting decisions are deferred. Started and reconstructed games remain visible on the Games tab because forecasts use pre-cutoff observations; grades use the best eligible pre-kickoff quote under the record methodology.

## Documentation

- [Documentation home](docs/index.md)
- [Weekly runbook](docs/ops/weekly_runbook.md)
- [V5 status guide](docs/modeling/v5_status.md)
- [Rating requirements](docs/modeling/rating_system_requirements.md) and [measurement catalog](docs/modeling/measurement_catalog.md)
- [Research roadmap](docs/planning/data-first-football-forecasting-roadmap.md)
- [Implementation contracts](docs/plans/index.md) and the [documentation archive](docs/archive.md)
- [AI assistant guide](AGENTS.md)

## Local setup and checks

```bash
uv sync
npm --prefix web install
make help     # every available target
make check    # mirrors CI: ruff, contracts, quality registry, pytest, mkdocs --strict, web lint/typecheck/tests/build
```

The web app has four tabs: Games, Ratings, Graphs and Model. See [web development](web/README.md).

Use `CFB_STORAGE_BACKEND=r2` with the intended environment wrapper for lake operations. The local backend requires `CFB_STORAGE_BACKEND=local` and an accessible external `CFB_MODEL_DATA_ROOT`; never create repository-local `./data/`. Credentials come from the Keychain wrappers and must not appear in logs. See [web development](web/README.md) and the [quickstart](.codex/QUICKSTART.md).

## CI

CI runs Ruff, contracts, the data-quality registry check, strict MkDocs, Python tests with a 60% coverage gate (including rating-publication and database suites) and the web checks. Database tests use disposable PostgreSQL instances; never point `TEST_DATABASE_URL` at a serving database. V4 is documented only in the [retrospective](docs/modeling/v4_retrospective.md).
