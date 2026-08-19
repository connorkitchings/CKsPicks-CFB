# CKsPicks-CFB Documentation

[![Project Status: Alpha](https://www.repostatus.org/badges/latest/alpha.svg)](https://www.postatus.org/#alpha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Welcome to the central documentation hub for the **CKsPicks-CFB** project — a
college football betting model (Python pipeline) with a Next.js web app on
Vercel, backed by Neon Postgres and a Cloudflare R2 immutable data lake.

> **📖 Start Here:** [Documentation Guide](./guide.md) — Single source of truth for all project documentation

## 2026 Season Status

The 6-phase buildout is complete and **production is live** at
`https://c-ks-picks-cfb.vercel.app` (fail-closed `market` mode, V4 bundle
`week0-2026-v4-strict-20260818-r2`). Remaining: game-week operations under the
[Week 0 Launch Contract](./plans/2026-08-18/week0-launch-execution.md).

## Quick Navigation

- **[📖 Documentation Guide](./guide.md)** — Main hub with complete navigation
- **[Week 0 Launch Contract](./plans/2026-08-18/week0-launch-execution.md)** — Active operations (Stages 4–5)
- **[Roadmap](./planning/roadmap.md)** — 2026 status and timeline
- **[Production Runbook](./ops/production_runbook.md)** — As-built production operations
- **[Weekly Pipeline](./ops/weekly_pipeline.md)** — Publish/freeze/close workflow
- **[Early-Season Regimes](./modeling/early_season_regimes.md)** — Five completed-game routing contract
- **[2026 Data Platform](./architecture/data_platform_2026.md)** — Immutable lake/catalog architecture
- **[Decision Log](./decisions/decision_log.md)** — Decision history and rationale
- **[Experiments](./experiments/index.md)** — Experiment tracking (V2 history + 2026 tournament)
- **Session Logs:** See `session_logs/` folder for daily development logs

> **Note:** Documentation reorganized 2025-12-04; realigned to the 2026 dual-stack architecture on 2026-08-19. All docs are accessible from [guide.md](./guide.md).
