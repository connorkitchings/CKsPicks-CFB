# Session: Games 1–3 Modeling Implementation

## TL;DR

- **Worked On:** Approved early-season modeling and branch-consolidation contract.
- **Outcome:** Games 1–3 result-only evaluation is now implemented; historical
  odds remain optional betting research rather than a model-readiness blocker.
- **Plan Contract:** [Games 1–3 Modeling](../../docs/plans/2026-08-15/games-1-3-modeling.md)
- **Approval / Status:** User explicitly authorized implementation on 2026-08-15.
- **Blockers:** Private v3 prediction generation passed, but full Preview
  preflight is blocked by missing isolated-Neon pipeline/publication tables,
  `current_week.active_run_id`, and an incomplete 2026-08-16 preseason snapshot.
- **Next:** Repair the Preview operational schema/snapshot, rerun readiness,
  then review the private v2-v3 comparison before any activation decision.

## Context and Decisions

- First, second, and third scheduled team games map to `game_1`, `game_2`, and
  `game_3`; historical labels remain readable.
- The Odds API is the selected timestamped historical source. Paid data access
  requires a dry-run request and credit estimate before backfill.
- Best available pre-kick quote is the selected execution policy.
- `artifacts/preview/` is user-owned and was preserved unmodified and unstaged.
- `main` was fast-forwarded locally to the web presentation tip; the new work
  starts at `codex/games-1-3-modeling`. Remote push and branch deletion remain
  user-controlled.

## Work Completed

- Consolidated the local branch baseline and created `codex/games-1-3-modeling`.
- Added canonical matchup routes (`game_1`, `game_2`, `game_3`, `established`)
  while retaining legacy route parsing and bundle support.
- Added model-bundle v3 loading/prediction, weekly pipeline/preflight support,
  database/web route compatibility, and a migration for new stored regimes.
- Added team-side empirical-Bayes feature helpers, direct-versus-points-derived
  candidate generation, nested temporal threshold selection, and quote-aware
  promotion gates.
- Added a The Odds API historical adapter, event reconciliation, executable
  best-quote grading, and a no-network cost-estimate command:
  `scripts/data/estimate_historical_odds_backfill.py`.
- Added focused test coverage for ordinal routing, shrinkage, market grading,
  historical quote handling, v3 bundles, candidate generation, and promotion.
- Added a separate result-only predictive evaluator, canonical training
  workflow, and immutable routing-report command. It has no market-line,
  price, or ROI dependency.
- Added a v3 refit command that retrains selected early routes and retains the
  established routes from an explicitly supplied, checksummed source bundle.
- Split Games 1–3 selection from locked validation, froze the immutable
  selection SHA before opening 2025, and added Ridge-grid/CatBoost-finalist
  candidate generation plus canonical frozen blend weights.
- Produced the private Preview selection/final routing reports and the complete
  eight-route bundle `week0-2026-games-ordinal-v3-20260816-r2`; generated a
  local Week 0 v2-v3 comparison from the active eight-game input snapshot.

## Files Modified

- `docs/plans/2026-08-15/games-1-3-modeling.md` — approved implementation contract.
- `session_logs/2026-08-15/05-games-1-3-modeling.md` — implementation log.
- Core implementation: `src/cks_picks_cfb/{data,features,models}/`,
  `src/cks_picks_cfb/model_bundle_v3.py`, and pipeline/config/contracts/web
  compatibility files listed in the working-tree diff.

## Validation

- [x] `uv run pytest` — 338 passed, 2 skipped.
- [x] `uv run ruff check .`
- [x] `uv run python contracts/validation.py`
- [x] `uv run mkdocs build --quiet`
- [x] `npm run lint`, `npm run typecheck`, `npm run test:publication`, and
  `npm run build` in `web/`.
- [x] `git diff --check`
- [x] Focused result-only evaluator and ordinal-model tests.
- [x] Result-only evaluator/refitter CLI help checks.
- [x] Sealed Preview selection, guarded 2025 validation, v3 refit, and private
  Week 0 prediction smoke test.
- [x] `uv run pytest -q` — 345 passed, 2 skipped.
- [x] Ruff, contracts validation, MkDocs, web lint/typecheck/publication/build,
  and `git diff --check`.

## Amendments and Blockers

- No paid API requests were issued. The estimate command makes zero network
  requests and reports expected historical snapshot credits from a schedule.
- The historical-odds adapter remains decoupled. It must not be substituted
  with legacy untimestamped lines if betting research is resumed.
- Preview preflight is intentionally not treated as passed: the isolated Neon
  branch lacks the required tables/column and the preseason snapshot is not
  complete. This is operational state outside the sealed modeling bundle; the
  active v2 Preview and market-only public configuration were not changed.

## Handoff Notes

- **Resume at:** Run `make train-week0` with the immutable canonical Gold
  feature reference, then freeze the result-only report and use
  `make refit-game-ordinal` with the established-route bundle specification.
- **Watch out for:** Preserve `artifacts/preview/`; do not make paid API calls,
  promote a route, or publish production changes without separate approval.

**tags:** ["modeling", "early-season", "odds", "implementation"]
