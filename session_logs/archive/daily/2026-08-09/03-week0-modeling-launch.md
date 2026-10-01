# Session: 2026 Week 0 Modeling and Launch

## TL;DR

- **Worked On:** Implemented the 2021–2025 temporal training contract, five completed-game regimes for spread and total, immutable Gold dataset inputs, Week 0 operations, and preview replay workflow.
- **Completed:** Local implementation and verification. The repository now supports training/selection on 2021–2024, a locked 2025 test, unchanged 2021–2025 refit, 2019 only as the early-2021 prior, and complete exclusion of 2020.
- **Blockers:** Live preview setup still needs Neon authentication/`PREVIEW_DATABASE_URL`, preview R2 credentials, a registered Gold feature dataset, the promoted model bundle, and Vercel revalidation configuration.
- **Next:** Provision the isolated preview resources, migrate the preview database, run `make audit-data`, train/evaluate/refit the ten-route bundle, replay 2025, and execute the Week 0 readiness/publish/freeze flow.

## Changes Made

- Added a versioned Week 0 training policy and validation for temporal folds, the locked test, production refit, prior-source overrides, and excluded seasons.
- Added point-in-time completed-game routing using each team's own count and the matchup minimum for the 0/1/2/3/4+ route.
- Added Ridge, CatBoost, and monotonic blend candidate generation and deterministic promotion selection for separate spread and total routes.
- Extended `model_bundle_v2` with executable `direct` and `blend` strategies and immutable dataset/model checksums.
- Added immutable Gold regime-feature building and `python -m cks_picks_cfb.ops audit-data`.
- Added production refit tooling for an unchanged selected design on 2021–2025.
- Made Week 0 valid in the orchestrator, serving query, navigation, replay, and publication paths.
- Standardized replay and preview operations on `PREVIEW_DATABASE_URL`.
- Updated modeling, operations, architecture, promotion, and quickstart documentation.

## Testing

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run pytest -q` — 248 passed
- [x] `.venv/bin/python contracts/validation.py`
- [x] `uv run mkdocs build` — passed with existing documentation-link warnings
- [x] `npm run lint`
- [x] `npm run typecheck`
- [x] `npm run build`
- [x] `git diff --check`
- [ ] Preview browser smoke tests — blocked until isolated Neon/R2/Vercel preview resources exist
- [ ] Full 2025 preview replay — blocked until the preview resources and promoted bundle exist

## Notes for Next Session

1. Authenticate the Neon CLI or provide `NEON_API_KEY`; create/reuse an isolated Week 0 preview branch and set `PREVIEW_DATABASE_URL`.
2. Provision a separate preview R2 bucket and scoped credentials. Do not reuse production storage credentials.
3. Apply the append-only SQL migrations to the preview branch.
4. Build/register explicit Silver and Gold dataset versions, then run `make audit-data`.
5. Run `make train-week0`, `make evaluate-week0`, and `make refit-week0-bundle` with the immutable dataset references.
6. Run `make replay-season YEAR=2025 ENV=preview`, verify the preview site, then start the 2026 Week 0 progressive publication cycle.

Proposed commit message: `feat: prepare 2026 week zero regime modeling and launch`

**tags:** ["week-0", "modeling", "temporal-validation", "data-platform", "operations", "preview"]
