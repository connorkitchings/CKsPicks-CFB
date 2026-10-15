# 2026-10-15 — Review fixes and V5 streamline implementation

Contract: `docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md`. Worktree branch `worktree-connorkitchings-review-and-v5-streamline`, from `dev` at `baf6b1b8`.

## TODO

- [x] Phase 1a revision builder + market snapshot capture IDs (subagent A)
- [x] Phase 1b exact score reconciliation + release-id normalization (subagent B)
- [x] Phase 1c runbook, Make targets, owner env wrapper (subagent C); owner must create the documented Keychain item
- [x] Phase 1d health route (subagent D)
- [x] Phase 1e CLI tests (subagent B)
- [x] Phase 1 verification and commit proposal (hard gate)
- [ ] Phase 2 docs
- [ ] Phase 3 streamline

## Log

- 1d done: health route reports the active release; `route.test.ts` (6 tests) added to `test:publication`.
- 1b/1e done (subagent B): exact per-team-game reconciliation shared by prepare and verification; manifest field `score_reconciliation_exceptions {uri, sha256}` bound into the revision manifest SHA; 42 team-games listed (Weeks 0–6, file sha256 `939ec41c…ea8cb`); release-id normalization; 20 CLI tests; 340 season/CLI tests pass.
  - Open: the Week 8 manifest must reference the exceptions file; the list must be refreshed after Week 7 finals land; an older manifest pinned to a previous exceptions sha can no longer be prepared once the file changes.
  - Three of the 42 carry only `score_regression_rollback`; they passed before only because of the 94% rate.
- 1c done (subagent C): runbook rewritten with an Environments section; `with_production_owner_env.sh` added (default Keychain item `ckspicks-cfb/production/owner-url`, account `cks_prod_owner`, both overridable; the item does not exist yet); `make season-revision|season-prepare|season-release|season-rollback` added; `make weekly|publish-week|freeze-week|close-week` now fail with a pointer to the runbook.
  - Open: runbook arguments must match the final `build_season_revision.py` CLI (it needs `--pre-week-cutoff` and `--pipeline-run-id`); the stale untracked w8 manifest blocks the builder's no-overwrite rule; Preview rollback is undocumented; `mkdocs --strict` fails on a pre-existing broken link in `docs/plans/2026-10-08/02-...md`.
- 1a (subagent A): `build_season_revision.py` and `--capture-id` support in `build_week_market_snapshot.py` built; 13 tests pass. Week 7 provenance check FAILED (details in the contract); stopped per plan. Nothing was fetched, uploaded, registered or written. Week 8 dry run is impossible until a controller run covers the Week 7 finals.
  - Runbook must change: the builder now performs the plays/game_stats ingest and needs `--pre-week-cutoff` and a fresh `--pipeline-run-id`.
- Owner chose to register the three Week 2–4 captures and rebuild. The registration write to the Preview catalog was denied by the permission system, so nothing is registered; the worker simulated it in memory. Provenance result 99.47% with only expected differences; re-grading with the rebuilt quotes changes the published record (spread 164-156-6, total 160-164-1; 3 Week 6 games become ungraded). Recorded in the contract.
- Fixed `tests/test_repository_boundaries.py` failure: `compatibility_v1.yaml` listed `publish-week`/`freeze-week`/`close-week` as public Make targets; replaced with the four `season-*` targets.
- Owner confirmed the three Week 2–4 captures are registered in Preview (the earlier failure was a foreign key on `ingestion_run_id`, not a permission denial) and accepted the record change. Real-state Week 7 dry run reproduced the simulation (17 captures, 2,187 rows, SHA `83e8d704…`, 99.47% match).
- Web checks pass: lint (one pre-existing warning), typecheck, `test:publication` (163 pass, 1 skipped), build (after replacing the worker's `node_modules` symlink with `npm ci`).
- Owner asked to pause when the running agents finish (out of usage). In flight at that point: runbook alignment (subagent C), serving parity check (new subagent), full pytest run.
- Remaining Phase 1: parity result, full pytest and database suite, `mkdocs --strict` (pre-existing broken link in `docs/plans/2026-10-08/02-...md`), `docs/status.md` and `docs/plans/index.md` updates, drop the stale w8 manifest and session log 13 decision, then propose the Phase 1 commit. Phases 2 and 3 not started.
- Runbook aligned with the final builder CLI (subagent C): Preview rollback documented as unsupported; stale w8 manifest must be deleted before the real Week 8 build.
- Full pytest passes: 3,222 passed, 33 skipped.
- Serving parity (Week 7 manifest plus the exceptions pin, prepared in a scratch clone at the original as-of, Preview R2 read-only): raw `serving_projections` SHA differs from the active release (`2534771035f2…` vs `b58af2126ce6…`) because the payload embeds identities derived from the manifest SHA and code commit. Substituting only those provenance strings in the active payload reproduces the scratch payload byte for byte; row count 54,753 in both; schedule, finals, measurements, features, ratings and grades files are SHA-identical. Strict byte equality in the contract's wording is therefore not achievable; the content-parity result is the evidence.
- Paused at owner request (out of usage). Not yet done: database suite, `mkdocs --strict` link fix, `docs/status.md` and `docs/plans/index.md` updates, decision on the stale w8 manifest and session log 13, Phase 1 commit proposal.
- Worktree created. Copied the uncommitted runbook edit, Week 8 manifest and session log 13 from the main checkout; they get corrected in Phase 1.


## Phase 1 closeout — 2026-10-15

### TL;DR

- **Worked On:** Remaining Phase 1 database validation and documentation closeout in the existing worktree.
- **Outcome:** Phase 1 is validated and ready for the proposed owner commit. No implementation code changed in this continuation; Phases 2 and 3 have not started.
- **Plan Contract:** `docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md`.
- **Approval / Status:** Owner explicitly requested implementation of the Phase 1 completion plan in chat; overall contract remains In Progress, Phase 1 awaiting owner commit.
- **Blockers:** Week 8 revision dry run awaits Week 7 finals/controller inputs. Production owner Keychain item is absent; Preview rollback is unsupported.
- **Next:** Owner reviews and commits Phase 1; only then may Phase 2 begin.

### Work completed and decisions

- Fixed the repair contract's MkDocs link by retaining the existing out-of-docs session-log path as inline code.
- Amended serving parity to normalize only documented identities derived from the manifest SHA and code commit. Retained evidence is 54,753 byte-identical rows after normalization and SHA-identical schedule, finals, measurements, features, ratings and grades files. This comparison retains the Week 7 quote inputs; the rebuilt quotes have a separately approved grade impact.
- Updated the contract's provenance status and Resolution: the owner confirmed registration of the three Week 2–4 CFBD captures in Preview and accepted rebuilt quotes (spread 164-156-6; total 160-164-1; three Week 6 games ungraded for both targets). Other unregistered captures remain pending owner review. This continuation made no registrations, Preview writes or Production writes.
- Added a narrow Phase 1 readiness/Week 8 prerequisites update to `docs/status.md` and an In Progress row to `docs/plans/index.md`. Active releases and the published scoreboard are unchanged; rebuilt results remain pending activation.
- Preserved the untracked Week 8 manifest and October 14 log 13 byte for byte. This supersedes earlier log notes proposing correction or removal during Phase 1. Both are excluded from the commit. Remove the stale manifest before regenerating it after Week 7 finals and refresh score-reconciliation exceptions before the real build.

### Validation

- [x] `tests/test_season_release_postgres.py`, `tests/test_build_season_revision_postgres.py`, `tests/test_migrations.py` and `tests/test_migration_integration.py`: **120 passed in 20.09s, zero skips**. Ran serially via `uv run --no-sync pytest ... -q -ra`; `TEST_DATABASE_URL` was overwritten with a private Unix-socket connection to a newly created local `phase1_migrations` database, never a hosted database. The release and builder modules used their own disposable clusters. Teardown stopped and removed clusters.
- [x] `uv run --no-sync mkdocs build --strict`: passed. Existing unlisted-nav and `5a-data/` messages are informational.
- [x] `make contracts-check`: passed.
- [x] `make quality-check`: passed, 32 registered checks, no problems.
- [x] `git diff --check`: passed.
- [x] Reused prior validation as authorized: full Python **3,222 passed, 33 skipped**; web lint (one existing warning), typecheck, publication tests (**163 passed, 1 skipped**) and build; Ruff checks recorded in the handoff. No implementation changes in this continuation required rerunning those checks.
- [ ] Week 8 revision dry run: **blocked**, not claimed as passed; requires Week 7 finals/controller inputs.

The default uv cache was sandbox-inaccessible, so checks used `UV_CACHE_DIR=/tmp/ckspicks-phase1-uv-cache` and `--no-sync` (or `UV_NO_SYNC=1` for Make) against the existing worktree environment. The first local `initdb` was blocked by sandbox shared-memory restrictions and cleaned up. The expanded-permission retry succeeded on disposable local PostgreSQL only.

### Files modified in this continuation

- `docs/plans/2026-10-08/02-repair-track-certification-and-closure.md`: session-log reference.
- `docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md`: parity criterion, provenance resolution and closeout amendment.
- `docs/status.md`: narrow Phase 1 readiness and pending candidate note.
- `docs/plans/index.md`: new In Progress contract row.
- `session_logs/2026-10-15/02-review-fixes-implementation.md`: TODO completion and closeout evidence.

### Proposed Phase 1 commit

`fix(season): complete weekly revision and release safeguards`

Include the following explicit allowlist (all inherited Phase 1 changes and additions plus this closeout); do not use broad directory staging or `git add -A`:

```text
Makefile
conf/repository/compatibility_v1.yaml
conf/season/2026/score_reconciliation_exceptions.json
docs/ops/weekly_runbook.md
docs/plans/2026-10-08/02-repair-track-certification-and-closure.md
docs/plans/2026-10-15/01-review-fixes-and-v5-streamline.md
docs/plans/index.md
docs/status.md
scripts/ops/with_production_owner_env.sh
scripts/pipeline/build_season_revision.py
scripts/pipeline/build_week_market_snapshot.py
scripts/pipeline/run_season.py
src/cks_picks_cfb/season/inputs.py
src/cks_picks_cfb/season/manifest.py
src/cks_picks_cfb/season/verification.py
tests/test_build_season_revision.py
tests/test_build_season_revision_postgres.py
tests/test_run_season_cli.py
tests/test_season_prepare.py
web/package.json
web/src/app/api/health/route.ts
web/src/app/api/health/route.test.ts
session_logs/2026-10-15/01-review-and-streamline-planning.md
session_logs/2026-10-15/02-review-fixes-implementation.md
```

Explicitly exclude these untouched, untracked files:

- `conf/season/2026/revision_manifest_w8_v1.json` (SHA-256 `031840cc4fe24ea7bc9a3102df9ea661b8abe7255a4cec203571b70d5ca5dc7b`).
- `session_logs/2026-10-14/13-runbook-script-paths-and-w8-manifest.md` (SHA-256 `df3c8491992b46b692bf9ae906bc9c91c6126b101d590904420a3c9894cdac1e`).

No files were staged and no commit, push or stash was performed. Review the 24-file allowlist and commit on this worktree branch. Phase 2 documentation consolidation and Phase 3 cleanup stay gated on that commit.

### Handoff notes

- **Resume at:** owner Phase 1 commit, then Phase 2 under the existing contract.
- **Watch out for:** after finals on Sunday October 18, regenerate the Week 8 manifest with fresh Week 7 inputs and exceptions; prepare from a clean tree, and do not commit between prepare and release. The first complete controller weekly update in Preview remains the bridge-contract acceptance gate. Production activation remains the owner's separate decision.

**tags:** ["phase1", "season", "validation", "documentation"]
