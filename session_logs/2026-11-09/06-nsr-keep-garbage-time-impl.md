# Session: Net success rate includes overtime (implementation)

> **Amendment 1 (rework):** after the first implementation the owner narrowed the scope to **overtime only**. An investigation (scripts in the session scratchpad, `recompute_nsr.py` and `recompute_ot.py`) showed our data is sound and that keeping garbage time tracks Fleming's ordering worse (rank agreement 0.952 kept, 0.966 dropped), so garbage time stays dropped. Columns are now `off_success_ot_n` and `off_success_ot_sum`; the filter keyword is `keep_overtime`. Where the text below still says "garbage time and overtime kept" or `off_success_all_*`, it describes the superseded first implementation. Week 10 has two overtime games: Buffalo 34-31 Miami (OH) (-0.059 old, -0.057 new) and Massachusetts 31-30 Ball State (+0.101 old, +0.092 new); every other game is unchanged.

## TL;DR

- **Worked On:** Phase 1 of the contract: builder columns, migration, web wiring, chart copy, tests, docs and a read-only Week 10 recompute.
- **Outcome:** `team_game_stats` gains nullable `off_success_all_n` and `off_success_all_sum` (scrimmage plays with garbage time and overtime kept); `netSuccessBars` reads them; every existing column is unchanged. The Week 10 recompute shows the change moves the blowout bars toward Fleming's but does not reproduce them.
- **Plan Contract:** [`docs/plans/2026-11-09/nsr-include-overtime.md`](../../docs/plans/2026-11-09/nsr-include-overtime.md)
- **Approval / Status:** Approved (owner decision 2026-11-09). Phase 2 (rebase on PR #26, prepare and Preview release) not started.
- **Blockers:** None for phase 1. Migration `0029` is written, not run on any database.
- **Next:** Merge PR #26, rebase, run `0029` on Preview, prepare and release to Preview per the weekly runbook, then check parity (old columns identical, only the two new ones added) and the chart on a local Preview server.

**tags:** ["charts", "net-success-rate", "migration", "garbage-time"]

## Context and Decisions

- `scrimmage_play_mask` and `eligible_play` gained a keyword-only `keep_garbage_and_overtime=False`; the default path is byte-for-byte the old logic. With the flag on, the garbage-time rule is skipped and a valid overtime period passes; an unknown period still fails.
- Only offense-side columns were added. The reconciliation mirror check covers `STAT_FIELDS` only and no contract requires defense twins.
- Columns are nullable and added with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` on both `team_game_stats` and `season_release_team_game_stats` (no new projection set, so retained releases keep their recorded set). Retained releases read back NULL; their Net success rate games are then listed "success rate unavailable" rather than silently falling back to regulation counts under copy that says garbage time is included.
- Staging requires the payload columns to equal the database columns exactly, so `0029` must be applied to a database before a release built from this code is staged there.
- `GAME_STATS_SPEC` moved from `web/src/lib/chart-queries.ts` to `web/src/lib/row-guard.ts` as `TEAM_GAME_STATS_SPEC` so it can be unit tested.

## Work Completed

- Builder, play filter, projection integer columns, migration `0029`, `contracts/schema.sql` (verbatim append, as its snapshot test requires), `contracts/schema.ts` and `web/src/lib/schema.ts`.
- Web: loader selects and guards the columns, `netSuccessBars` uses them, footnote copy says garbage time and overtime are included for this chart only.
- Tests: builder (`tests/test_team_game_stats_all_plays.py`), projection column parity, Postgres release templates and snapshot tail, verification fixtures, `netSuccessBars`, row guard, chart config copy, e2e fixtures.
- Docs: methodology, decision log, `AGENTS.md`, `.agent/CONTEXT.md`, `.codex/MAP.md` migration number. `measurement_catalog.md` does not list these columns and is unchanged.

## Verification (Week 10, read-only, active Preview release inputs)

Recomputed from `revision_manifest_w11_v1.json` `inputs.byplay` (sha256-checked) with the new builder logic. Old values reproduce the chart's current values exactly.

| Game | Old chart | New (garbage and overtime kept) | Garbage-time only | Overtime only | Fleming (approx.) |
| --- | --- | --- | --- | --- | --- |
| UGA 42-7 Ole Miss | +0.160 | +0.163 | +0.163 | +0.160 | +0.465 |
| TLSA 60-10 Tulane | +0.467 | +0.260 | +0.260 | +0.467 | +0.38 |
| OKST 66-28 Kansas State | +0.337 | +0.247 | +0.247 | +0.337 | +0.405 |
| DUKE 41-3 NC State | +0.131 | +0.168 | +0.168 | +0.131 | +0.21 |
| CMU 35-7 Eastern Michigan | +0.294 | +0.076 | +0.076 | +0.294 | n/a |
| OHIO 28-20 Akron | -0.148 | -0.148 | -0.148 | -0.148 | -0.135 |
| SJSU 30-19 Northern Illinois | -0.123 | -0.123 | -0.123 | -0.123 | -0.11 |

- Dropping the filters separately: the garbage-time rule accounts for the entire change in every game; none of these seven games has an overtime play, so the overtime rule changes nothing here.
- Tulsa and Oklahoma State move away from Fleming (down), Duke and Georgia move slightly toward him, Ohio and San Jose State agree. The UGA gap (+0.163 against his +0.465) is not explained by garbage time; some other definition difference remains (for example play population or the success definition).

## Files Modified

- `src/cks_picks_cfb/data/play_filters.py`, `src/cks_picks_cfb/charts/team_game_stats.py`, `src/cks_picks_cfb/season/projection_charts.py`
- `contracts/migrations/0029_team_game_success_all.sql`, `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`
- `web/src/lib/charts.ts`, `chart-queries.ts`, `row-guard.ts`, `chart-config.ts`, tests and `web/src/test/fixtures/charts.ts`
- `tests/test_team_game_stats_all_plays.py`, `tests/test_season_projection_charts.py`, `tests/test_season_release_postgres.py`, `tests/test_season_verification.py`
- `docs/modeling/team_charts_methodology.md`, `docs/decisions/decision_log.md`, `AGENTS.md`, `.agent/CONTEXT.md`, `.codex/MAP.md`

## Validation

- [x] `make check`
- [x] `make web-e2e`
- [x] `git diff --check`

## Amendments and Blockers

- None. Deviation from the contract wording: the row guard spec was moved into `row-guard.ts` (testability) and no defense twins were added.

## Handoff Notes

- **Resume at:** Phase 2 after PR #26 merges.
- **Watch out for:** a web deploy before a release carrying the new columns is active leaves the Net success rate chart empty ("success rate unavailable") on Production; run `0029` and release first.
