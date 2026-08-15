# Session: 2026 Preview Readiness and Publication Preparation

## TL;DR

- **Worked On:** Historical data repair, 2026 CFBD capture, early-season model routing, Pick'em contract, and web readiness.
- **Completed:** Rebuilt audited preview Gold data, captured available 2026 data, published a display-only ten-route preview model bundle, and passed the local web production build.
- **Blockers:** No current CFBD talent data; all routes remain display-only because authentic historical market lines are quarantined. Vercel preview upload is rate-limited before a new deployment is registered. Pick'em needs a separate current prediction token and final user approval. The schema-only Neon branch needs a catalog-hydration path for the immutable Preview R2 history; serial import was safely interrupted after confirming 7,156 already-present eligible objects.
- **Next:** Hydrate the Preview catalog from existing verified R2 observations, resume Silver/Gold registration, then generate/publish a Week 0 preview run and smoke test the protected preview. Obtain explicit production and Pick'em submission approval only after Preview passes.

## Data and Model Results

- Refreshed immutable CFBD `game_outcomes` for 2021–2025 and rebuilt preview Gold lineage as of `2026-08-14T13:15:00Z`.
- Structural and model-ready preview audits passed: 2021–2025 labels, 2026 Week 0 schedule, transitive Bronze/Silver lineage, regime coverage, and baseline completeness.
- Captured available 2026 preview sources: teams (138), games (888), venues (150), rosters (15,442), coaches (138), rankings (25), recruiting (221), and Week 1 betting lines (102); preseason snapshot captured returning production (136), transfers (4,441), recruiting (824), and coaches (138).
- CFBD talent remains unavailable. The explicit `prior_only_fallback` is display-only; one Week 0 row requires model imputation for prior features.
- Created preview bundle `week0-2026-preview-20260814`, manifest SHA `c151a5b635d333839c2cfa940c45d2fdc18c40dac28c094859c63137f5bb4066`. All 10 routes load and predict all eight Week 0 FBS-vs-FBS games; zero routes are high-confidence eligible.
- Selection (2022–2024) and locked 2025 routing evaluation correctly yielded `display_fallback` for every route because archived market lines are quarantined and cannot provide authentic promotion-volume evidence.

## Publication and Pick'em

- `/api/health` now exposes the active run's `dataAsOf` field.
- CFBD Model Pick'em exporter now uses the prediction-token endpoint and submits one `{gameId, pick}` at a time after exact contest-game reconciliation; totals are excluded.
- `npm run build` in `web/` passed.
- Vercel project link is configured locally. Preview deploy attempts did not create a deployment: normal upload hit the free-tier file-count limit; compressed upload ended before Vercel registered a deployment. Existing ready preview remains unchanged.
- Created the schema-only Neon branch `preview-2026`, applied migrations `0002`–`0004`, and switched local `.neon` context to it. The durable Preview branch now has separate SQL-created migrator, pipeline, and read-only web roles; none inherit `neon_superuser`.
- Applied migration `0005` to seed the neutral `current_week` singleton required by a schema-only branch. The Preview model bundle now has a separate, immutable Preview-only weekly configuration, and preflight supports an exact timestamp cutoff while mapping CFBD provider Week 1 through the checked-in canonical Week 0 policy.
- Stored the Preview pipeline and migration connection strings in the local macOS Keychain. Vercel Preview now uses only the read-only web connection with an explicit `CFB_PUBLICATION_SEASON=2026` / `CFB_PUBLICATION_WEEKS=0` scope. Production's database variable was restored after splitting the formerly shared target.

## Testing

- [x] `git diff --check`
- [x] Targeted pytest: 25 passed
- [x] Targeted Ruff check: passed
- [x] `npm run build` in `web/`: passed
- [x] Preview structural and model-ready audits: passed
- [x] Preview schema migrations and least-privilege role checks: passed
- [x] Focused bootstrap/readiness tests and lint: passed (20 tests)
- [x] Keychain-backed Preview command wrapper syntax and migration check: passed

## Notes for Next Session

- Do not promote the preview bundle or deploy production without explicit user approval.
- Do not submit Pick'em without `CFBD_PREDICTION_TOKEN` and explicit final-slate approval.
- The preview data/model artifacts are immutable under `artifacts/preview/refs/refresh-20260814/` and `artifacts/preview/models/week0-2026-preview-20260814/`.
- `CFB_MODEL_DATA_ROOT` is mounted and accessible. Preview preflight now passes storage, schema, control-row, deployment-layout, and ten-route bundle checks; data catalog hydration, Week 0 publication, Vercel deployment, branch protection, and legacy preview-branch deletion remain pending.

## End-of-Session Handoff

- `make hydrate-history` registered all 7,156 eligible existing Preview R2 source captures in `preview-2026`; its final workflow-status update was interrupted by a transient Neon `AdminShutdown` after the batch insert completed. Confirmed: `catalog.source_captures = 7,156` and `catalog.dataset_versions = 0`.
- Resume with `zsh scripts/ops/with_preview_env.sh make import-history-silver` after remounting the SSD. That should reuse the hydrated catalog and immutable Preview R2 objects to register Silver/Gold datasets; do not rerun raw `make import-history`.
- Then run Preview readiness with `CONFIG=conf/weekly_bets/v2_preview_2026.yaml`, publish only canonical Week 0, deploy Vercel Preview, verify `/api/health`, protect `preview-2026`, and only then delete `week0-2026-preview`.
- The external SSD was safely disconnected after all running data operations stopped.
- End-session validation: targeted Python formatting; `uv run ruff check .`; `uv run pytest -q` (**304 passed**); and `git diff --check` all passed. Full-repository formatting was intentionally not run because the worktree contains unrelated in-progress user changes.

**tags:** ["2026", "preview", "data", "models", "pickem", "vercel"]
