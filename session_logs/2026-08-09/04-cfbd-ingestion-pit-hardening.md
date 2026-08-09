# Session: CFBD Ingestion and Point-in-Time Hardening

## TL;DR

- **Worked On:** Canonical request-level CFBD ingestion, immutable Bronze lineage,
  provider-neutral Silver contracts, cross-source reconciliation, deterministic
  point-in-time Gold features, and resumable operations.
- **Completed:** Migration `0004` was applied and verified on the isolated preview
  Neon branch. Production was not touched. Python, contract, migration, and web
  quality gates pass.
- **Blockers:** The preview catalog is empty (`0` captures and `0` dataset
  versions), so authenticated 2021-2026 capture/backfill, equivalence replay, and
  browser validation remain external execution work.
- **Next:** Capture CFBD fixtures and historical source responses into preview,
  build explicit Silver versions, reconcile 2021-2025, build Gold features, and
  run the audit before model training or Week 0 publication.

## Changes Made

- Added typed `SourceRequest`/`SourceResponse` contracts and a bounded,
  retry-aware `CFBDSourceAdapter` with fail-closed error classification.
- Changed ingestion to validate, write/reuse immutable canonical-JSON Bronze,
  register observations in Neon, and only then update compatibility projections.
- Fixed Week 0 truthiness defects and made plays/game-stat requests independently
  traceable by week.
- Added provider-neutral Silver contracts, deterministic market snapshots, FBS
  scope validation, explicit dataset/capture dependencies, and source
  reconciliation results.
- Split prior and current features in Gold, removed hidden early-season blending
  from canonical aggregation, and added deterministic team-side/wide builders.
- Corrected neutral travel, eastward travel, timezone/DST, weather missingness,
  temporal sort order, and completed-game eligibility behavior.
- Replaced hardcoded corrections in the canonical build with a required,
  versioned `data_corrections` reference; the hardcoded path remains compatibility
  only.
- Added resumable `fetch-source`, `build-silver`, `build-team-game`,
  `build-features`, and catalog-aware `audit-data` operations and Make wrappers.
- Upgraded and pinned the CFBD Python client to `5.20.1` and added SDK contract
  checks.
- Added append-only migration `0004_ingestion_hardening.sql` and updated the
  reconstructed schema.

## Testing

- [x] `uv run ruff format --check .`
- [x] `uv run ruff check .`
- [x] `uv run pytest -q` — 263 passed
- [x] `uv run python contracts/validation.py`
- [x] `uv run pytest -q tests/test_migrations.py` — 2 passed
- [x] `npm run lint` in `web/`
- [x] `npm run typecheck` in `web/`
- [x] `npm run build` in `web/`
- [x] Preview migration `0004` applied and schema verified
- [ ] Historical preview data audit (preview catalog has not been populated)
- [ ] 2021-2025 dual-run equivalence and full 2025 replay
- [ ] Preview browser smoke tests after replay/deployment

## Notes for Next Session

Do not run publication or model selection yet. The next boundary is authenticated
preview-only historical capture. Start with representative endpoint fixtures,
then backfill exact captures and build Silver versions from explicit capture IDs.
Run reconciliation before any Gold version is considered prediction-eligible.

**tags:** ["ingestion", "cfbd", "bronze", "silver", "gold", "point-in-time", "week0"]
