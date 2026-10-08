# Session: Stage 1 implementation log (corrected Week 5 data finalization)

## TL;DR
- **Worked On:** Task 0 (read-only verification of the contract's assumptions).
- **Outcome:** Assumptions checked; contract Amendment 1 records four corrections (no new namespace needed; full Week-4-binding list; lock builder moved before Task 4; `prepare-week` step list). No code, data or database change.
- **Plan Contract:** [Stage 1 contract](../../docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md)
- **Approval / Status:** Approved; In progress (Task 0 done). Task 1 and Task 4 write to Preview and need the user's explicit go-ahead.
- **Blockers:** None.
- **Next:** Tasks 2, 3, 3B are local code with tests and can start without a go-ahead; Task 1 (Preview ingest) waits for it.

## Task 0 evidence
- Namespaces: `rebuild/plan.py:22` `RUN_NAMESPACES`; `rebuild/targets.py:12-17,142-181` allow-list, `FORBIDDEN_PREFIXES`, special case for `rebuild/6b/`.
- Week-4 bindings: `recon_foundation.py:118`, `recon_markets.py:283`, `recon_grades.py:232`, `states_2026.py:249-264`, `silver_2026.py:1,204`, `pin_6a_silver_parents.py:64-110`, `run_data_first_repair_v2.py:99` (+ `:578` matching loop), `tests/test_data_first_2026_extension.py:531`.
- 2026 Silver pins: `conf/rebuild/silver_2026_parents_v1.json` (parents `plays eda5263c…` 38,401 rows, `games 31a337df…`, `teams 590e9865…`, `team_game_stats ccf56d58…` 430 rows; outcomes `d9a37cf4…`; legacy byplay `443019a9…`).
- `prepare-week`: `src/cks_picks_cfb/ops/__main__.py:1727-1935` (see contract Amendment 1).
- Unverified, to be settled in Task 1: whether re-ingesting Weeks 0-4 reproduces the pinned `plays` content exactly.

## Files Modified
- `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md` (Amendment 1)
- This log.

## Validation
- [x] Read-only commands only.
- [ ] `git diff --check` and docs build at commit time.

## Handoff Notes
- **Resume at:** Task 2 (approved input set `w5` design) and Task 3 (week-parameterize the corrected rebuild) as local work; ask for the Preview go-ahead before Task 1.
- **Watch out for:** Weeks 0-4 byte-parity gates; every Preview write needs a go-ahead; commit and push in batches.

**tags:** ["data", "stage1", "task0", "corrected-lineage"]

## Update: Task 1 started; work order changed (contract Amendment 2)
- **Task 1 running** (user go-ahead given): `ops prepare-week --year 2026 --week 6 --as-of 2026-10-05T00:00:00Z --environment preview --pipeline-run-id stage1-w5-ingest-20261007`, started 19:06:31Z through `with_preview_env.sh`, log in the session scratchpad. The `--as-of` is an event-time cutoff chosen after Week 5's certified finals (scored 2026-10-04 15:04Z; last kickoff plus the 6-hour availability buffer) and before Week 6's first game (2026-10-07T00:00Z), so Weeks 0-5 are complete and Troy is excluded. Stop condition stays: any Weeks 0-4 row change halts work.
- **Findings** (details in the contract's Amendment 2): core deliverables do not need Week 5 plays; no code builds the team-stats or matchup release payloads; the v2 controller rejects changed `source_versions` (`v5_batch_selection_v2.py:231-236`), which would block any corrected release.
- **Next:** Group A payload builders and verifier (local code and read-only reads of the published 6A/6B run) while the ingest finishes; then the Weeks 0-4 stability comparison.

## Update: Task 1 result, stop condition triggered; Group A done
- **Task 1 (19:06:31Z-19:18:24Z):** raw ingest and four Silver builds completed; the run then failed at `build_current_team_game` with `Blocking source conflicts for games: [401871090]` (Troy, a Week 6 game completed after the as-of label). New immutable Silver versions exist (`games ddccd30e…`, `game_outcomes e3e4cfab…`, `plays 46a62d34…`, `team_game_stats 4701e2f3…`); nothing previously pinned was changed.
- **Weeks 0-4 stability gate FAILED, work halted as instructed:** 71 rows in game 401856660 (Week 1) differ from the pinned `plays` (70 `ppa` values, one drive re-sequenced); Week 1's capture changed, the other weeks' did not. Options and recommendation in the contract's Amendment 4. Tasks 2-4 are blocked on the user's decision.
- **Group A (done, local):** controller provenance amendment (Contract 04 Amendment 6, five failing-then-passing tests), `release_payloads.py` (8 tests, incl. acceptance by the real controller validation), builder and verifier scripts; the corrected as-of 1-5 team-stats payload verifies and reproduces 6A Task 4's comparison (1,328 value + 263 rank-only, EPA/PPA only).
- **Finding:** Task 7 is a build task, not a copy (contract Amendment 5).
- **Validation:** ruff clean; `tests/test_release_payloads.py` (8) and `tests/test_v5_batch_selection_v2.py` (10 + 2 DB tests skipped locally) pass.
- **Next (after the user's decision):** if A, the capture-selecting Silver build path; then Tasks 2-4.

## Update: decisions applied; tools built while the re-run ingests
- **User decisions:** Option B (adopt the revised CFBD data, re-derive Weeks 0-5), Troy rule (exclude games after the cutoff), controller fix committed standalone (`e54a2e37`, three files, staged Week 6 files left alone).
- **Built (all local, tested, lint clean):** `exclude_games_after_cutoff` (6 tests) used by `build_team_game_dataset.py` and `silver_2026.py`; `rebuild/lock_extension.py` plus `extend_rebuild_source_lock.py` (7 tests); `pin_2026_from_versions` (3 tests). Related suites: 86 passed, 2 DB tests skipped.
- **Running:** `prepare-week` r2 (`stage1-w5-ingest-20261007-r2`) started 19:27:22Z; captures are content-addressed so unchanged weeks are reused.
- **Next:** when it finishes, confirm Weeks 0-4 differ from the pinned data only in game 401856660; generate the Week 5 pin file and extended lock; generate `conf/rebuild/6a_w5_v1.yaml`; preflight the new plan (stop and report on any gate); then the build (hours).
