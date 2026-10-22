# Review Weeks 6–7 work, fix pre-Week-8 blockers, streamline to V5-only

- **Status:** Implemented
- **Created:** 2026-10-15
- **Approval source:** Owner approved the plan in chat on 2026-10-15.
- **Implementation log:** session_logs/2026-10-15/02-review-fixes-implementation.md
- **Commit policy:** One proposed commit per phase; the owner performs git operations. No Production writes.

## Goal and acceptance

Confirm the Weeks 6–7 repairs and the Oct 14 atomic-release cutover were done correctly, fix what blocks the Week 8 run (finals Sunday Oct 18), make the documentation true, and reduce the repo to the V5 operational path. V5 Blitzkrieg is the only operational model; research code stays; V4 is documented, not operated. Package modularity is a later session.

Phase 1 ships alone and is a hard gate: phases 2 and 3 start only after the Phase 1 commit. Phase 1 + 2 is a complete outcome for Week 8. Phase 3 is deferrable.

## Review findings (read-only)

Done correctly: Production and Preview serve one atomic release; `docs/status.md` week table and scoreboard match the Stage 4 log (329 games, spread 166-157-6, total 163-164-1); release tests cover stage/activate/rollback, environment refusal and Preview-proof requirements; no code hardcodes Week 7; venues fix complete in both environments; CI PR #7 merged and `dev` == `origin/main` (`baf6b1b8`).

Broken before Week 8:

1. Runbook step 1 fails as written: `ingest_week.py --entities plays,...` needs `--request-inventory`; `build_week_market_snapshot.py` only finds captures under ops-controller run IDs; `fetch_odds_api_market_quotes.py` has no env wrapper and defaults to the Production bucket.
2. No documented step produces the revision-manifest inputs (Silver `game_outcomes`, `byplay`, `drives`, `source_reconciliation`, cumulative `market_quotes`). `season_2026_w7_cumulative_v2` came from uncommitted code; session log `2026-10-14/07` cites `reconstruct_next_week.py`, `export_market_quotes.py`, `run_season.py full`, none of which exist in git. The untracked Week 8 manifest still carries Week 7 input hashes.
3. Runbook rollback cannot work: no env wrapper (`run_season.py:119-123`), no owner/migrator credential path (`release.py:780-784`), ambiguous `<release_id>` (folder name unprefixed, database ID environment-prefixed, `release.py:524`).
4. Score reconciliation was weakened in `257c4ad3` from exact per team-game to a season-wide ≥94% rate (`season/inputs.py:289-312`, `season/verification.py:1139-1164`), contradicting "score reconciliation remains mandatory". No boundary test; stale comment at `inputs.py:265`.
5. `web/src/app/api/health/route.ts:52-56` reads legacy `current_week`/`prediction_runs`.
6. Legacy writers (`score_to_db.py:487-491`, `freeze_week.py:155`) can mutate release-served `public.prediction_runs`; `make weekly` still runs legacy `publish-week`.
7. Week 8 prepare cannot run on a dirty tree, and release refuses if a commit lands between prepare and release; the runbook does not warn.

Documentation gaps: `weekly_runbook.md` is the declared sole authority but is linked from nowhere (and has a broken `../status.md` link); stale content in `docs/status.md`, `AGENTS.md`, `README.md`, `docs/index.md`, `.codex/*`, `.agent/CONTEXT.md`, modeling/data/architecture docs, `decision_log.md`, `Makefile` help; `docs/plans/index.md` has ~10 contracts to Supersede (Stage 7B, repair track, Week 6 display release, Week 7 run sheet, Week 6 closeout, gate waiver, standalone fallback, both Task 4 contracts, two-window plan), three missing (10-10/03, 10-10/04, 10-14/02) and a stale CI row. Contract `2026-10-14/01` is correctly In Progress (acceptance needs one controller weekly update); session log 08 wrongly says "Complete".

## Owner decisions

- Started and reconstructed games stay on the Picks page as they are; document why (no leakage: forecasts use only pre-cutoff observations).
- Grading reconstructed games against the best pre-kickoff quote is intended; document it.
- Score reconciliation must be exact, with declared per-game exceptions.
- Cleanup has wide latitude; research code stays; V4 documented not operated.

## Phase 1 — Fix what blocks the Week 8 run

File ownership (no overlap): A `scripts/pipeline/build_season_revision.py`, `build_week_market_snapshot.py` + tests; B `src/cks_picks_cfb/season/{inputs,verification}.py`, `scripts/pipeline/run_season.py`, `conf/season/2026/score_reconciliation_exceptions.json`, season tests, `tests/test_run_season_cli.py`; C `docs/ops/weekly_runbook.md`, `Makefile`, `scripts/ops/`; D `web/src/app/api/health/route.ts` + test; orchestrator: contract, logs, `docs/status.md`, `docs/plans/index.md`, `conf/season/2026/revision_manifest_w8_v1.json`.

- **1a. Committed revision builder.** `build_season_revision.py --season 2026 --week N --environment preview --as-of ... [--dry-run]` reuses the ops functions behind `fetch-source`/`build-silver` to refresh `games`, `game_outcomes`, `byplay`, `drives`, `source_reconciliation` through the completed week; builds a content-addressed cumulative `market_quotes` Silver version (union of all registered 2026 CFBD betting-lines and Odds API captures, existing normalization, no new parsing); writes `conf/season/2026/revision_manifest_w<N>_v1.json` with real URIs/SHA-256s and truthful `captured_at`, omitting `observations`/`scoring_events` (recomputed by `season/inputs.py:201-240`); reuses catalog registration and `validate_revision`. Captures come from the Preview Neon catalog (`PREVIEW_DATABASE_URL` via `with_preview_env.sh`). Provenance check: run read-only for Week 7 and compare to `season_2026_w7_cumulative_v2` row by row; `game_id`, provider, target, `captured_at`, spread/over-under line and price must match 100%; row/column order and non-key auxiliary metadata differences are allowed but each listed here; any semantic difference is stop-and-report. Also make `build_week_market_snapshot.py` take explicit capture IDs (or have the builder register them).
- **1b. Exact score reconciliation.** Restore per-team-game exact check. Add `conf/season/2026/score_reconciliation_exceptions.json` (`game_id`, `team`, reason) referenced from the revision manifest (hashed into release identity; the sealed model manifest SHA stays fixed). Pattern follows `byplay_v1_collision_exceptions`: listed mismatches pass, unlisted fail, unused exceptions fail (in `verification.py` and prepare). Malformed-reason tags are no longer an automatic bypass. `run_season.py rollback`/`release`: normalize `--release-id` and `--expected-previous-release-id` (accept prefixed as is, prepend environment to bare `season-2026-...`, reject mismatched prefix). Remove the private `_MALFORMED_SCORE_REASONS` import; fix stale comment. Tests: unlisted fails, listed passes, unused fails, prepare/verification agree, three ID-normalization cases. Populate exceptions from a read-only Preview prepare dry run (Weeks 0–7), listing exactly the current non-reconciling team-games.
- **1c. Runbook rewrite.** All data commands under `scripts/ops/with_preview_env.sh`. Step 1: ingest (with `--request-inventory`) → `build_season_revision.py` → commit manifest → prepare from a clean tree. Warnings: no commit between prepare and release; folder `release_id` differs from the prefixed database ID. Rollback via new `scripts/ops/with_production_owner_env.sh` (Keychain pattern of `with_production_pipeline_env.sh`; sets `DATABASE_URL` and `CFB_ARTIFACT_ENV=production`; non-zero exit if entry missing; refuses roles ending `_pipeline`/`_web`; never prints the URL). Keychain service/account name must come from the owner. Correct `--reconstruct-next-week` guidance (only for a week after its pre-week cutoff). Fix `../status.md` link. Add Make targets `season-revision`, `season-prepare`, `season-release`, `season-rollback`; `make weekly`, `publish-week`, `freeze-week`, `close-week` print a "removed — see weekly_runbook.md" error until Phase 3 deletes them.
- **1d. Web health route.** Resolve through `season-release-context.ts`, report active `release_id` and week; legacy fallback only when no release is active (matching `getCurrentWeek`).
- **1e. CLI tests.** `tests/test_run_season_cli.py`: argument parsing, `--initial` vs `--expected-previous-release-id` exclusivity, environment-mismatch refusal, dirty-tree refusal, rollback environment requirement.

Phase 1 verification: pytest, `make contracts-check`, Preview parity check (below), Week 8 revision dry run. Then propose the Phase 1 commit and wait.

## Phase 2 — Make the documentation true

- `docs/status.md`: keep header/product/week table/scoreboard/branches; replace "Release state" and "Open work" with current release, Week 7 finals/grading pending, Week 8 via `run_season.py` as the `2026-10-14/01` acceptance gate, and deferred backlog (EPA replacement, six quality follow-ups, scoring recertification, 2025 matchup backfill, non-monotonic running score); move dated material to `docs/status_history.md`; add session log 08 to "Verified from".
- Plans index and contract headers: apply the lifecycle corrections above; leftover repair obligations are Superseded with a pointer to the backlog; add the three missing contracts; CI contract Merged; rewrite the `2026-10-14/01` row as "Cutover complete; awaiting first controller weekly update + section 4 docs".
- Ops docs: `weekly_runbook.md` is the only ops entry in the mkdocs nav (plus `data_first_capture.md` under Research). Archive `weekly_pipeline.md`, `v5_weekly_operator.md`, `production_runbook.md`, `v5_shadow_runbook.md`, `rating_shadow_operations.md`, `rating_successor_research.md`, `mlflow_mcp.md` to `docs/archive/ops/` with one-line stubs at old paths; first move environment/role facts (Neon branches, `cks_prod_pipeline`, Vercel) into an "Environments" runbook section. Move `validation.md` to `docs/data/`.
- Modeling/data docs: `v5_status.md`, `record_methodology.md` (season_verification_v2 checks replace the leakage-audit gate; early Week 6 games graded; per-game/target market precedence; best-pre-kickoff-quote grading; started/reconstructed games display unlabeled because forecasts use only pre-cutoff observations), `known_issues.md`, `data_platform_2026.md` (add `season_releases`), `decision_log.md` (Oct 14 cutover, Picks display, best-quote grading, exact reconciliation).
- Write `docs/modeling/v4_retrospective.md` (methodology, windows, features, results, 2025 holdout, last git SHA with V4 code) before Phase 3 removes V4.
- Entry points: `AGENTS.md`, `README.md`, `docs/index.md`, `.codex/QUICKSTART.md`, `.codex/MAP.md`, `.agent/CONTEXT.md`, `.agent/skills/CATALOG.md`, `contracts/README.md`, `web/README.md`; delete `.codex/HYDRA.md` and `GEMINI.md`.
- Session logs: append dated "Correction (2026-10-15)" notes to `2026-10-14/07` (cited files/command never existed; actual commits `5a7196d4` and `16656098`; quotes producer is now `build_season_revision.py`) and `2026-10-14/08` ("Complete" is wrong). Do not rewrite original text.

## Phase 3 — Streamline (deferrable)

Rule: delete a module only when nothing in the live path, `scripts/research/`, `scripts/analysis/` or research src packages imports it (import-graph check in scratchpad, not committed). Update `conf/repository/compatibility_v1.yaml` and `Makefile` in the same commit as each group. Record baseline combined coverage (as CI measures it) first; re-measure after each group; stop and report below 60%.

- 3a Safe deletions (local-only strays; `templates/`, `docker/mlops/`, `scripts/archive/`, five unreferenced scripts, `conf/venue_supplement_*`, unused web components, `model-accuracy.json`; untrack `.neon`; pytest `testpaths`/`norecursedirs`).
- 3b 6A/6B rebuild and one-off cutover tooling (`src/cks_picks_cfb/rebuild/`, `conf/rebuild/`, `rebuild-6b.yml`, one-off scripts, invalid-lock/backup artifacts, their tests).
- 3c Legacy V5 publication path (move `assert_v5_database_environment` into `season/`; lazy `ops/__init__`; remove `v5_*`, publish/freeze/close/replay commands and writers, `inference/`, their Make targets and tests). Keep the web legacy read fallback.
- 3d V4 operational stack (train, V4 models/features, Hydra `conf/` groups, MLflow utils, broken weekly-bets scripts; drop unused dependencies after grep confirms none are imported; `uv lock`).
- 3e Nx removal (CI uses `npm --prefix web run ...`; delete root `package.json`, lockfile, `nx.json`, `project.json`, `web/project.json`; update `AGENTS.md`).

Kept: `scripts/research/`, `scripts/analysis/`, `ratings_lab/`, `audit/`, research `forecast/` and `ratings/`, `conf/research/`, `data_first_*`, the `data-first-pregame-capture` workflow (ask the owner whether its variable is on), web legacy query fallback, `contracts/`, `docs/plans/`, `session_logs/`.

## Verification

After each phase: `uv run pytest tests -q -n 4` plus database suite on disposable Postgres; `uv run ruff format --check .`, `uv run ruff check .`; `make contracts-check`, `make quality-check`; `npm --prefix web run lint typecheck test:publication build`; `uv run mkdocs build --strict`; `git diff --check`. Serving parity (read-only, Preview R2, with owner go-ahead): before and after Phases 1b and 3, `run_season.py prepare` with the Week 7 manifest at the original as-of into scratchpad; `serving_projections` business content must equal the active release's after normalizing only embedded provenance identities derived from the revision manifest SHA and code commit; no football values, market selections or grades may be normalized. Compare the normalized payload byte for byte and require equal row counts; raw payload SHA equality is not required because these identities change when the exceptions pin or code commit changes. Week 8: dry run before finals; owner runs the rewritten runbook end to end in Preview after finals (the `2026-10-14/01` acceptance gate); Production activation is an owner decision. `rg` checks that nothing references deleted paths.

## Out of scope

Package modularity; changes to public record or grading policy; Production writes or migrations; moving the 84 MB `docs/plans` evidence out of git.

## Provenance-check differences

**Status: resolved with owner-approved differences. The owner confirmed the three Week 2–4 captures are registered in Preview and accepted the rebuilt-quote record change. The real-state Week 7 dry run reproduced the simulated result: 17 captures, 2,187 rows, SHA `83e8d704…`, 99.47% match with no unexplained semantic differences.**

Read-only Week 7 check (2026-10-15): `build_season_revision.py --dry-run` against the Preview catalog and R2, compared with `season_2026_w7_cumulative_v2` (1,205 rows, 2,285 lines), one row per line on `game_id`, provider, target, `captured_at`, line and both prices, totals read from `total`.

- First check, registered captures only: 14 captures, 1,970 rows; 1,840 lines match (80.5% of v2). The gap was v2's Week 2–4 CFBD lines (captures `2ad6474f…`, `0e9b9707…`, `cd851874…`), which are not registered in the Preview catalog although their Bronze files and observation records are intact in Preview R2.
- Second check, those three captures loaded in memory as if registered (nothing written): 17 captures, 2,187 rows, 4,353 lines, content SHA-256 `83e8d704…`; 2,273 lines match (99.47% of v2); no unexplained semantic differences.
- Non-quote inputs: `schedule`, `finals` and cutoffs identical; `byplay`, `drives`, `reconciliation` have identical content SHA-256s and new version IDs (the code commit is part of version identity); `captured_at` is the true last capture time `2026-10-14T14:41:33.551640Z`, not the hand-set `14:42:04Z`.

Expected differences (owner chose "register missing, rebuild"):

- The rebuild adds 1,950 lines from registered captures v2 left out: CFBD `9f1d088b` (Week 0), `53810f3e` (Week 1), `4c4fcd01` and `b09eaaeb` (Week 5), `d61e175e` and `ba941e66` (Week 7), Odds API `e134dd22` (Sept 4), and all 493 rows of Odds API `ed0900ba` (v2 kept 18).
- 118 Week 7 CFBD totals (capture `fc808f83`) are filled from `over_under` by the standard normalizer; v2 had them blank.
- Six Week 6 CFBD quotes (capture `da13ee7e`; games 401871090, 401871051, 401871066) carry their real capture time `2026-10-08T16:19:27.655892Z` instead of v2's backdated `2026-10-06T18:00:00Z`.

Benign differences: row and column order (same 29 columns); the 18 `ed0900ba` rows v2 kept match exactly but lost capture metadata, so their `quote_id`s differ; `season`/`week_y` null in the rebuild for 52 shared quote IDs whose games are not in the engine schedule (version `cf1fcc2f`); `season`/`week_y` float in the rebuild and int in v2.

Grade impact (read-only re-grade of active release `season-2026-d0272a48d3a0252fd4196db3`; v2 quotes reproduce the published grades exactly): 16 of 657 graded rows change their selected quote and 7 change result.

| | Published | With rebuilt quotes |
|---|---|---|
| Spread (W-L-P) | 166-157-6 (−6.091u) | 164-156-6 (−6.949u) |
| Total (W-L-P) | 163-164-1 (−15.818u) | 160-164-1 (−18.545u) |

- Week 2: Odds API Sept 4 FanDuel/DraftKings quotes win best-quote selection on 10 games (401856674, 401856679, 401856682, 401856782, 401856783, 401856788, 401856810, 401858216, 401858443, 401860884). One result flips: 401858443 total, under 55 (win) to over 49.5 at −105 (loss).
- Week 6: 401871090, 401871051 and 401871066 become ungraded for spread and total, because their only quotes were captured after kickoff. Published grades were spread W/W/L and total W/W/L.
- Weeks 0, 1, 3, 4, 5, 7: no change.

Unregistered Preview R2 market files not covered by the owner's approval (all `staged`, no ingestion run, hashes intact): about 25 more CFBD files for 2026 Weeks 0–4 (several duplicates minutes apart; four larger ones captured after kickoffs: `810831d5…`, `ad590b98…`, `e3968d60…`, `e2ad9405…`), three 2025 files that do not belong, and Odds API `0b681dba…` (Sept 30). Registering any of them can move best-quote grades. Not registered pending owner review.

Resolution (2026-10-15): the owner confirmed registration of the three Week 2–4 CFBD captures in Preview and accepted rebuilt quotes, including spread 164-156-6, total 160-164-1 and the three Week 6 games becoming ungraded for both targets. These are approved candidate results pending activation; the published record and active release remain unchanged. No other unregistered market files are approved for registration.

## Phase 1 closeout amendment — 2026-10-15

The owner explicitly authorized the Phase 1 completion plan in chat. The serving-parity criterion above now measures business content while normalizing only the documented manifest/code-derived provenance identities. Retained Week 7 evidence: both payloads contain 54,753 rows; replacing only those provenance strings reproduces the scratch payload byte for byte. Schedule, finals, measurements, features, ratings and grades files are SHA-identical. Raw projection payload SHAs differ (`2534771035f2…` scratch versus `b58af2126ce6…` active), as expected from the embedded identities. This check uses the existing Week 7 quote inputs; the separately approved rebuilt-quote grade changes are documented above.

Leave `conf/season/2026/revision_manifest_w8_v1.json` and `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md` untouched and out of the Phase 1 commit. The stale Week 8 manifest carries Week 7 hashes and must be removed before regeneration after Week 7 finals; the builder refuses to overwrite it. The Week 8 revision dry run remains blocked until the required Week 7 finals/controller inputs exist. Refresh score-reconciliation exceptions before the real Week 8 build. Preview rollback is unsupported; the owner must create the Production owner Keychain credential before using the owner rollback wrapper. Phase 1 closeout stops at the proposed commit; Phases 2 and 3 remain gated on the owner committing Phase 1.


Phase 1 closeout validation: the release/revision-builder PostgreSQL suites and migration tests passed together (120 tests, zero skips) on disposable local clusters; strict MkDocs, contracts validation, the 32-check quality registry and `git diff --check` passed. Prior full Python/web/Ruff results are retained in the implementation log. Phase 1 is ready for the owner commit; this contract remains In Progress because Phases 2 and 3 have not started and Week 8 execution remains pending.


## Phase 2 execution amendment — 2026-10-15

Phase 1 is committed as `2807e087`; the owner confirmed the commit in chat after the agreed Phase 2 handoff. Phase 2 is now In Progress with log `session_logs/2026-10-15/03-phase2-documentation-truth.md`. Phase 3 remains deferred; no runtime, dependency or CI cleanup is included in this documentation phase.

The documentation-authority test contains obsolete assertions for a selected Week 5 run, Week 4 entry-point wording and separate exact-packet publication. Update those assertions to the approved season-release/runbook authority while retaining fixed-mathematics, historical provenance, leakage and six-slate-policy protections. This is a mechanical validation amendment required by the approved documentation changes, with no runtime interface or acceptance relaxation. Prior Phase 1 readiness paragraphs above are dated history; its commit gate is now satisfied.


Phase 2 mechanical scope note: deleting the Hydra guide exposed a current reference in `CLAUDE.md`; replace that one guide reference with the canonical weekly runbook while preserving its `AGENTS.md` redirect. Historical audit/inventory mentions remain as evidence. No Phase 3 runtime/dependency deletion is included.


## Phase 2 closeout — 2026-10-15

Phase 2 documentation is complete locally and ready for the owner commit. The V4 retrospective is written with verified recovery commit `2807e0871c53a659943c5c23e5def888e0be5fbc`; the seven ops runbooks are archived with redirects, validation is moved, entry points and authority tests are current, ten overlapping contracts are Superseded with backlog pointers, and dated log corrections are appended. Section 4 documentation in the season-operations contract is delivered locally; that contract remains In Progress until its first controller weekly update. This review contract stays In Progress because Phase 3 remains deferred, not implemented. No runtime/model/dependency/CI cleanup was performed.

Validation: full Python suite 3,227 passed and 33 skipped; expanded serial database suite 147 passed with zero skips in UTC client sessions; web lint/typecheck/publication tests/build, Ruff format/lint, contracts, the 32-check quality registry, strict MkDocs and diff checks pass. The first expanded database run exposed a preexisting non-UTC timestamp serialization limitation in the legacy publisher (146 passed, 1 failed); fresh cluster `PGTZ=UTC` retry matches CI and passes. The implementation log records the limitation and environment correction without changing legacy runtime code. The two untracked exclusions remain unchanged; Week 8 revision dry run is still blocked by Week 7 finals/controller inputs and was not claimed as passed.

Proposed Phase 2 commit: `docs(season): consolidate V5 operations and preserve V4 history`. No commit, staging, push or stash was performed. Resume with owner review/commit; Phase 3 requires its import-graph and combined-coverage checks before any deletion.

## 2026-10-22 Phase 3 closure

Phase 3 was carried out by [2026-10-22/01-repo-consolidation](../2026-10-22/01-repo-consolidation.md) and merged into `dev` on 2026-10-22, which completes this contract. Caveats: the serving-parity check from this plan was not run (see the consolidation session log), and Week 8 Preview execution is tracked by the season-operations contract, not here.
