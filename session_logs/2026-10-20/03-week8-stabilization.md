# 2026-10-20 — Week 8 stabilization: site fixes, shared registry, workflow targets

Follows the Week 8 line refresh ([log](02-week8-line-refresh.md)). Done in a detached worktree off `origin/dev` because another session had uncommitted work in the primary checkout.

## Site

- **Results is a single-week view.** The season block is gone. It shows that week's spread and total record, average miss and 95% interval coverage (`getV5Performance(season, undefined, week)`), and links to `/performance`. The accuracy line appears from the `sm` breakpoint up; on phones it is hidden so the first game card still clears the bottom navigation. Picks keeps the season record.
- **Spread notation.** `homeSpreadFromMargin` and `homeSpreadText` (`lib/betting-format.ts`) render a home-margin forecast as the home spread (`-margin`). Applied on the Performance audit and team pages. Matchup pages and the Picks/Results cards already used spread notation. Check: the audit now reads "Jacksonville State -2.5 … Forecast Jacksonville State -4.2" for FIU @ Jacksonville State.
- **Biggest edges.** "Best Bets" is renamed. `getBiggestEdgesRecord` (`lib/queries.ts`) replaces loading every scored week's full games: one read of the selected runs' predictions, one batched selections read, then the same `overlaySelection`, `withFrozenLines` and `leanFor` steps, ranked by `biggestEdgesRecord`. A unit test checks it against the per-week `topLeans` ranking including ties. Live check: production (old code) and the local new code both show 45–35–0 (56.3%).
- **One slate loader.** `lib/slate-page.ts` holds the test-fixture branch, run selection, display-only notice, performance scope and sort parsing for Picks and Results. `V5_INTENDED_UPDATE_MODEL_ID` lives in `run-selection.ts`; the stale `"Trench Warfare V5"` fallback is gone, so a season-2026 slate with no games no longer invents a system name.
- **Dead modules deleted:** `HistoricalModelContext.tsx`, `RecordBanner.tsx`, `slate/EdgeNote.tsx`, `slate/ResultLeanRow.tsx`.

## Data architecture and workflows

- **Projection-set registry.** `contracts/projection_sets.json` is loaded by `projection_common.PROJECTION_SETS`; `web/src/lib/projection-sets.json` is a byte-identical mirror; `RECORDED_PROJECTION_SETS` is derived from it. `contracts/validation.py` (`make contracts-check`) fails when the mirror drifts. The exact `code_sha` pin in `run_season.py` is unchanged.
- **Market-only builder tests** (`tests/test_build_market_revision.py`): changes only the quotes, the target-week cutoff and the revision identity; refuses to overwrite; refuses a late capture or an incomplete schedule; registers nothing when the manifest is invalid.
- **Make and docs.** `make season-market-revision`, `make season-prepare MANIFEST=` (default still `_v1`), a "Mid-week line refresh" runbook section, `.codex/QUICKSTART.md`.
- **Capture CLI moved** from `scripts/research/` to `scripts/pipeline/`; the compatibility manifest, the pregame-capture workflow and the capture runbook point at the new path.
- **Plans.** Charts plans `2026-10-16/01`, `2026-10-18/01`, `2026-10-18/03` and mobile release `2026-10-19/01` closed out (Charts "complete as released, hidden"; visual verification deferred). Phase C contract drafted: [incremental weekly ingestion](../../docs/plans/2026-10-20/02-incremental-weekly-ingestion.md), Draft, no provider calls.

## Verification

- `make test`: 3,407 passed, 34 skipped. `tests/test_season_release_postgres.py` against a disposable cluster: 125 passed.
- `ruff format --check`, `ruff check`, `make contracts-check`: clean.
- Web: `lint`, `typecheck`, `test:publication` (268 pass), `build`, `test:ui` (152 pass, 9 skipped), `test:charts-gate` (12 pass).
- Local run against production data: Results Week 7 is 26–32–1 spread and 32–27–0 total with no season block; Biggest edges is 45–35–0.

## Open items

- `uv run mkdocs build --strict` fails on a link that predates this work: `docs/planning/weekly-operations-process-review.md` links into `session_logs/`, which is outside the docs tree. CI does not run mkdocs. Not changed here.
- Hygiene deletions need owner confirmation: the stale `sos-sor-draft` branch (`6b3f07a1`) and `stash@{0}` (2026-10-02).
