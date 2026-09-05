# Repository Boundaries

This page is the architectural authority for code ownership, dependency
direction, and compatibility during the data-first football forecasting
program. The [production runbook](../ops/production_runbook.md) remains the
authority for operating the live system. The
[data-first roadmap](../planning/data-first-football-forecasting-roadmap.md)
governs research sequence and evidence policy.

## Current production system

V4 bundle `week0-2026-v4-strict-20260818-r2`, configured by
`conf/weekly_bets/v4_2026.yaml`, remains the production champion. Supported
weekly commands resolve immutable R2 inputs, generate predictions, publish a
durable prediction artifact, copy that derived view to Neon, freeze the scored
artifact identity, and close the week after finalized outcomes. The Next.js
application in `web/` reads the fail-closed Neon serving view.

Ownership is divided as follows:

| Area | Owner | Responsibility |
|---|---|---|
| Reusable Python | `src/cks_picks_cfb/` | Data contracts, features, bundles, inference, ratings, and operations |
| Production commands | `scripts/pipeline/` and `src/cks_picks_cfb/ops/` | Supported weekly orchestration and publication |
| Production configuration | `conf/weekly_bets/` and applicable shared `conf/` groups | Frozen runtime and model choices |
| Durable evidence | Cloudflare R2 | Immutable source captures, datasets, bundles, runs, and reports |
| Web serving state | Neon Postgres | Derived current predictions, results, and system statistics |
| Shared schema | `contracts/` | Canonical SQL, TypeScript schema, migrations, and team-name mapping |
| Web application | `web/` | Read-only product presentation and health interfaces |

R2 is the durable source of truth. Neon is a derived serving database. Schema
and team mapping copies in the web app and publisher are checked against
`contracts/` before release.

## Data-first research system

The new program uses this flow:

```text
audited immutable data → football measurements → opponent adjustment
→ preseason and in-season ratings → spread and total forecasts
→ prospective evaluation → timestamped line comparison
```

New executable research commands live in `scripts/research/`. Reusable logic
lives in `src/cks_picks_cfb/`, with rating and forecasting components under
`src/cks_picks_cfb/ratings/` where appropriate. Exploratory notebooks and
analyses stay in `research/` and cannot become production dependencies.

New program configuration lives under
`conf/research/data_first_football_v1/`. Its artifacts use only
`artifacts/research/data-first-football-v1/`. The 2015–2019 and 2021–2025
development corpus, including 2025 as development evidence, applies only to
this namespace. Existing V4 and named benchmark identities retain their
original season policies and locations.

Research code cannot publish, freeze, close, migrate, deploy, or change live
state. Timestamped market lines are joined after football evaluation for
comparison. Betting selection, staking, bankroll management, and threshold
optimization are outside the program.

## Dependency direction

```text
scripts/pipeline ─┐
scripts/research ─┼─> src/cks_picks_cfb
tests ────────────┘

src/cks_picks_cfb ─X─> scripts/*
production code ──X─> research/*
production code ──X─> artifacts/research/data-first-football-v1
```

Production commands may depend on reusable library modules. Research commands
may use the same stable interfaces. Reusable modules cannot import executable
scripts, and production modules or commands cannot import either research
command location. A reusable component that could alter V4 behavior must be
introduced behind a new versioned research interface.

## Compatibility and versioning

`conf/repository/compatibility_v1.yaml` records the supported commands,
required paths, V4 identity, and named benchmark paths. Phase 0 preserves:

- V4 prediction, routing, publication, artifact loading, and rollback paths.
- The certified R1 foundation and artifact readers.
- The fixed rating measurement and team-state baseline.
- Candidate-v1 shadow evaluation.
- The completed R2 prior tournament.
- Direct early-game candidate generation and evaluation.

An invalidated research result remains readable as historical evidence but
does not remain eligible for model selection. Measurement-definition changes,
corrected research datasets, and materially changed candidates receive new
identities. Existing source captures, reports, production configs, and bundle
references are never rewritten to imply new lineage.

## Moving or deleting files

An existing command, config, or module can move or be removed only after all
of these are established:

1. Static imports, subprocess calls, Make targets, docs, configs, tests, and
   artifact identity references have been checked.
2. Production and named benchmark behavior has an equivalent tested path or a
   compatibility wrapper.
3. The replacement and pinned recovery commit are recorded in a disposition
   report.
4. Contract synchronization, deterministic inference, CLI smoke checks,
   Python tests, docs validation, and web checks pass.
5. The active implementation contract explicitly authorizes the change.

Static reference counts alone cannot authorize deletion because orchestration
and stored artifact identities may resolve paths dynamically. Phase 0 therefore
classifies existing research and legacy files without moving or deleting them.
