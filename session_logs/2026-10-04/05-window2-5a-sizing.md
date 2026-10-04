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

## Offline sizing completed (2026-10-04, user away; no approval needed because nothing external was touched)
The user stepped away and asked me to do what I could without another approval. I kept the one boundary the user set earlier: **no CFBD request** until the counts are reviewed. I also made no R2 write, database write, production change or git operation.
- **Historical diff:** 3,193 allocation groups in 2,324 of 8,936 games across 2015-2019 and 2021-2025 (baseline 86,937 scoring events, R1 82,416, 126 team-games left unresolved). 85.4% attribution-only, 13.0% points recovery (414 groups, +7,198 points), 1.6% reduction. Primary cause: dip_restore 79.5%, incomplete_stream 9.3%. 2021-2025 change far more groups per season than 2015-2019 (414-621 versus 93-185); not investigated.
- **Request count (exact):** 153 (season, season type, week) bundles for changed games, 162 for the whole corpus; all 8,936 games matched the repair-pinned `fbs_involved_games` (8,521 regular, 415 postseason; 88 changed games are postseason). My first count (143 and 152) omitted the season type and was wrong; the first bundle check also used the wrong Silver games version (7,377 games, regular season only) before I switched to the repair-pinned dataset.
- **Null PPA exposure:** 1,953 of 1,123,065 eligible scrimmage plays (0.17%) have original-null PPA, withholding `eligible_epa` in 1,203 of 17,805 team-games (6.8%); pass 537, rush 727, early-down 889; 0 unmatched plays.
- **2026:** 132 groups in 119 team-games, weeks 0-4 only (Silver byplay `443019a9` does not yet include Week 5 plays).
- **Baseline reproduction completed:** historical and 2026 measurement record hashes match; served ratings are byte-identical (see the report, section 1).
- **Report:** `docs/plans/2026-10-03/window2/5a-sizing-report.md` (draft, unsigned), data in `5a-data/`. The gate has not been evaluated: it needs CFBD drives.
- **Things I did not do:** quarter-line-score pre-screen (events carry no quarter, so it would need a new join; it is not part of the frozen gate), any CFBD request, signing or publishing a receipt.
- **Errors made and fixed in this stretch:** the sizing script's first version crashed building finals (population has no score columns); the exposure script first referenced the wrong mask name after formatting; neither produced a wrong number that reached a report.

## CFBD fetch and corroboration (2026-10-04; user approved all 162 bundles)
- **Fetch:** 162 of 162 bundles, HTTP 200 throughout, 282,062 drive rows, no empty bundle, SHA-256 verified for every file, 162 requests used (about 29,800 of 30,000 remain). Evidence kept with request URL, capture time and hash; the API key is in no stored file (checked). Raw files retained locally and git-ignored at `artifacts/research/window2_5a_cfbd_drives/` (149 MB); manifest committed under `5a-data/`. **Retention in R2:** approved by the user after the gate result and done: 162 objects plus a checksum manifest under Preview `raw/cfbd/drives/`, each read back and hash-checked; a second run found all 162 identical (`scripts/data/upload_cfbd_drives_5a.py`).
- **First corroboration run: 0 corroborated, 23 usable games.** Two checks were implemented wrongly (quarter boundaries only observable at halftime; strict set equality against ledger possessions that include return-only rows). Fixed and documented as a labelled post-hoc amendment to the frozen definitions; the first result is kept as superseded.
- **Gate result: PASS, 1,416 of 3,193 groups (44.4%); 799 needed.** By season 31% (2025) to 57% (2024). Sensitivity: 47.6% without check 2, 48.8% with only checks 3 and 4, 60.3% with no usability filter (not valid), 0% with strict set equality (mechanically impossible).
- **What the pass rests on:** 1,408 of the 1,416 corroborated groups are attribution-only. Of 414 points-recovery groups only 8 corroborate (104 of 7,198 recovered points, 1.4%); 402 of them are in games whose drives are unusable, and even if usable only 72 would corroborate (310 would match neither). Final-cap (90) and point-reduction (52) groups: 0 corroborated. 1,718 groups (54%) are in unusable games.
- **Method validated against the October investigation:** my pipeline reproduces its 2026 drive-level result exactly (66 differing drives on clean team-games: baseline 36, R1 28, neither 2). The historical result is the opposite (usable games: R1 1,415, baseline 9) and agreement with R1 declines over time (about 90% in 2015-2017 to 62% in 2025). I have not explained why; a plausible but untested reading is that recent seasons' score dips more often reflect real reversals.
- **Not decided here:** this is a gate result, not an admission. R1 groups are admitted one by one at 5C; 5B and 5C have not started.
