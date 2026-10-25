# AGENTS.md

Entry point for AI coding assistants working on CKsPicks-CFB (Claude Code, Copilot, Cursor and others). `CLAUDE.md` only points here.

## Read order

1. This file.
2. [`docs/status.md`](docs/status.md): live release IDs, week state and scoreboard. Never copy run IDs elsewhere.
3. [`.codex/QUICKSTART.md`](.codex/QUICKSTART.md): commands. [`.agent/CONTEXT.md`](.agent/CONTEXT.md): architecture. [`.codex/MAP.md`](.codex/MAP.md): file map.
4. The last three logs in `session_logs/`, then code on demand.

Do not read automatically: `artifacts/**`, `.venv/**`, `scripts/research/**` (unless working there), files over 200 KB, or `session_logs/` older than three days.

## Critical rules

### Data root

The durable store is the Cloudflare R2 immutable lake (`CFB_STORAGE_BACKEND=r2`). The local backend (`CFB_STORAGE_BACKEND=local`) reads and writes the external drive named by `CFB_MODEL_DATA_ROOT`. Before any data operation confirm the backend matches the task, the matching credentials (`CFB_R2_*` or `CFB_R2_PREVIEW_*`) or mounted drive are present, and never print secrets. Load paths from the environment and fail loudly when unset; never create or read `./data/` in the repository root and never hardcode `/Users/...` or `/Volumes/...` paths.

### Modeling guardrails

- V5 Blitzkrieg is the only operational model; live release IDs and week state are in `docs/status.md`. V4 is [historical evidence](docs/modeling/v4_retrospective.md), not a rollback path. Rollback reactivates a prior verified V5 season release. The accepted model, lineage and limits are in the [V5 status guide](docs/modeling/v5_status.md).
- Training strictly precedes prediction; no target-aware transforms on the full dataset; use `load_point_in_time_data()` for feature work. Development years are 2015-2019 and 2021-2025; skip 2020 in every boundary.
- Markets never enter football measurements, ratings or model selection; they join after forecasting for line comparison and grading. Do not bookmaker-derive features.
- Opponent adjustment happens once, at the measurement layer; do not double-count schedule strength or rating variance. Polls and direct-core models are diagnostic-only; the original Phase 4B retained manifest is prohibited as a forecasting parent.
- V5 model development is complete and accepted. The public 2026 record is one continuous point-in-time record from Week 0 ([record methodology](docs/modeling/record_methodology.md)); six slates are not a prelaunch gate. "Prospective" names freeze provenance only.
- Production activation needs an owner decision and a verified Preview rehearsal. Further research stays isolated from production bundles, Neon activation and publication until a separate promotion contract is approved; betting decisions are deferred.
- Keep `season`, `week`, `game_id`, `team` keys and consistent `off_*`, `def_*`, `adj_*` prefixes.

## Repository layout

| Component | Location | Notes |
|---|---|---|
| Python pipeline | `src/`, `scripts/`, `conf/`, `tests/` | Python 3.12, `uv`; never move or rename these roots |
| Season engine | `src/cks_picks_cfb/season/`, `scripts/pipeline/run_season.py` | Prepare, verify, release, rollback |
| Research | `scripts/research/`, `conf/research/` | Isolated; see `scripts/research/README.md` |
| Web app | `web/` | Next.js 16, React 19, Tailwind v4, npm; own `package.json` |
| Contracts | `contracts/` | Canonical schema (`schema.sql`, `schema.ts`), team mapping (`teams.py`, `teams.ts`) and append-only migrations (latest 0028) |
| Durable data | Cloudflare R2 | Source of truth; Neon is derived serving state |

Data flow: immutable R2 captures and reconciled Silver inputs, then a hash-pinned revision manifest, then `run_season.py prepare` (measurements, ratings, predictions, grades, verified projections), then Preview rehearsal, then an owner-approved atomic Production release in Neon, then Vercel reads the active release through Drizzle with ISR.

The web copies of `schema.ts` and `teams.ts` in `web/src/lib/` must match `contracts/` exactly (web-only team helpers live in `web/src/lib/team-routes.ts`); `make contracts-check` verifies this. Migrations run only through `scripts/pipeline/migrate_db.py --database-url <verified target>`; `make migrate-db` is disabled.

Site: the 4-tab interface (Games `/`, Ratings `/ratings`, Graphs `/stats`, Model `/model`, plus `/matchup/[gameId]` and `/teams/[team]`). Matchup pages are on unless `CFB_MATCHUP_ENABLED=0`; `CFB_UI_TEST_MODE=1` serves fixtures. Details in [`web/README.md`](web/README.md).

## Workflow

- **Branches:** `main` is production (Vercel deploys from it); `dev` is the working branch. Short-lived branches come off `dev` and are deleted after merging. Release by merging `dev` into `main`. Delete merged branches locally and on GitHub.
- **Substantial work** (architecture, data/model lineage, schemas or migrations, production behavior, security, multi-subsystem) uses Sol planning, then Terra implementation: plan with `.agent/skills/plan-session/`, persist the approved contract at `docs/plans/YYYY-MM-DD/<slug>.md`, then implement in a fresh task with `.agent/skills/implement-plan/`. Localized changes use the fast path. Lifecycle rules are in [`docs/plans/index.md`](docs/plans/index.md); strategic roadmaps stay in `docs/planning/`.
- **Weekly update:** follow the [weekly runbook](docs/ops/weekly_runbook.md), the sole operational authority: `make season-close-week` (the incremental rollover), `season-prepare`, `season-release`, `season-rollback`. `season-revision` is the full-history repair path and refuses to run without `FULL_HISTORY=1`. Reconcile the full FBS schedule against fresh spread and total coverage; prior null lines do not prove the provider lacks lines. Commit pinned inputs before preparing from a clean tree and do not commit between prepare and the last release. Production rollback needs the owner credential. Legacy `weekly`, `publish-week`, `freeze-week` and `close-week` targets refuse execution.
- **Start a session:** verify only the storage the task needs.
- **End a session:** write `session_logs/YYYY-MM-DD/NN-slug.md` from [`session_logs/TEMPLATE.md`](session_logs/TEMPLATE.md); run validation scoped to the change; do not broad-format a dirty worktree; update docs and the implementation contract when behavior changed and `docs/status.md` when week state changed; propose a commit message and leave git operations to the user.
- **Skills:** [`.agent/skills/CATALOG.md`](.agent/skills/CATALOG.md) (start-session, plan-session, implement-plan, end-session).

## Validation

```bash
make check    # mirrors CI: ruff, contracts, quality registry, pytest, mkdocs --strict, web lint/typecheck/tests/build
make test     # Python tests only
uv run pytest tests/<file>.py
```

`make help` lists every target. Run scripts with `PYTHONPATH=src:.` from the repository root (or `uv run`).

## Troubleshooting and pitfalls

- **Missing data or path errors:** check `CFB_STORAGE_BACKEND`, `CFB_MODEL_DATA_ROOT` and that the drive is mounted (`ls /Volumes/`); confirm the script reads the environment rather than a hardcoded path.
- **Prepare or release refusal:** confirm revision URIs and SHA-256s, the intended wrapper and exact score exceptions. Prepare needs a clean tree and release needs the same commit. Read `season_verification_v2` failures and follow the runbook; never bypass gates.
- **Training on 2020 or leaking future data:** exclude 2020 from all V5 and research inputs; use point-in-time loading for temporal splits.
- **Screenshots of gated pages:** `next start` returns the 404 page for gated routes, so open them with their flag (for example `CFB_MATCHUP_ENABLED=1`) plus `CFB_UI_TEST_MODE=1` and look at the image before sending it.
- **Raw `db.execute()` in the web app:** the Neon HTTP driver returns `{ rows }`, not an array. Use `existsFrom`/`rowsOf` from `web/src/lib/db-result.ts`. Fixture mode bypasses the database, so check optional-table features once against a real Preview database.
- **Correlated subqueries in drizzle selects:** in a single-table select `${table.col}` renders unqualified and binds to the inner alias. Qualify outer references with the table name (see `web/src/lib/tie-sql.ts`) and verify against real data.

## Links

[`README.md`](README.md) | [`docs/index.md`](docs/index.md) (authority map) | [rating requirements](docs/modeling/rating_system_requirements.md) | [measurement catalog](docs/modeling/measurement_catalog.md) | [betting policy](docs/modeling/betting_policy.md) | [decision log](docs/decisions/decision_log.md) | operational config in `conf/season/2026/`
