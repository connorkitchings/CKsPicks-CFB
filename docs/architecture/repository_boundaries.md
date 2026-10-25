# Repository Boundaries

This page is the architectural authority for code ownership, dependency direction and compatibility. The [weekly runbook](../ops/weekly_runbook.md) is the authority for operating the live system; [Current Status](../status.md) holds live release IDs. V5 Blitzkrieg is the only operational model (see the [V5 status guide](../modeling/v5_status.md)); V4 is historical evidence in the [V4 retrospective](../modeling/v4_retrospective.md), and its training and serving code was removed on 2026-10-22.

## Ownership

| Area | Location | Responsibility |
|---|---|---|
| Season engine | `src/cks_picks_cfb/season/`, `scripts/pipeline/run_season.py`, `scripts/pipeline/build_season_revision.py` | Revision manifests, chronological preparation, grading, verification, serving projections, atomic release and rollback |
| Weekly data steps | `src/cks_picks_cfb/ops/`, `scripts/pipeline/`, `scripts/data/` | Ingestion, Silver builds, `prepare-week`, team-stats and matchup-data publication, catalog reconciliation and audits |
| Reusable libraries | `src/cks_picks_cfb/` (`data/`, `features/`, `charts/`, `metrics/`, `ratings/`, `forecast/`, `models/`, `quality/`, `db/`) | Lake and catalog, football measurements, ratings, forecasts, market grading, data-quality registry |
| Operational configuration | `conf/season/2026/`, `conf/weekly_bets/`, `conf/policy/`, `conf/quality/` | Sealed model manifest, revision manifests, exact score exceptions, week policy, quality policy |
| Research | `scripts/research/`, `scripts/analysis/`, `src/cks_picks_cfb/ratings_lab/`, `audit/`, `conf/research/` | Isolated research runners, verifiers and configurations |
| Shared schema | `contracts/` | Canonical SQL and TypeScript schema, append-only migrations (latest 0028), team-name mapping |
| Web application | `web/` | Read-only product (Games, Ratings, Stats, Model tabs; matchup and team pages; `/api/health`) |
| Durable evidence | Cloudflare R2 | Immutable captures, datasets, runs and reports; the source of truth |
| Serving state | Neon Postgres | Derived season releases and projections; catalog metadata |

Schema and team-mapping copies in `web/src/lib/` are checked against `contracts/` by `make contracts-check`. Named benchmark readers (the certified R1 foundation and fixed rating baseline) remain under `scripts/pipeline/` and `src/cks_picks_cfb/ratings/` and are recorded in the manifest below.

## Data flow

```text
audited immutable data → football measurements → opponent adjustment
→ ratings + uncertainty → Ridge margin/total bridge → calibrated forecasts
→ point-in-time evaluation → timestamped line comparison
```

Operationally, `run_season.py prepare` computes this chain chronologically from a hash-pinned revision manifest and writes verified serving projections; `release` stages them and atomically activates the release in Neon after Preview rehearsal. Measurements record possession and scoring evidence; opponent adjustment happens once, upstream of ratings. Markets are joined only after football evaluation. Betting selection, staking and threshold optimization are outside the program.

## Dependency direction

```text
scripts/pipeline ─┐
scripts/research ─┼─> src/cks_picks_cfb
tests ────────────┘

src/cks_picks_cfb ─X─> scripts/*
production code ──X─> scripts/research/*
production code ──X─> artifacts/research/data-first-football-v1
```

Commands may depend on library modules. Library modules cannot import executable scripts, and production code cannot import either research location. Research commands may freeze and score isolated shadow artifacts under `artifacts/research/data-first-football-v1/` using configuration from `conf/research/data_first_football_v1/`, but cannot publish, migrate, deploy or alter Production state; promotion needs a separate approved contract. Research development evidence is 2015-2019 and 2021-2025, excluding 2020.

## Compatibility manifest

`conf/repository/compatibility_v1.yaml` records the public make targets, required paths (production, contracts, web, research, V5), named benchmark paths and the prohibited import and output prefixes. `tests/test_repository_boundaries.py` enforces it: required paths exist, declared make targets exist, library and production scripts import no research namespaces, and research configs reference no production outputs.

An invalidated research result stays readable as historical evidence but is not eligible for model selection. Changed measurement definitions, corrected datasets and materially changed candidates receive new identities; existing captures, reports and configs are never rewritten to imply new lineage.

## Moving or deleting files

A command, config or module may move or be removed only after all of these hold:

1. Static imports, subprocess calls, make targets, docs, configs, tests and stored artifact identities have been checked; reference counts alone do not authorize deletion because orchestration can resolve paths dynamically.
2. Nothing in the live V5 graph, `scripts/research/`, `scripts/analysis/` or the research packages imports it.
3. A replacement or recovery commit is recorded (for V4, see the retrospective).
4. Contracts, tests, strict docs build and web checks pass (`make check`).
5. The active implementation contract authorizes the change.
