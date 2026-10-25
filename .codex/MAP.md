# Project File Map

Use [current status](../docs/status.md) for live release/week state and the [weekly runbook](../docs/ops/weekly_runbook.md) for operations. V5 is the only operational model; [V4](../docs/modeling/v4_retrospective.md) is historical evidence.

## Entrypoints and tooling

| Path | Purpose |
|---|---|
| `AGENTS.md`, `CLAUDE.md` | Assistant instructions and pointer to them |
| `.agent/CONTEXT.md`, `.agent/skills/CATALOG.md` | Architecture and session workflows |
| `.codex/QUICKSTART.md` | Current command interfaces and guardrails |
| `Makefile`, `pyproject.toml`, `uv.lock` | Pipeline tasks (`make help`, `make check`), Python dependencies and lock |
| `web/package.json` | Isolated Next.js npm toolchain |
| `mkdocs.yml` | Documentation navigation |

## Live season path

| Path | Purpose |
|---|---|
| `scripts/pipeline/build_season_revision.py` | Controller ingestion/Silver refresh, cumulative registered market quotes, pinned revision manifest |
| `scripts/pipeline/run_season.py` | Prepare, status, release and rollback CLI |
| `src/cks_picks_cfb/season/` | Input validation, chronological runner, grading, verification, projections and atomic release |
| `conf/season/2026/` | Sealed model manifest, revision manifests, score reconciliation exceptions |
| `scripts/ops/with_preview_env.sh` | Preview credentials and artifact environment |
| `scripts/ops/with_production_pipeline_env.sh` | Production pipeline credentials |
| `scripts/ops/with_production_owner_env.sh` | Production owner/migrator rollback credentials |
| `artifacts/season/2026/preview/` | Ignored local candidate outputs; not the durable lake |

Use `make season-revision`, `season-prepare`, `season-release` and `season-rollback` as specified in the runbook. Legacy publish/freeze/close Make targets refuse execution.

## Football data and research

| Path | Purpose |
|---|---|
| `src/cks_picks_cfb/data/` | Provider adapters, immutable storage/lake/catalog, Silver, reconciliation, timing |
| `src/cks_picks_cfb/features/` | Measurements, by-play enrichment, point-in-time assembly and opponent adjustment |
| `src/cks_picks_cfb/ratings/`, `forecast/` | V5 rating/forecast implementation and retained research |
| `src/cks_picks_cfb/ratings_lab/`, `audit/` | Isolated research and audit libraries |
| `scripts/data/` | Source ingestion/capture CLIs; use the intended environment wrapper |
| `scripts/research/`, `scripts/analysis/`, `conf/research/` | Research/analysis commands and configurations |
| `conf/repository/compatibility_v1.yaml` | Machine-readable ownership and compatibility manifest |

V4 code was removed on 2026-10-22; see the [V4 retrospective](../docs/modeling/v4_retrospective.md). Research code stays.

## Shared contracts and web

| Path | Purpose |
|---|---|
| `contracts/schema.sql`, `schema.ts` | Canonical schema snapshot and Drizzle contract |
| `contracts/migrations/` | Append-only upgrades through `0028_team_resume.sql` |
| `contracts/teams.py`, `teams.ts`, `validation.py` | Shared team mappings and sync validation |
| `src/cks_picks_cfb/db/migrations.py`, `scripts/pipeline/migrate_db.py` | Verified-target migration mechanism |
| `web/src/lib/schema.ts`, `teams.ts` | Synchronized contract copies |
| `web/src/lib/season-release-context.ts`, `season-release-query.ts` | Active season release resolution and projections |
| `web/src/lib/publication.ts`, `queries.ts` | Publication policy and legacy read fallback |
| `web/src/app/`, `components/` | Routes: Games `(games)`, `ratings`, `stats`, `model`, `matchup/[gameId]`, `teams/[team]`; health at `api/health/route.ts` |
| `web/README.md`, `web/playwright.config.ts` | Local development, flags and fixture UI verification |

## Documentation and checks

| Path | Purpose |
|---|---|
| `docs/index.md`, `docs/status.md`, `docs/status_history.md` | Authority map, live state and dated history |
| `docs/ops/weekly_runbook.md` | Sole recurring operational guide |
| `docs/ops/data_first_capture.md` | Isolated research capture workflow |
| `docs/data/validation.md`, `docs/architecture/` | Data checks and architecture |
| `docs/modeling/v5_status.md`, `record_methodology.md`, `v4_retrospective.md` | Accepted model, public record policy and historical V4 |
| `docs/planning/`, `docs/plans/index.md`, `docs/decisions/` | Strategy, implementation contracts and decisions |
| `docs/archive/`, `docs/archive.md` | Superseded runbooks, V4-era process, experiments, reports and research; indexed in `docs/archive.md` |
| `tests/`, `web/src/**/*.test.ts` | Python and web behavioral tests |
| `session_logs/` | Dated execution evidence |

Run `make test`, `make contracts-check`, `make quality-check` and affected web scripts; see quickstart for strict docs and non-mutating lint checks. Database tests require disposable PostgreSQL. Durable football data lives in R2 or the external `CFB_MODEL_DATA_ROOT`, never repository-local `./data/`.
