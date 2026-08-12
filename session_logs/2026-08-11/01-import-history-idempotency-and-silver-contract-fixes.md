# Session: Historical Bootstrap — Idempotency & Silver Contract Fixes

## TL;DR
- **Worked On:** Unblocking `make import-history` (Phase 2 historical bootstrap)
- **Completed:** Fixed 6 root causes; pipeline now completes all Bronze imports, all Silver builds, and all 5 team_game builds (2021–2025)
- **Blockers:** `combine_games_2021_2025` step had an int-in-argv bug (fixed, untested in full run); user paused before final validation
- **Next:** Re-run `make import-history` end-to-end; if combine step passes, proceed to temporal matchups and downstream model-ready features

## Changes Made

### This session's fixes
- **`src/cks_picks_cfb/features/situational.py`**: Normalize Silver `venue_id` → `id` before venues lookup so `merge_situational_features` works with the Silver contract
- **`src/cks_picks_cfb/data/history.py`**: `import_historical_object` now probes the catalog for an existing capture *before* opening an ingestion run — makes re-runs idempotent and cuts per-object DB ops from 4 to 1
- **`scripts/pipeline/seed_data_corrections.py`**: Short-circuit if the immutable ref file already exists (idempotent re-runs)
- **`scripts/pipeline/build_history_silver.py`**: Short-circuit if the output ref already exists (idempotent re-runs)
- **`src/cks_picks_cfb/ops/__main__.py`**: Convert season ints to `str()` in `--season` argv construction for combine steps (`subprocess.run` requires str argv)

### Prior session work (also uncommitted, included in this commit)
- Week policy pipeline (`build_schedule_week_policy.py`, `week_policy.py`, `conf/policy/`)
- Legacy market references dataset support
- Silver provider-aware capture lookup (`DATASET_PROVIDERS`)
- Data audit: exact-market audit mode
- Various doc/roadmap updates

## Testing
- [x] `uv run ruff format .` — 161 files unchanged (clean)
- [x] `uv run ruff check .` — all checks passed
- [x] `uv run pytest -q` — 285 passed, 5 pre-existing failures (test_external_ratings.py, unrelated)
- [x] `build_team_game_dataset.py` for 2021 succeeded end-to-end
- [x] `make import-history` completed all Bronze imports + Silver builds + team_game 2021–2025

## Technical Details

### The stale-bytecode red herring
The initial error `KeyError: "['id'] not in index"` was caused by Python loading a **stale `.pyc`** of `byplay.py` that contained `df.set_index(["id", "game_id"])` — code that no longer exists in the source. Clearing `src/cks_picks_cfb/**/__pycache__` resolved this. The `inspect.getsource()` output did not match the file on disk at the same line numbers, confirming the bytecode/source mismatch.

### The Silver contract
Silver plays uses `play_id` (not `id`); Silver venues uses `venue_id` (not `id`). The feature pipeline (`allplays_to_byplay`, `merge_situational_features`) must normalize these. `allplays_to_byplay` already handles `period`→`quarter`, `distance`→`yards_to_first`, `yardline`→`yard_line`. We added `venue_id`→`id` normalization to `merge_situational_features`.

### Neon connection timeouts
The import pipeline processes ~7,000 historical objects. Each opens/closes a Postgres connection. Transient Neon timeouts occurred when many operations ran back-to-back. The idempotency probe (check before ingest) reduced this to a single SELECT per already-imported object, mitigating the issue.

## Notes for Next Session

**Resume at:** Re-run `make import-history` to validate the `combine_games_2021_2025` str(season) fix and push through to completion.

**Context:**
- The `str(season)` fix in `ops/__main__.py:321,334` was applied but NOT validated in a full run (user paused)
- All upstream steps (Bronze import, Silver build, team_game) are now idempotent and fast on re-run
- 5 test failures in `test_external_ratings.py` are pre-existing (path issue, not related to this work)

**Watch out for:**
- After combine_games, the pipeline has `build_temporal_matchups` → `point-in-time` → `regime features` → `model selection` → `baseline predictions` steps that haven't been exercised yet
- The `FutureWarning` about downcasting in `situational.py:212` is cosmetic but should be addressed eventually

**Next steps:**
1. Re-run `make import-history` end-to-end
2. Fix any remaining failures in downstream steps
3. Run `npx nx run-many -t lint typecheck test` for the full monorepo check
4. Consider adding a regression test for the venue_id normalization

**tags:** ["pipeline", "data-platform", "historical-bootstrap", "idempotency", "silver-contract"]
