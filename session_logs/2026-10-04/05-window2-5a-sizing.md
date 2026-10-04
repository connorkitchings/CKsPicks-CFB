# Session: Window 2 Step 5A (sizing) — opened

## TL;DR
- **Worked On:** Opened 5A. Recorded the user's three decisions, froze the group, channel and cause definitions before any historical evidence, and built the non-serving R1 candidate and group-diff module with tests.
- **Outcome:** No historical diff, CFBD request, R2 write or database write has been run. The port reproduces the 2026 investigation (145 changed team-games, rollback and cap counts exactly). The 25% gate has not been evaluated.
- **Plan Contract:** `docs/plans/2026-10-03/04-data-integrity-two-window-implementation.md`, Amendment 2, Appendix A (5A).
- **Approval / Status:** Amendment 2 approved 2026-10-04. The user directed 5A to open on 2026-10-04.
- **Scope note:** the user described 5A as covering "the retrospective replay and best-quote alignment for Weeks 0-5". As contracted, 5A is the scoring-allocation sizing and baseline reproduction; the replay is 6B. The best-quote part is already sized for Weeks 0-5 (known issue 13).

## Decisions (user, 2026-10-04)
1. Grouping: per team-game region.
2. If the 25% gate fails: stop and review, as the contract says. No pre-authorized reduced Window 2.
3. CFBD: compute the diff offline first, report games and request count, fetch only changed games after the user approves.

## Verified this session
- The baseline ledger builder is `build_possession_ledger` (`possession_measurements.py:104`, rollback at :294, final cap at :358). R1 existed only as investigation scratch code (`delta_build_candidate.py`); no R1 code is in `src/` apart from the new module.
- The Preview catalog holds Silver plays, byplay, drives, games, game outcomes, team-game stats and reconciliation for 2015-2019, 2021-2025 and 2026. Production holds plays for 2021-2026 only, so the sizing runs on Preview. No CFBD drive retention exists for 2015-2025 (the only CFBD drive files are 2026 weeks 0-4).
- `CFBD_API_KEY` is present in the environment (value not read).
- The prior 2026 evidence leans against the gate: CFBD drives were clean in 9 of 30 affected team-games and, on clean ones, agreed with the baseline on 36 of 66 differing drives versus 28 for R1 (decision packet items 21 and 26, labelled verified there; not re-derived by me). That is evidence about 2026 weeks 0-4, not a forecast for the historical corpus.

## Built
- `docs/plans/2026-10-03/window2/5a-frozen-definitions.md`: frozen definitions plus the port check.
- `src/cks_picks_cfb/ratings/score_envelope_r1.py`: `apply_r1`, `restoration_jumps`, `align_events`, `changed_groups`, `summarize_groups`. Not wired into serving, ratings or any publisher.
- `tests/test_score_envelope_r1.py`: 10 tests.

## Next (not started)
1. Baseline reproduction of the served artifacts (byte or canonical record hash) for the full served lineage: needs the exact measurement and rating manifest ids from `docs/plans/2026-09-29/v5-repair-2026-source-lock.json` and the repair manifest's per-season Silver refs.
2. Historical baseline-versus-R1 diff for 2015-2019 and 2021-2025 from the pinned Silver byplay and game outcomes (read-only on Preview R2; compute-heavy), plus null-PPA exposure by season, metric and team-game.
3. Report changed groups, games and CFBD request count; wait for the user's go-ahead before any CFBD request.
4. Corroboration, go/no-go, signed sizing receipt (the signing and any R2 publication are user-run).

## Progress (later 2026-10-04)
- **Issue 7 assigned:** user confirmed the reconciliation score comparison (skipped because the team-game data has no points column) belongs to 5B; recorded in Appendix B's ownership table and the issue register.
- **Gate-failure path, restated to avoid drift:** the user's decision is stop and review. A reduced Window 2 (replaying Weeks 0-5 with the corrected Away-line rule without R1) is **not** pre-authorized; it would need a new amendment approved by the user.
- **Served lineage located (verified, read-only):** the historical served measurement run is `possession-v1-measurements-20260921-r9` on Preview R2 (certification `fc26a3d0…`, code `39c395f3…`, 2015-2019 and 2021-2025, 2020 forbidden). Its manifest carries the baseline `scoring_events` ledger (86,937 rows), possessions (316,257), observations (285,952), coverage, population, snapshots, terminal and adjusted history (26,247,274 rows), each with a record hash, plus the repair manifest URI `artifacts/research/data-first-football-v1/repair/v2/runs/repair-v2-20260909T1417Z/repair-manifest.json`. The 2026 live measurement manifests are `possession-v1-measurements-2026w0..w4`, listed in the source lock.
- **Baseline reproduction method:** the existing runner's dry run (no `--apply`) recomputes every output in memory from the pinned Silver inputs and prints each dataset's `records_sha`; those are compared with the manifest's `output_records_sha256`. It was launched against current HEAD, which differs from the served code SHA, so a match shows the current builder reproduces the served baseline, which is what the R1 comparison needs.

## Baseline reproduction, historical lineage (2026-10-04) — verified by me, read-only
- **Method:** the runner `scripts/research/run_data_first_possession_measurements.py` was run without `--apply` against current HEAD with the served repair manifest (`repair-v2-20260909T1417Z`), run id `possession-v1-measurements-5a-baseline-repro`, as-of `2026-09-21T00:00:00Z`. It recomputes every output in memory from the pinned Silver inputs and prints each dataset's `records_sha`. It wrote nothing to R2 or the database (about 15 minutes).
- **Result:** all eight datasets' record hashes equal the served run `possession-v1-measurements-20260921-r9` manifest's `output_records_sha256`, with identical row counts: adjusted history 26,247,274; coverage 160; observations 285,952; population 8,936; possessions 316,257; scoring events 86,937; snapshots 142,960; terminal 8,794. The rebuilt certification SHA equals the served `fc26a3d03416e688dc437ad863653dfac7df6faad51b478a7b94f466c0d870c3`.
- **What that does and does not show:** the current builder code, which differs from the served code SHA `39c395f3…`, reproduces the served historical baseline at canonical-record-hash level, which the contract accepts. Byte-for-byte artifact equality was not compared. The 2026 weekly measurement manifests (`possession-v1-measurements-2026w0..w4`) and the served rating artifacts were **not** reproduced in this step (the 2026 observation frame of 6,880 rows and the Week 5 ratings were reproduced by the October investigation, which I have not re-derived). The contract's 5A baseline requirement is therefore met for the historical lineage only.
- **Added for the diff:** `scripts/analysis/size_r1_vs_baseline.py` (read-only, writes only to `--output-dir`) and a rule that a team-game without a certified final is left unchanged by R1 (the baseline also applies no cap there).
- **CFBD request count, assumption to verify:** CFBD's drives endpoint is queried by year, season type and week (not by game), so the request count is estimated as the number of distinct (season, week, season type) bundles among changed games. This is my recollection of the API shape, not verified here. The sizing script reports that count alongside the all-corpus count and the changed-game count.
