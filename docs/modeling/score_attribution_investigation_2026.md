# Score-attribution investigation: the quarantined games, one by one

Read-only investigation of the running-score defect behind `missing / unresolved_scoring_attribution`. Contract: [04-score-attribution-investigation](../plans/2026-11-12/04-score-attribution-investigation.md). Per-game data: [`score_attribution_games_2026.json`](evidence/score_attribution_games_2026.json). Regenerate and verify with `uv run python scripts/research/run_score_attribution_investigation.py [--check]`. Nothing here changes a 2026 prediction, grade, release, the score exceptions file, Production or any stored data.

## Answer

- **Every one of the 56 games was read from the raw provider plays.** In all of them the defect is in the CFBD feed: the Bronze plays and the Silver plays are identical row for row (56 of 56 games), so nothing in our Silver build creates or hides a bad score. No ordering (production order, provider play id, wall clock, period and clock) makes the streams monotone.
- **What the defect looks like.** The provider writes the running score on every play row, but only the scoring plays carry a trustworthy value. Ordinary plays, penalties and kickoffs often carry a stale, zero, or later-in-the-game score. In clean team-games 3381 of 3395 score increments sit on a scoring play.
- **Direct repair (rule R4).** Read the score only on scoring plays, fit those values with a monotone fit capped at the game final, and carry the value forward. It resolves 82 of the 86 team-games the builder rejects today (95.3%) and 80 of them reproduce the quarter line scores exactly, an independent check that the cap at the final cannot supply. The prior candidate R1 resolves 61 (70.9%) and 49 match the quarter lines.
- **History.** Applied read-only to 2021-2025, R4 restores 339 team-game offenses (and the same number of opponent defenses) that the stored measurements exclude today. Previously observed team-games are unchanged.

## Data read

- 2026: the Silver `schedule`, `finals` and `byplay` of revision `season-2026-w11-preview-r2` (pinned by checksum in `conf/season/2026/revision_manifest_w11_v2.json`), plus the 11 Bronze CFBD `plays` captures (121,978 rows, one per week 0 to 10) behind the Silver `plays` version `3cff6d233deea2c53e3760f0`. Read-only, checksum verified.
- 2021-2025: the Silver `byplay` and `fbs_involved_games` versions pinned in the persisted ratings-lab corpus, and the corpus's stored ppp observations as the baseline. All five seasons were reachable; none is approximated. Raw Bronze for 2021-2025 was not read (the stored lineage resolves to Silver; Bronze equals Silver in 2026).
- No provider request was made or needed.

## 1. Inventory

The audit ledger holds 44 games (39 partial and 5 whole-game quarantines). The exceptions file holds 54 entries in 49 games, 11 of them not in the ledger. Rebuilding the measurements from the pinned week 0 to 10 plays with the unchanged builder quarantines 53 games today; 1 of those (`401858279`) is in neither list (it is quarantined with no exception). The inventory is the union: **56 games**.

| Week | Partial | Whole game | Exception only (observed) | Games |
|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 1 |
| 1 | 3 | 1 | 0 | 4 |
| 2 | 7 | 2 | 0 | 9 |
| 3 | 5 | 0 | 2 | 7 |
| 4 | 5 | 0 | 1 | 6 |
| 5 | 7 | 2 | 0 | 9 |
| 6 | 6 | 0 | 0 | 6 |
| 7 | 1 | 0 | 0 | 1 |
| 8 | 4 | 0 | 0 | 4 |
| 9 | 4 | 0 | 0 | 4 |
| 10 | 4 | 1 | 0 | 5 |
| all | 47 | 6 | 3 | 56 |

Partial means one team's offense and the opponent's defense are excluded; whole game means all four role observations are excluded; exception only means the game is declared in the exceptions file but the builder still observes it. The 44 ledger games reproduce the audit's classification (39 partial, 5 whole). The stored event totals of the ledger games were reproduced for 44 of 44.

## 2. Per-game reading

For each game the plays were read in the production order (drive, quarter, play). The data file has one row per game with, for each team: the final, the quarter line scores, the stored possession points, the maximum and last running score, every regression with its pattern, whether it is restored later, and the outcome of each rule. The raw Bronze rows were compared with the Silver plays by provider play id, score, drive, play and period.

**Bronze equals Silver.** 56 of 56 games have identical Bronze and Silver plays (10,140 rows). The byplay build then removes 762 rows (play types such as timeouts, end-of-period rows and uncategorised rows). Removing them can only hide regressions, never create one: counting team-games with a regression, the raw rows give 89 and the Silver byplay rows give 85. Sorting by provider play id gives 88 and by wall clock 83 (production order: 89); no order removes the defect.

Every regression of a team's running score, by the pattern taxonomy of known issue 1:

| Pattern | Events | Never restored |
|---|---|---|
| drop to zero | 30 | 0 |
| point after before kick | 19 | 0 |
| after scoring row | 22 | 1 |
| penalty adjacent | 20 | 2 |
| scoring credited then reversed | 103 | 7 |
| all | 194 | 10 |

Across the inventory, 12 team-games finish with a running maximum above the final, 1 below it, and 48 contain a single-row jump above 8 points.

**Overall shape.** The 194 regressions in the inventory are restored later to at least the pre-drop value 184 times and never restored 10 times. 45 sit on kickoff rows, 108 on ordinary scrimmage plays, 21 on penalty rows, and only 18 on a scoring play. The defect lives mostly on rows that are not scoring plays.

**Drop to zero.** 30 events, all restored. A team's running score is wiped to exactly 0 for a run of rows and then returns. In `401858436` USC is at 16 after a safety, shows 0 on the next five rows (the kickoff and USC's whole drive), and shows 23 on the touchdown row that ends the drive. The scoring rows on either side are consistent, so the zeros are plain outliers.

**Point after credited before the kick.** 19 events, all restored. A scoring row is followed, usually on the kickoff row, by a score one or two points lower. In `401856790` Pittsburgh's safety lifts it from 3 to 5, the next row shows 3 again, and 5 returns later. Where the touchdown row already includes the extra point and the next row does not, the row after the score is the one that is wrong, which is why a rule must not trust it.

**Reversal beside a penalty or review.** 20 events (2 never restored). Penalty rows (accepted, declined and no-play) carry scores that disagree with the plays around them. In `401856661` Ole Miss reads 10, then 9 on a delay-of-game row, then 17 on the touchdown. Two penalty rows filed under third-quarter drive 17 carry 24 and 27 (Louisville's 27 is only reached in the fourth quarter); their provider play ids and wall-clock stamps (03:45 and 03:47 UTC) are two hours after the neighbouring rows (02:16 UTC), so they are fourth-quarter plays attached to the wrong drive.

**Touchdown or field goal credited, then reversed.** 103 events (7 never restored), the largest group. An ordinary play carries a score the team has not reached yet or has already left behind. In `401856661` a pass-reception row shows Ole Miss at 18 and the next row at 17; in `401856732` Ole Miss falls from 17 to 3 on a reception row and is restored later. In `401856816` a touchdown row shows Utah at 24 when the fitted score is 17: the later score arrived early.

**Score restored later, or never.** 184 of 194 regressions are restored. The 10 that are not all belong to overshoot or undershoot team-games (below): a score that was too high falls back to the final, so it never returns to the earlier, wrong value.

**Maximum above the final.** 12 team-games finish with a running maximum above the final. In `401856790` UCF is at 7 after its fourth-quarter touchdown and then shows 13 on a Pittsburgh punt row; its final is 7 and its quarter line scores are 0, 0, 0, 7, so six points were never real. In `401856729` Kentucky's stream is perfectly monotone and ends at 40 against a final of 34. For these the final, not the stream, is the arbiter.

**Maximum below the final, and touchdowns credited short.** 1 team-game finishes below its final. In `401864579` New Mexico State's first fourth-quarter touchdown row moves the score from 3 to 5 (two points), the next from 5 to 12, and the game ends at 18: the six points of the first touchdown were never written. In `401861970` Miami (OH)'s first touchdown row reads 1 and the next scoring row 14. In `401864514` the full 61 appears on an ordinary play before the scoring plays reach 60. A scoring row can therefore be short, not only early.

**Negative scores.** 145 rows in 10 team-games carry a negative running score (for example Miami in `401858206`, 7 to -1 on a kickoff row). They are wrong rows, not points.

**A segment recorded twice.** `401860899` (Colorado State at Oregon State) has 31 direction reversals in one team's stream against 12 or fewer everywhere else. Its fourth-quarter plays appear twice a couple of seconds apart, one copy with Oregon State at 55 and the other at 42, and the stream peaks at 68 for a team that scored 56. Only this game has this pattern; the monotone fit and the cap at the final still resolve it, and its quarter line scores match.

## 3. Root-cause classes

Classes are assigned by the data file from each game's own plays (first matching rule, in the order listed): D when a team's score never reaches its final on a scoring play, C when it exceeds the final, B when a scoring play's own value disagrees with the monotone fit, A when only non-scoring rows disagree, E when nothing disagrees.

| Class | Games | Origin | Example games |
|---|---|---|---|
| `A_spurious_values_on_non_scoring_rows` | 41 | Provider feed | `401856661`, `401856695`, `401856716`, `401856732` |
| `B_wrong_value_on_a_scoring_row` | 2 | Provider feed | `401856816`, `401861970` |
| `C_points_above_the_final` | 11 | Provider feed | `401856729`, `401856790`, `401858259`, `401858278` |
| `D_points_missing_from_the_stream` | 2 | Provider feed | `401864514`, `401864579` |
| `E_no_stream_defect` | 0 | Ours (policy only) | none |
| Total | 56 |  |  |

**A, spurious values on non-scoring rows (41 games).** Every scoring play is consistent and the final is reachable; the bad values sit on kickoffs, penalties and ordinary plays. R4 resolves 64 of the 64 rejected team-games (63 match the quarter lines); R1 resolves 45. Provider defect: the same rows and values are in the raw Bronze capture.

**B, a scoring row carries the wrong value (2 games).** Utah (`401856816`) and Miami (OH) (`401861970`): a touchdown row is credited far too little (Miami (OH) reads 1) or too much (Utah reads 24 instead of 17), so even the scoring rows do not give a clean monotone path. R4 resolves 1 of 3 rejected team-games; R1 1. Provider defect.

**C, points above the final (11 games).** At least one team's running score exceeds its final: a touchdown (or more) is credited and never removed, or removed only by the final whistle. Quarantined today by the cap at the final. R4 resolves 16 of 16 rejected team-games, 16 matching the quarter lines; R1 14. Provider defect: the final score and the quarter line scores agree with each other and disagree with the play-by-play.

**D, points missing from the stream (2 games).** New Mexico State (`401864579`) and New Mexico (`401864514`): a team's scoring plays never add up to its final (a touchdown credited as two points; the last point of 61 appearing only on an ordinary play). R4 resolves 1 of 3; no rule that reads only the score columns can, because the missing points are not written on any scoring row. Provider defect.

**E, quarantined with no stream defect (0 games).** None. Every game has a rejected stream or a declared exception. **Our handling of valid data created no defect in any of the 56 games**: the Bronze and Silver plays are identical. What is ours is policy: the builder drops a whole team-game (and the opponent's defense) as soon as any row regresses, even though in most games only a handful of rows are wrong; it treats a final-score overshoot as unrecoverable although the final is the arbiter; and, for the three exception-only games, its score-regression rollback loses non-possession points (known issue 1).

## 4. Repair specification

**Recommended rule (R4 with a quarter-line gate).** Per completed game and team:

1. Anchors are the rows the provider marks as scoring plays (`scoring` is true, or the play type contains Touchdown, Field Goal Good, Safety, Extra Point Good or Two Point). Every other row's score column is ignored.
2. Fit the team's anchor values with the non-decreasing sequence that minimises total absolute error, using only values seen on the anchors plus 0 and the final, and never exceeding the final. Ties choose the lowest value.
3. Carry the fitted value forward to every row until the next anchor.
4. Resolved only if the carried stream reaches the final exactly and every possession (before = the team's score on the row before the drive, after = its score on the drive's last row) is between 0 and 8 points. Otherwise the team-game stays quarantined, exactly as today.
5. Optional gate: accept only if the points gained per quarter equal the game record's quarter line scores.
6. A team-game the builder already accepts is never touched.

Evidence relied on: the provider's scoring flag and play type (independent of the score columns; in team-games the builder accepts outside the inventory, 3381 of 3395 score increments sit on a scoring row), the game final, and the quarter line scores. The cap at the final is what guarantees the rule never exceeds it; `tests/ratings_lab/test_score_attribution.py` asserts that for synthetic overshoot streams, and the code asserts it on every stream it rebuilds (inventory and 2021 to 2025).

**Why not R1.** R1 reaches the final by construction, but it books a leaked early value as real, so the later scoring plays land in zero-point possessions, which shows as 24 rejected team-games (a single drive above 8 points) and, among those it resolves, only 264 of 306 increments are near a scoring play. R4 puts every increment on a scoring play by construction, and the quarter lines (a field R4 does not read) confirm it independently.

**Repair by class.** A: R4 as above. B: R4 repairs a wrong scoring value when the neighbouring anchors outvote it; where two adjacent anchors disagree the team-game stays quarantined, and a floor on the increment of a touchdown row (at least 6) plus the quarter lines would be the next refinement (not evaluated). C: the cap at the final removes the phantom points; the quarter lines show which quarter they belonged to. D: no score-column rule applies; the points would have to be rebuilt from the scoring plays' own text (touchdown 6, field goal 3, safety 2, plus the conversion in the text) and checked against the final and the quarter lines, which is a separate contract. Until then these stay quarantined.

### Rules compared on the whole set

Over the 112 team-games in the inventory, 86 fail the stream test (any regression, overshoot, undershoot or possession above 8 points; the builder's rollback absorbs some of these, so this is stricter than its quarantine; the other 26 are the clean sides of the same games and no rule touches them). Share of the stream-test rejects each rule resolves, where resolved means: monotone, reaches the final, never exceeds it, and every possession's points are between 0 and 8.

| Rule | Resolved team-games | Quarter lines match | Increments on or beside a scoring row | Games fully resolved | Unresolved reasons |
|---|---|---|---|---|---|
| R0 today (observed stream) | 0 (0.0%) | 0 | 0 of 0 | 0 | exceeds_final 1, score_regression 85 |
| R1 monotone envelope capped at the final | 61 (70.9%) | 49 | 264 of 306 | 31 | drive_points_outside_0_8 24, short_of_final 1 |
| R2 capped monotone fit to every row | 80 (93.0%) | 65 | 449 of 467 | 50 | drive_points_outside_0_8 5, short_of_final 1 |
| R3 R2 bounded by the quarter line scores | 76 (88.4%) | 68 | 422 of 441 | 48 | drive_points_outside_0_8 5, quarter_bounds_infeasible 4, short_of_final 1 |
| R4 capped monotone fit to scoring rows only | 82 (95.3%) | 80 | 447 of 447 | 52 | drive_points_outside_0_8 2, short_of_final 2 |

The quarter line scores come from the CFBD game record, a separate field from the play-by-play score, so a match is independent corroboration. R3 uses them as bounds, so its match is by construction and it is shown only to demonstrate that anchoring to them does not beat R4. The share of rejected team-games whose reconstructed total equals the final without the validity checks is 85 for R1 and 84 for R4 of 86.

The earlier R1 analysis (known issue 1, weeks 0 to 4) left 18 quarantines unresolved because one possession would carry more than 8 points. In this rebuild 11 weeks 0 to 4 team-games are unresolved under R1 for that reason; R4 resolves 9 of them (9 matching the quarter lines). R1's resolved team-games are also the less trustworthy ones: a leaked early value is booked as real, so later touchdowns are credited to the wrong possession (the table's increments column).

### Team-games R4 leaves unresolved

| Game | Team | Final | Max running | R4 reaches | Reason |
|---|---|---|---|---|---|
| `401856816` | Utah | 31 | 31 | 31 | drive_points_outside_0_8 |
| `401858460` | Wisconsin | 54 | 54 | 54 | resolved, quarter lines differ |
| `401861970` | Miami (OH) | 24 | 24 | 24 | drive_points_outside_0_8 |
| `401864514` | New Mexico | 61 | 61 | 60 | short_of_final |
| `401864579` | New Mexico State | 18 | 12 | 12 | short_of_final |
| `401864579` | New Mexico | 42 | 42 | 42 | resolved, quarter lines differ |

Utah and Miami (OH) (class B): two adjacent scoring rows disagree, so one possession would have to carry more than 8 points. New Mexico and New Mexico State (class D): the missing points are on no scoring row. Wisconsin (`401858460`) and New Mexico (`401864579`) are resolved by R4 but one quarter's gain differs from the quarter line (Wisconsin gains 29 in the second quarter against a line of 28); a gate that requires the quarter lines would hold them back, and the cause of the one-point shift was not isolated.

## 5. Historical effect, 2021 to 2025

Each rule was applied read-only to the pinned Silver `byplay` of each season: only team-games the builder rejects had their score columns rewritten, then the unchanged `build_measurements` produced the ppp observations. The baseline is the stored corpus observation set. Season ppp below is the exposure-weighted raw points per possession of the observed team-games (teams with at least 40 observed possessions); it is **not** the opponent-adjusted, prior-shrunk V5 rating, which was not recomputed.

| Season | Rule | Offense team-games excluded today | Offenses restored | Roles still excluded | Roles newly lost | Observed rows changed | Points restored |
|---|---|---|---|---|---|---|---|
| 2021 | R1 | 121 | 51 | 140 | 0 | 0 | 2260.0 |
| 2021 | R2 | 121 | 57 | 128 | 0 | 0 | 2264.0 |
| 2021 | R4 | 121 | 61 | 120 | 0 | 0 | 2944.0 |
| 2022 | R1 | 148 | 57 | 182 | 0 | 0 | 2326.0 |
| 2022 | R2 | 148 | 56 | 184 | 0 | 0 | 2248.0 |
| 2022 | R4 | 148 | 68 | 160 | 0 | 0 | 3024.0 |
| 2023 | R1 | 65 | 34 | 62 | 0 | 0 | 1370.0 |
| 2023 | R2 | 65 | 39 | 52 | 0 | 0 | 1544.0 |
| 2023 | R4 | 65 | 42 | 46 | 0 | 0 | 1946.0 |
| 2024 | R1 | 74 | 38 | 72 | 0 | 0 | 1752.0 |
| 2024 | R2 | 74 | 50 | 48 | 0 | 0 | 2090.0 |
| 2024 | R4 | 74 | 50 | 48 | 0 | 0 | 2358.0 |
| 2025 | R1 | 151 | 78 | 146 | 0 | 0 | 3328.0 |
| 2025 | R2 | 151 | 120 | 62 | 0 | 0 | 5514.0 |
| 2025 | R4 | 151 | 118 | 66 | 0 | 0 | 5966.0 |

| Season | Rule | Offense teams moving > 0.05 / > 0.10 ppp | Offense rank moves > 5 | Max offense move | Defense teams moving > 0.05 / > 0.10 ppp | Defense rank moves > 5 | Max defense move |
|---|---|---|---|---|---|---|---|
| 2021 | R1 | 29 / 14 | 21 | 0.382 | 26 / 17 | 22 | 0.267 |
| 2021 | R2 | 29 / 13 | 19 | 0.390 | 25 / 13 | 20 | 0.367 |
| 2021 | R4 | 26 / 14 | 18 | 0.382 | 30 / 13 | 23 | 0.206 |
| 2022 | R1 | 26 / 18 | 16 | 0.370 | 32 / 17 | 23 | 0.287 |
| 2022 | R2 | 22 / 13 | 12 | 0.370 | 30 / 15 | 27 | 0.272 |
| 2022 | R4 | 30 / 20 | 22 | 0.432 | 35 / 18 | 26 | 0.287 |
| 2023 | R1 | 19 / 11 | 14 | 0.230 | 18 / 9 | 12 | 0.288 |
| 2023 | R2 | 18 / 11 | 15 | 0.230 | 24 / 15 | 18 | 0.288 |
| 2023 | R4 | 24 / 15 | 19 | 0.230 | 22 / 12 | 18 | 0.312 |
| 2024 | R1 | 19 / 9 | 15 | 0.523 | 19 / 9 | 14 | 0.193 |
| 2024 | R2 | 26 / 11 | 20 | 0.523 | 23 / 11 | 18 | 0.269 |
| 2024 | R4 | 23 / 13 | 18 | 0.523 | 22 / 11 | 19 | 0.232 |
| 2025 | R1 | 31 / 21 | 20 | 0.385 | 40 / 21 | 31 | 0.395 |
| 2025 | R2 | 46 / 23 | 28 | 0.400 | 50 / 25 | 35 | 0.384 |
| 2025 | R4 | 45 / 23 | 27 | 0.310 | 48 / 31 | 45 | 0.571 |

Only team-games the stored measurements exclude today were rewritten, so every observation that exists today is unchanged (the `Observed rows changed` and `Roles newly lost` columns are 0 in every season and rule). Across the five seasons 559 offense team-games are excluded today.

- R1 restores 258 of 559 offense team-games (and as many opponent defenses): 2021 42%, 2022 39%, 2023 52%, 2024 51%, 2025 52%.
- R2 restores 322 of 559 offense team-games (and as many opponent defenses): 2021 47%, 2022 38%, 2023 60%, 2024 68%, 2025 79%.
- R4 restores 339 of 559 offense team-games (and as many opponent defenses): 2021 50%, 2022 46%, 2023 65%, 2024 68%, 2025 78%.

R4 restores far fewer team-games in 2021 to 2024 than the 95% it resolves in the 2026 inventory. In those seasons the builder excludes team-games for reasons beyond a regressing stream, and the pinned historical Silver is the older `byplay_v1` lineage; the split was not isolated here. Season raw points per possession moves for 23 to 45 offenses and 22 to 48 defenses per season by more than 0.05 under R4, and the largest single-team move is 0.52 ppp on offense. Ranks among the roughly 135 to 150 teams compared move by more than five places for 18 to 27 offenses per season. R1 and R4 are close on these observation-level totals; the difference between them is where points are placed within a game (known from the 2026 placement column), which season totals mostly do not show.

## 6. Spot check

Five games, one from each class that has games plus the game with the most direction reversals, were re-read independently of the analysis module. The first check recomputes each team's maximum running score and its count of regressions with plain array operations straight from the raw Bronze rows; the maximum matches the committed record for 5 of 5 games. Bronze counts at least as many regressions as the record because the byplay build removes rows that could only add regressions. The second check was a manual reading of the plays around each defect (kickoff, penalty and scoring rows with their play text):

- `401856661` (A): Ole Miss max 41 (record 41), regressions 3 raw / 3 record; Louisville max 38 (record 38), regressions 2 raw / 1 record.
- `401856816` (B): Iowa State max 17 (record 17), regressions 4 raw / 4 record; Utah max 31 (record 31), regressions 8 raw / 7 record.
- `401856729` (C): Kentucky max 40 (record 40), regressions 0 raw / 0 record; Vanderbilt max 17 (record 17), regressions 0 raw / 0 record.
- `401864514` (D): New Mexico max 61 (record 61), regressions 5 raw / 5 record; UTEP max 7 (record 7), regressions 0 raw / 0 record.
- `401860899` (C): Colorado State max 32 (record 32), regressions 7 raw / 6 record; Oregon State max 68 (record 68), regressions 19 raw / 19 record.

The manual readings agree with the records: `401856661` (A) shows the stale penalty-row and later-score values described above; `401856816` (B) the Utah touchdown row at 24; `401856729` (C) a Kentucky stream that is monotone to 40 against a final of 34; `401864514` (D) the 61 appearing on an ordinary play with the scoring rows at 60; `401860899` the duplicated fourth quarter.

## 7. Not done, risks, decisions

- **No ratings were recomputed.** The historical effect is at the ppp observation level (season points per possession and its ranks). The opponent-adjusted, prior-shrunk V5 rating needs the V5 control replay and was not run; the move in rating terms is smaller than the raw-ppp move shown. Nothing was written.
- **Raw Bronze was read for 2026 only.** 2021 to 2025 use the pinned Silver `byplay`; 2026 shows Bronze equals Silver, and the quarantine rate and classes in 2025 match 2026's (known issue 10).
- **No play-text ledger** (touchdown 6, field goal 3, safety 2, conversions parsed from text) was built, so classes B and D have no repair yet. It would use only fields already in the Silver plays; no provider request is needed.
- **Provider-side cause.** What inside CFBD produces the stale and future scores cannot be settled from our data. Settling it would need a different CFBD request (for example the drives endpoint for these games, already seen to be unclean in known issue 1) or a provider ticket; no request was made.
- **Possession points outside drives** (defensive and special-teams touchdowns) are unchanged by every rule here; they feed offsets and the matchup page, not ppp.
- **Inventory is 56 games, not 55.** The contract's union of the audit ledger and the exceptions file is 55; the current builder also quarantines `401858279` with no exception, so it is included and flagged.
- **Decisions for the owner.** (1) Whether to open a contract that adopts R4 plus the quarter-line gate as the next-model measurement rule, and whether it should also re-derive the 2025 terminal table and priors. (2) Whether to open the play-text ledger contract for classes B and D. (3) Whether to ask the provider about the feed defect.

## Appendix: every game

| Game | Week | Final | Kind | Max running | Regressions | Class | R1 resolves | R4 resolves |
|---|---|---|---|---|---|---|---|---|
| `401856661` | 1 | Ole Miss 41, Louisville 38 | partial quarantine | 41 / 38 | 4 | A | yes | yes |
| `401856695` | 3 | Vanderbilt 35, NC State 31 | observed exception only | 35 / 31 | 1 | A | yes | yes |
| `401856716` | 6 | Missouri 27, Texas A&M 6 | partial quarantine | 27 / 6 | 2 | A | yes | yes |
| `401856729` | 8 | Kentucky 34, Vanderbilt 17 | partial quarantine | 40 / 17 | 0 | C | yes | yes |
| `401856732` | 8 | Texas 34, Ole Miss 27 | partial quarantine | 34 / 27 | 1 | A | yes | yes |
| `401856783` | 2 | Oregon State 24, Texas Tech 35 | partial quarantine | 24 / 35 | 4 | A | yes | yes |
| `401856790` | 2 | Pittsburgh 12, UCF 7 | partial quarantine | 12 / 13 | 2 | C | yes | yes |
| `401856793` | 3 | Arizona 42, Northern Illinois 17 | observed exception only | 42 / 17 | 2 | A | yes | yes |
| `401856816` | 4 | Iowa State 17, Utah 31 | partial quarantine | 17 / 31 | 11 | B | no | no |
| `401856825` | 6 | Kansas State 16, Houston 35 | partial quarantine | 16 / 35 | 1 | A | no | yes |
| `401856853` | 10 | Baylor 42, Iowa State 31 | partial quarantine | 42 / 31 | 1 | A | no | yes |
| `401856854` | 10 | Kansas State 28, Oklahoma State 66 | partial quarantine | 28 / 66 | 2 | A | no | yes |
| `401858201` | 0 | Stanford 37, Hawai_i 27 | partial quarantine | 37 / 27 | 5 | A | no | yes |
| `401858206` | 1 | Stanford 6, Miami 45 | whole game quarantine | 6 / 45 | 8 | A | yes | yes |
| `401858224` | 2 | Purdue 36, Wake Forest 38 | whole game quarantine | 36 / 38 | 7 | A | no | yes |
| `401858245` | 5 | Virginia Tech 33, Pittsburgh 35 | partial quarantine | 33 / 35 | 3 | A | no | yes |
| `401858247` | 5 | UNLV 39, California 31 | partial quarantine | 39 / 31 | 2 | A | no | yes |
| `401858259` | 6 | California 25, Virginia Tech 20 | partial quarantine | 25 / 25 | 4 | C | no | yes |
| `401858275` | 8 | North Carolina 30, Syracuse 31 | partial quarantine | 30 / 31 | 3 | A | no | yes |
| `401858278` | 9 | Syracuse 30, SMU 27 | partial quarantine | 30 / 33 | 3 | C | yes | yes |
| `401858279` | 9 | Duke 47, Boston College 2 | partial quarantine | 47 / 2 | 1 | A | yes | yes |
| `401858283` | 9 | Louisville 52, Stanford 24 | partial quarantine | 52 / 24 | 3 | A | yes | yes |
| `401858433` | 1 | Oregon 34, Boise State 27 | partial quarantine | 34 / 27 | 6 | A | no | yes |
| `401858436` | 1 | USC 39, Fresno State 0 | partial quarantine | 39 / 0 | 1 | A | yes | yes |
| `401858445` | 2 | USC 49, Louisiana 30 | partial quarantine | 49 / 30 | 6 | A | no | yes |
| `401858454` | 3 | Ohio State 59, Kent State 3 | partial quarantine | 59 / 3 | 2 | A | no | yes |
| `401858460` | 3 | Wisconsin 54, Eastern Michigan 10 | partial quarantine | 54 / 10 | 3 | A | yes | yes |
| `401858464` | 4 | Michigan State 13, Nebraska 31 | partial quarantine | 13 / 31 | 1 | A | yes | yes |
| `401858475` | 5 | Nebraska 48, Maryland 23 | partial quarantine | 48 / 23 | 4 | A | no | yes |
| `401858482` | 6 | Northwestern 45, Ball State 14 | partial quarantine | 45 / 14 | 1 | A | no | yes |
| `401858493` | 7 | Purdue 26, Washington 38 | partial quarantine | 26 / 38 | 2 | A | no | yes |
| `401859184` | 2 | Notre Dame 52, Rice 0 | partial quarantine | 52 / 0 | 1 | A | yes | yes |
| `401860881` | 2 | Boise State 38, Memphis 20 | partial quarantine | 38 / 21 | 2 | C | yes | yes |
| `401860899` | 5 | Colorado State 26, Oregon State 56 | whole game quarantine | 32 / 68 | 25 | C | no | yes |
| `401860900` | 5 | San Diego State 31, Texas State 29 | partial quarantine | 31 / 29 | 3 | A | yes | yes |
| `401861966` | 9 | Air Force 35, Connecticut 26 | partial quarantine | 35 / 26 | 1 | A | yes | yes |
| `401861970` | 4 | Miami (OH) 24, Connecticut 21 | partial quarantine | 24 / 21 | 3 | B | no | no |
| `401862702` | 2 | Army 24, South Florida 28 | partial quarantine | 30 / 28 | 2 | C | yes | yes |
| `401862703` | 2 | Florida Atlantic 38, Navy 30 | partial quarantine | 38 / 30 | 3 | A | no | yes |
| `401862710` | 3 | Old Dominion 17, East Carolina 20 | partial quarantine | 17 / 20 | 2 | A | yes | yes |
| `401862771` | 3 | Florida Atlantic 16, Florida International 10 | partial quarantine | 16 / 10 | 3 | A | no | yes |
| `401864443` | 3 | Middle Tennessee 27, Nevada 20 | partial quarantine | 30 / 20 | 1 | C | yes | yes |
| `401864502` | 2 | Air Force 32, North Dakota State 38 | whole game quarantine | 32 / 38 | 2 | A | no | yes |
| `401864514` | 5 | New Mexico 61, UTEP 7 | partial quarantine | 61 / 7 | 5 | D | no | no |
| `401864579` | 4 | New Mexico State 18, New Mexico 42 | observed exception only | 12 / 42 | 5 | D | no | no |
| `401866425` | 4 | Kent State 26, Ball State 13 | partial quarantine | 26 / 13 | 3 | A | yes | yes |
| `401866431` | 5 | Ball State 24, Toledo 39 | partial quarantine | 31 / 39 | 3 | C | yes | yes |
| `401866449` | 8 | Ohio 24, Eastern Michigan 20 | partial quarantine | 24 / 20 | 5 | A | yes | yes |
| `401869933` | 6 | Arkansas State 49, South Alabama 56 | partial quarantine | 49 / 62 | 4 | C | yes | yes |
| `401869942` | 5 | Coastal Carolina 24, Georgia Southern 31 | whole game quarantine | 24 / 37 | 6 | C | yes | yes |
| `401869951` | 10 | Georgia Southern 49, Marshall 13 | whole game quarantine | 49 / 13 | 5 | A | yes | yes |
| `401869961` | 4 | Old Dominion 20, James Madison 46 | partial quarantine | 20 / 46 | 3 | A | no | yes |
| `401869964` | 10 | Southern Mississippi 23, James Madison 54 | partial quarantine | 23 / 54 | 1 | A | yes | yes |
| `401869965` | 6 | Louisiana Tech 32, Louisiana 31 | partial quarantine | 32 / 31 | 2 | A | no | yes |
| `401871049` | 5 | New Mexico State 34, Western Kentucky 13 | partial quarantine | 34 / 13 | 4 | A | yes | yes |
| `401871074` | 10 | Florida International 23, Missouri State 20 | partial quarantine | 23 / 20 | 4 | A | yes | yes |
