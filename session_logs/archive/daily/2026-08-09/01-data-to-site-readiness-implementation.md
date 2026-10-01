# Session: 2026 Data-to-Site Readiness Implementation

## TL;DR

- **Worked On:** Implemented the run-versioned 2026 ML-to-site control plane, completed-game regimes, fail-closed weekly operations, site run selection, and the early-season evaluation contract.
- **Completed:** Immutable R2 run/model artifacts, point-in-time feature snapshots, Neon run schema/migration, progressive publish/freeze/close commands, preview replay isolation, run-aware UI/health, local Geist, canonical training entry point, and promotion tests.
- **Blockers:** Live readiness/replay was not run because R2, Neon, `CFB_STORAGE_BACKEND`, and `CFB_MODEL_DATA_ROOT` are not configured in this session. The champion config intentionally has null durable model metadata until promoted bundles are uploaded.
- **Next:** Upload promoted spread/total bundles and fill their metadata, apply migration `0002_prediction_runs.sql` to an isolated Neon branch, capture the real 2026 preseason snapshot, then run `make readiness YEAR=2026 WEEK=1 AS_OF=<date> ENV=preview` and the 2025 preview replay.

## Changes Made

- Added immutable prediction/scored/model artifact paths, checksums, manifests, production/preview namespaces, and an explicit temporary working root.
- Added canonical team-keyed point-in-time feature snapshots with cutoff, completed-game count, provenance, and missingness fields.
- Added 0/1/2/3/4+ completed-game routing and monotone, separately selected spread/total blend weights; preseason features now cover any scheduled week.
- Added five-gate target/regime promotion evaluation and a ten-cell Ridge/CatBoost routing-report command.
- Added `prediction_runs`, `predictions`, `current_week.active_run_id`, compatibility view, and legacy-row migration.
- Added fail-closed publish validation, progressive line handling, freeze coverage/waivers, exact frozen-artifact scoring, and transactional scored-state publication.
- Added readiness, publish, freeze, close, and isolated replay Make targets.
- Updated Next.js reads and UI for immutable run state, regime/model labels, missing-line behavior, historical frozen runs, expanded safe health output, and local Geist fonts.
- Retired obsolete training wrappers and updated active training/operations documentation to the canonical module entry point.

## Testing

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run pytest -q` — 219 passed
- [x] `uv run python contracts/validation.py`
- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run build`
- [ ] Live Neon migration/readiness — credentials not configured
- [ ] 2025 Neon/Vercel preview replay — preview branch/deployment not configured

## Notes for Next Session

The readiness command is expected to fail until both model entries in `conf/weekly_bets/v2_champion.yaml` contain an immutable URI, SHA-256, schema/feature versions, training years, code SHA, and promotion report matching the uploaded artifact manifest. Preview replay writes under `artifacts/preview/` and refuses to use the production database URL.

**tags:** ["2026", "modeling", "early-season", "pipeline", "r2", "neon", "nextjs", "readiness"]
