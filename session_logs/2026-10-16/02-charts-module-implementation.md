# Session: Charts module implementation

## TL;DR

- **Worked On:** Ordered tasks 1-7 of the Charts module contract: metric and adjustment module, release compatibility, migration 0026 and projection wiring, `team_chart_reconciliation`, the web Charts page, Playwright coverage and docs.
- **Outcome:** Tasks 1-7 implemented locally on `connorkitchings/charts-module` and reviewed; nothing committed or pushed, migration 0026 not applied to any real database, task 8 pending.
- **Plan Contract:** [`docs/plans/2026-10-16/01-charts-module.md`](../../docs/plans/2026-10-16/01-charts-module.md)
- **Approval / Status:** Contract approved by the owner on 2026-10-16; implementation awaiting owner review and commit. Ten safe amendments (the tenth is the closeout review) are recorded in the contract.
- **Blockers:** None for tasks 1-7. Task 8 (Preview then Production rehearsal) is owner-gated.
- **Next:** Owner review and commit; then the rehearsal checklist below (task 8 stays pending).

**tags:** ["charts", "release-pipeline", "web", "verification"]

## Context and Decisions

- Baseline `dev` at `a08bf6f3`. Isolation: the shared adjuster, V5 measurements, ratings, forecasts and the existing projection builders are unchanged; a golden-digest test proves model frames and `core_v1` payload bytes are identical to the pre-change baseline.
- Venue WLS uses row-wise `sqrt(w)` scaling of `X` and `y` only; one `RCOND` policy; identification by the rank condition alone.
- Projection sets: `core_v1` (retained releases, read back by their recorded set) and `charts_v1` (the only staging set).

## Work Completed

- `src/cks_picks_cfb/charts/` (roster, team_game_stats, adjusted_epa, reconciliation) and `season/projection_charts.py`.
- `projection_common` sets and `recognized_projection_set`; `release.py` recorded-set readback, `charts_v1`-only staging, chart scope check; `verification.py` `team_chart_reconciliation`.
- Migration 0026 with live and release tables; `schema.sql`, `schema.ts`, `web/src/lib/schema.ts`.
- Web: registry split, `chartsAvailable`, chart CTEs, `getChartsDb`, `chart-queries.ts`, `charts.ts`, components, `/charts`, nav, `WeekNav` `labelMode`, team metadata (refreshed from CFBD with `--metadata-only`), fixtures.
- Tests: Python (module, reconciliation negatives, builders, isolation, release unit, Postgres), web unit and Playwright.
- Docs: methodology page, measurement catalog entries, runbook note, plans index, check count 23.

## Files Modified

See `git status` in the worktree; new directories are `src/cks_picks_cfb/charts/`, `web/src/app/charts/`, `web/src/components/charts/`.

## Validation

- [x] `PYTHONPATH=src:. uv run pytest tests/` full suite: exit 0, 3300 passed, 33 skipped (none of the chart tests); closeout-fix suites re-run: 405 passed
- [x] `make contracts-check`, `make quality-check`, `uv run --extra dev ruff check .`, `git diff --check`, `uv run --extra dev mkdocs build --strict`
- [x] `web/`: `npm run lint` (one existing warning in `SlateView.tsx`), `npm run typecheck`, `npm run test:publication`, `npm run test:ui`, `npm run build`
- [ ] Preview rehearsal and cumulative spot-check against Ratings/matchup values (task 8, owner-gated)

## Amendments and Blockers

- Ten safe amendments, listed in the contract's "Amendments" section (the tenth records the closeout review).

## Handoff Notes

- **Resume at:** Owner review and commit, then task 8.
- **Closeout:** five-lens review done, blocking-free; fixes and deferred items in contract amendment 10. Isolation golden re-derived from pristine `a08bf6f3`: identical. Pinned `teams` parquet (R2) not inspected: verify its `conference` column before the next prepare.
- **Watch out for:** Once merged, staging requires `charts_v1`, so 0026 must reach Preview and Production before the next staged release. The pinned `teams` input must carry `conference`.

## Read-only Preview preflight (2026-10-16)

Run with `zsh scripts/ops/with_preview_env.sh` and read-only database sessions; no migration, ingest, re-pin or activation. No secret values were printed.

- **Database identity:** the pipeline (`cks_preview_pipeline`) and migrator (`cks_preview_migrator`) URLs resolve to the same host and database (`ep-steep-feather-atzstbh2.c-9.us-east-1.aws.neon.tech/neondb`), both sessions `session_user = current_user`, read-only on. The database holds only `preview` releases (1 active, 2 superseded) and the roles `cks_preview_*`, `cks_pipeline`, `cks_web`; it contains no production release.
- **Migration state:** latest recorded migration is `0025_season_releases.sql`; 0026 is pending. `season_release_team_season_roster`, `season_release_team_game_stats`, `season_release_team_adjusted_epa` and the three live chart tables are all absent. Applying the migration runner would apply only 0026.
- **Active Preview release:** `preview-season-2026-d0272a48d3a0252fd4196db3`, Week 7, `core_v1` (18 projection tables). The web resolver will therefore report `chartsAvailable = false` until a `charts_v1` release is activated. The owner policy for `(preview, 2026)` is enabled.
- **Preview owner rollback:** `cks_preview_migrator` holds `UPDATE` on `season_release_policies` and is not a superuser, so it satisfies the code's rollback login rule, but no wrapper or CLI supplies it for Preview (`make season-rollback` and `run_season.py rollback` are Production-only per the runbook). **No verified, explicitly targeted Preview recovery procedure exists; this limitation is recorded and not worked around.**
- **Storage configuration:** `CFB_R2_PREVIEW_{BUCKET,ACCOUNT_ID,ACCESS_KEY,SECRET_KEY,ENDPOINT}` are all set (from the main checkout's `.env`; the worktree has none). The preview bucket is `cks-picks-cfb-preview`; the production bucket name resolves to the same bucket (as the runbook states: separation is by Neon branch).
- **Pinned `teams` input** (`lake/silver/dataset=teams/version=590e986596436aa001ff77b7/data.parquet`): SHA-256 matches the pin (34,672 bytes). Columns include `team`, `classification`, `conference`, `abbreviation`, `color`, `alternate_color`. 138 rows, all `fbs`; **0 FBS rows with a missing conference** (Big Ten 18, ACC 17, SEC 16, Big 12 16, Sun Belt 14, American Athletic 14, Mid-American 13, Mountain West 10, Conference USA 10, Pac-12 8, FBS Independents 2). All 138 team names equal the 138 teams of the pinned schedule, so the roster joins to the play and game data. **No deficiency; no re-pin or replacement provenance is needed.** (Notre Dame is an `FBS Independents` team, handled by name in the Power Four filter.)

## Rehearsal checklist (task 8, pending, owner-gated)

Distinguish three separate things: (A) the database state, (B) the chart-capable web code, and (C) which release is active. Spot-checks must run the committed chart-capable code (B) against the same active release (C) that the database reports.

1. **Commit** the allowlist below (owner). The tree must be clean afterwards.
2. **Re-check identity and migration state** (read-only; step 3 of the preflight above): same host and database, latest migration `0025`, active release `preview-season-2026-d0272a48...`.
3. **(A) Apply migration 0026 to Preview only** (owner/migrator; applies only 0026): `zsh scripts/ops/with_preview_env.sh uv run python scripts/pipeline/migrate_db.py --database-env DATABASE_URL`. Verify the 3 live and 3 `season_release_*` chart tables exist, `cks_web` has `SELECT` and `cks_pipeline` has `SELECT, INSERT` only on the release copies, and the live copies are owner-only. The active release is unchanged.
4. **(B) Run the committed chart-capable web code against Preview.** Vercel deploys only `main` and reads Production, so the documented way is `zsh scripts/ops/run_web_local.sh preview` from the committed branch (reads Preview through the pipeline login). Verify against the still-active `core_v1` release:
   - Picks, Results, Ratings and Performance resolve release `d0272a48...` and show its Week 7 data;
   - `/charts` shows "Charts arrive with the next weekly release" (`chartsAvailable = false`);
   - nothing errors and no chart query touches live tables.
5. **Prepare the next weekly candidate** from the clean committed tree per the runbook (`make season-revision`, commit the manifest, `make season-prepare WEEK=<N> AS_OF=<PRE_WEEK_CUTOFF>`). Confirm 23 passing verification checks including `team_chart_reconciliation`, a non-empty `team_adjusted_epa` when the active week is 3 or later, and that the candidate's `projection_checks` has the 21 `charts_v1` tables. Commit nothing between prepare and release.
6. **(C) Stage and activate in Preview:** `make season-release ENV=preview RELEASE_ID=... PROJECTION_SHA=... EXPECTED_PREVIOUS=preview-season-2026-d0272a48d3a0252fd4196db3`. Read back the new active release id.
7. **Spot-checks with (B) on release (C):** start the local web as in step 4 and confirm it resolves the new release id.
   - `/charts` renders all three charts with "Through Week N" labels and the net-success bars from Week 0.
   - Compare 3 to 5 teams' cumulative success rate and EPA/play with the Ratings and matchup pages **for the same week and the same active release**. These existing pages must show the new release's values: a new weekly release can legitimately change displayed numbers, so verify correct release resolution (same release id, same as-of week) and expected behavior, not equality with Week 7 values.
   - Check a one-role or no-game team under "Not plotted", the conference filter and search, a PNG export (2000x1125 for scatters), and the `/api/health` release identity.
8. **Recovery (Preview).** There is no supported Preview rollback. If the new release is wrong, do not improvise a wrapper: leave Preview as is (it is not public), fix the cause, then prepare and release a new candidate (a superseded or already-activated release cannot be re-activated by the pipeline). If migration 0026 is the problem, stop before step 5; it is additive and the active `core_v1` release is unaffected.
9. **Production** (separate owner decision, after Preview passes): apply 0026 to Production first, deploy the web code via `main`, then the Production release with the independent Preview rehearsal proof. Production recovery is `make season-rollback` (owner credential, decision reference, explicit approval); it reads back by each release's recorded projection set.

Task 8 stays pending until the owner completes and records these steps.

## Changed-file allowlist (62 files + the allowlist itself; regenerated from the worktree with `git status --porcelain -uall`, caches and test output excluded)

The same list is in `session_logs/2026-10-16/02-charts-module-commit-allowlist.txt` (usable with `git add --pathspec-from-file`).

```
.agent/CONTEXT.md
contracts/migrations/0026_team_chart_tables.sql
contracts/schema.sql
contracts/schema.ts
docs/modeling/measurement_catalog.md
docs/modeling/team_charts_methodology.md
docs/ops/weekly_runbook.md
docs/plans/2026-10-16/01-charts-module.md
docs/plans/index.md
mkdocs.yml
pyproject.toml
session_logs/2026-10-16/01-charts-module-planning.md
session_logs/2026-10-16/02-charts-module-commit-allowlist.txt
session_logs/2026-10-16/02-charts-module-implementation.md
src/cks_picks_cfb/charts/__init__.py
src/cks_picks_cfb/charts/adjusted_epa.py
src/cks_picks_cfb/charts/reconciliation.py
src/cks_picks_cfb/charts/roster.py
src/cks_picks_cfb/charts/team_game_stats.py
src/cks_picks_cfb/season/projection.py
src/cks_picks_cfb/season/projection_charts.py
src/cks_picks_cfb/season/projection_common.py
src/cks_picks_cfb/season/release.py
src/cks_picks_cfb/season/verification.py
tests/isolation_digests.py
tests/isolation_golden.json
tests/season_fixtures.py
tests/test_chart_reconciliation.py
tests/test_charts_module.py
tests/test_season_prepare.py
tests/test_season_projection_charts.py
tests/test_season_projection_common.py
tests/test_season_release.py
tests/test_season_release_postgres.py
tests/test_season_verification.py
uv.lock
web/e2e/charts.spec.ts
web/e2e/logos.spec.ts
web/package.json
web/scripts/build-team-logos.mjs
web/scripts/team-logos-lib.mjs
web/scripts/team-logos-lib.test.mjs
web/src/app/charts/page.tsx
web/src/components/SiteNav.tsx
web/src/components/WeekNav.tsx
web/src/components/charts/ChartExportButton.tsx
web/src/components/charts/ChartTable.tsx
web/src/components/charts/ChartsView.tsx
web/src/components/charts/NetSuccessChart.tsx
web/src/components/charts/ScatterChart.tsx
web/src/components/charts/TeamMark.tsx
web/src/components/charts/useChartSelection.ts
web/src/lib/chart-queries.ts
web/src/lib/charts.test.ts
web/src/lib/charts.ts
web/src/lib/schema.ts
web/src/lib/season-release-context.ts
web/src/lib/season-release-query.ts
web/src/lib/season-release.test.ts
web/src/lib/season-release.ts
web/src/lib/team-logos.generated.ts
web/src/lib/team-logos.ts
web/src/test/fixtures/charts.ts
```

Proposed owner commit (run from the worktree on branch `connorkitchings/charts-module`; the owner decides when):

```bash
git add --pathspec-from-file=session_logs/2026-10-16/02-charts-module-commit-allowlist.txt
git status --porcelain=v1 -uall | grep -v '^A ' ; echo "must print nothing above"
git commit -F - <<'MSG'
feat(charts): add weekly team charts with atomic charts_v1 release tables

Releases carry a published FBS roster, team-game success/EPA sums and
venue-neutral, opponent-adjusted EPA/play, verified by full recomputation
(team_chart_reconciliation). Retained core_v1 releases still read back and
roll back by their recorded projection set; new candidates must be charts_v1.
The Charts page reads only release-scoped tables and never falls back to live ones.
MSG
```

## Local Preview smoke test (2026-10-16, committed code `450c622c`)

Run from the clean worktree with `CFB_PUBLICATION_MODE=predictions CFB_PUBLICATION_SEASON=2026 PORT=3200 zsh scripts/ops/run_web_local.sh preview` (settings scoped to the command; no fixture mode, `CFB_UI_TEST_MODE` unset). The server read the Preview database through the pipeline login, read-only use. Nothing was migrated, prepared, activated, pushed or merged, and the server was stopped afterwards.

**Correction of the first run.** The first smoke test ran without publication settings (the worktree has no `web/.env`, which the main checkout sets to `CFB_PUBLICATION_MODE=predictions`, `CFB_PUBLICATION_SEASON=2026`), so it rendered the default `market` view, and I misread `/results`' "Week 6 games" text as belonging to `/`. The rerun below replaces that evidence.

| Check | Result |
| --- | --- |
| `/api/health` | `publication.mode = predictions`; `activeRelease = preview-season-2026-d0272a48d3a0252fd4196db3`, Week 7 (`core_v1`). |
| `/api/health?season=2026&week=7` | `selectedWeek` = run `season-2026-d0272a48d3a0252fd4196db3:w7`, state `published`, model `v5-intended-update-2026-v1`, coverage expected/predicted/lined 59/59/55, `agreesWithCurrentWeek: true`. |
| `/api/health?season=2026&week=6` | run `...:w6`, state `scored`, coverage 58/58/58, `agreesWithCurrentWeek: null` (not the current slate). `selectedWeek` is null without explicit `season` and `week` by design. |
| `/` (Picks) | The Week 7 slate: 59 distinct matchup ids; day groups 2 + 2 + 3 + 3 + 49 = 59 games from Tue Oct 13; "Blitzkrieg Published, run published Oct 13"; per-game model lines ("Model: Delaware by 0.2", model total) beside the market spread and total. |
| `/results` | "completed Week 6 games", 58 of 58 games, week selector Week 0 to Week 6. |
| `/charts` | "Charts arrive with the next weekly release."; no chart rendered (active release is `core_v1`, charts correctly unavailable). |
| Other pages | `/ratings` and `/performance` return 200 with no error state (checked in the first run; unchanged code). |

**Follow-up (separate, not fixed here): scored-week redirect.** `GET /?week=6` returns HTTP 200, not 307. The body shows this is a streamed Next.js redirect, not a missing redirect: it contains `NEXT_REDIRECT;replace;/results?week=6;307` and `<meta id="__next-page-redirect" http-equiv="refresh" content="1;url=/results?week=6"/>`, so browsers are sent to `/results?week=6` after the shell streams. The code path is unchanged by the chart work (`web/src/app/page.tsx`). A client that does not follow meta refresh (a crawler or a plain HTTP check) sees a 200 page rather than a 307. Whether that is acceptable, or whether the redirect should run before streaming starts (for example in middleware or before any suspending work), is a separate decision; a 200 alone does not show that no redirect happens.
