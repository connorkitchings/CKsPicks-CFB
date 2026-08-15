# Session: Week 0 Launch Readiness Implementation

## TL;DR

- **Worked On:** Historical data readiness, immutable weekly publication, market-only web mode, and CFBD Pick'em rehearsal for the August 29, 2026 Week 0 slate.
- **Outcome:** Preview data audits pass, private run `2026w0-d990f9b0e495` published exactly eight fully lined games with zero high-confidence claims, and an eight-row local Pick'em CSV was generated without an API call or submission.
- **Plan Contract:** [Week 0 Launch Readiness](../../docs/plans/2026-08-15/week0-launch-readiness.md)
- **Approval / Status:** User approved implementation in this task; contract is Implemented.
- **External Blocker:** `CFBD_PREDICTION_TOKEN` is not configured, so authenticated contest reconciliation and dry-run remain gated. This does not block market-only launch readiness.
- **Production State:** Unchanged. No production migration, Vercel deployment, Git staging/commit/push, or Pick'em POST occurred.

**tags:** ["week0", "data", "pipeline", "preview", "web", "pickem"]

## Decisions and Amendments

- Re-registered existing immutable R2 refs and their parent lineage instead of rebuilding or deleting historical artifacts.
- Captured corrected 2021–2025 final-score truth and rebuilt the affected immutable Gold chain after the legacy source incorrectly marked 2025 Army–Navy incomplete.
- Mapped canonical Week 0 to CFBD provider Week 1 by game ID while retaining both week values.
- Added a run-bound Bronze-to-Silver market build so weekly prediction input refs include immutable canonical quotes and snapshots.
- Removed the unused 2026 `reconciled_team_game` precondition and made prediction coverage depend on the frozen canonical games ref.
- Added a fail-closed public `market` mode; only the exact `predictions` value exposes model output.

See Amendments 1–4 in the implementation contract for the expected state, discovered conflicts, and scope analysis.

## Operational Evidence

- Structural data audit: `614931f330244386ab1ad9ee2d5f2cbb` — passed.
- Model-ready audit: `d9a90f9d24944b62907fb689b9ea2fe4` — passed.
- Week 0 readiness: `40e83fc7d84f4385a3b7f6fbb19406c9` — passed; ten routes and eight games verified, with two explicit display-only imputer fallbacks.
- Successful weekly pipeline: `d990f9b0e4954e829e7551b2fccd8dcd`.
- Published Preview prediction run: `2026w0-d990f9b0e495`.
- Market snapshot version: `e1b27542306d9f38826de41d`.
- Prediction artifact: `artifacts/preview/predictions/year=2026/week=0/run_id=2026w0-d990f9b0e495/predictions.csv`.
- Frozen input refs: `artifacts/preview/pipeline-runs/d990f9b0e4954e829e7551b2fccd8dcd/input_refs.json`.
- Preview database verification: 8 distinct predictions, 8 spreads, 8 totals, 0 high-confidence rows; `current_week.active_run_id` equals `2026w0-d990f9b0e495`.
- Local Pick'em output: `artifacts/preview/pickem/cfbd_pickem_2026_w0_2026w0-d990f9b0e495.csv` — 8 data rows, spread margin only.
- Failed runs remain recorded as incident evidence, including `f2e0f642600d4ea8a7f629e763fe7a31`, `02995cb08485464fa45ffb94a37947a2`, and the first failed steps of the resumed successful run.

## Main Files Changed

- `src/cks_picks_cfb/data/catalog.py` and affected builders — idempotent immutable ref recovery.
- `src/cks_picks_cfb/data/betting_lines.py`, `src/cks_picks_cfb/data/silver.py`, and `src/cks_picks_cfb/data/lake.py` — canonical/provider week handling and market normalization.
- `scripts/pipeline/build_week_market_snapshot.py`, `snapshot_week_inputs.py`, `generate_weekly_bets.py`, and `src/cks_picks_cfb/ops/__main__.py` — explicit run-bound market lineage and input freezing.
- `web/src/lib/publication.ts`, queries, page/components, health route, tests, and environment documentation — market-only public boundary.
- Historical refresh/build scripts, tests, and operational documentation listed in the worktree diff.

The repository was already substantially dirty when implementation began. Unrelated user-owned changes were preserved; no broad formatter, staging, cleanup, or commit was performed.

## Validation

- [x] `uv run pytest -q` — 313 passed.
- [x] `uv run ruff check .` — passed.
- [x] `make contracts-check` — passed.
- [x] `npm run test:publication` — 3 passed.
- [x] `npm run lint` — passed.
- [x] `npm run typecheck` — passed.
- [x] `npm run build` — passed.
- [x] `uv run mkdocs build --quiet` — passed.
- [x] Preview structural audit, model-ready audit, readiness, publish, and row-level invariant queries — passed.
- [x] Pick'em local export — 8 rows; no totals and no POST.
- [ ] Authenticated Pick'em reconciliation/dry-run — blocked only by missing `CFBD_PREDICTION_TOKEN`.
- [x] `git diff --check` — passed after the final log and plan update.
- [x] Modified-document internal targets resolve and MkDocs passes. The repo-wide link checker remains nonzero only for pre-existing placeholder, localhost, retired external, and historical absolute-file links outside this implementation scope.

## User-Controlled Release Gates

1. Review and commit the dirty worktree in intentionally scoped commits. Suggested first commit: `feat: establish immutable Week 0 preview publication`.
2. On an approved production database backup/maintenance window, point `DATABASE_URL` only at production and run `make migrate-db`; then rerun `make contracts-check` and production preflight before publishing.
3. Configure Vercel production server variables `CFB_PUBLICATION_MODE=market`, `CFB_PUBLICATION_SEASON=2026`, and `CFB_PUBLICATION_WEEKS=0`, deploy a committed revision with Root Directory `web/`, and smoke-test `/` plus `/api/health`. Do not enable `predictions` for the fallback run without a separate approval.
4. Supply `CFBD_PREDICTION_TOKEN`, then reconcile this exact CSV without submission:

   ```bash
   PYTHONPATH=.:src uv run python scripts/pipeline/export_cfbd_pickem.py \
     --year 2026 --week 0 \
     --input-csv artifacts/preview/pickem/cfbd_pickem_2026_w0_2026w0-d990f9b0e495.csv \
     --validate-api --dry-run
   ```

5. Refresh lines and regenerate/reconcile the exact final run near lock. Only after the user approves the displayed game IDs and margins may the same command be rerun with `--submit-api`.

## Precise Next Step

Review the implementation diff and decide the intended commit boundaries. The safest first operational follow-up is configuring the short-lived Pick'em token and performing the read-only reconciliation above; production remains untouched until separate migration and deployment approval.
