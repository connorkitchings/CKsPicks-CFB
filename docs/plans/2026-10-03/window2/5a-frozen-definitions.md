# Window 2 Step 5A: frozen definitions

- **Authority:** [contract 04, Amendment 2](../04-data-integrity-two-window-implementation.md), [Appendix A, 5A](data-contracts-and-certification.md).
- **Frozen:** 2026-10-04, **before** any baseline-versus-R1 diff, CFBD drive, or corroboration result was computed or looked at for 2015-2019 or 2021-2025. The only prior evidence is the 2026 weeks 0-4 investigation (`artifacts/backups/2026-10-03/investigation/`, decision packet items 16-26). Commit this file before the diff runs; any later change is an amendment with its reason, never a silent edit.
- **User decisions recorded 2026-10-04:** grouping = per team-game region; if the 25% gate fails, stop and review as the contract says (no pre-authorized reduced Window 2); CFBD drives are fetched only for games with changed groups, after the diff is reported and the user approves the request count.

## Inputs and comparison

- **Baseline** is the served ledger rule, `build_possession_ledger` in `src/cks_picks_cfb/ratings/possession_measurements.py` (score-regression rollback, eight-point increment limit, `exceeds_repaired_final` cap, unresolved quarantine), run on the pinned historical Silver byplay and game outcomes.
- **Candidate R1** is the rule frozen in `artifacts/backups/2026-10-03/investigation/d1-candidate-rule.md`: for each team-game, `e_t = min(F, max over u <= t of s_u)` in `(season, game_id, quarter, drive_number, play_number)` order, applied to `offense_score` and `defense_score`, with the team-game left unresolved (quarantined as today) when the envelope does not reach the certified final. The eight-point limit, conversion rules, category rules, the final cap and the exclusion of overtime and garbage time are unchanged. It is a non-serving candidate (`src/cks_picks_cfb/ratings/score_envelope_r1.py`).
- **Scope:** 2015-2019 and 2021-2025 for the gate; 2020 excluded; 2026 reported separately and excluded from the gate.

## Events, changes and groups

- **Event key:** `(game_id, team, source_event_id)`.
- **Compared fields:** `score_increment`, `scoring_category`, `unit_category`, `associated_possession_id`, `conversion_for_event_id`, `quality_reason`. Missing equals missing.
- **Changed event:** present in only one ledger, or any compared field differs.
- **Order within a team-game:** events sorted by `(drive_number, position)`, where position is the event's position in the baseline ledger, or in the candidate ledger when the event exists only there.
- **Region:** within one `(game, team)`, a maximal run of changed events with no unchanged event between them in that order.
- **Allocation group:** a region, merged with any other region of the same `(game, team)` that is linked to it by a `conversion_for_event_id` reference on either side. A group is counted once. `group_id` is the first 16 hex characters of SHA-256 of `season|game_id|team|first_changed_event_id`.
- **Denominator of the gate:** every changed group in 2015-2019 and 2021-2025.

## Channels and causes

- **Net change** of a group = sum of candidate `score_increment` minus sum of baseline `score_increment` over its events.
- **Channel:** `points_recovery` (net > 0), `points_reduction` (net < 0, for example a final-cap clip), `attribution_only` (net = 0).
- **Flags** (a group can carry several): `incomplete_stream` (an `unresolved` marker on exactly one side other than an `exceeds_repaired_final` marker), `restoration_gt8` (the raw team score stream has an increase of more than eight points after an earlier decrease), `dip_restore` (a baseline event with `quality_reason = score_regression_rollback`), `final_cap` (a baseline event with `quality_reason = exceeds_repaired_final`), `conversion_reassignment` (`conversion_for_event_id` differs), `category_possession_reassignment` (category, unit or possession differs).
- **Primary cause**, assigned by this precedence: `incomplete_stream`, `restoration_gt8`, `dip_restore`, `final_cap`, `conversion_reassignment`, `category_possession_reassignment`, `other`. All flags are still reported.

## Corroboration (5A, applied only after the diff is reported)

- **A game's CFBD drives are usable** only if all four checks pass: drive scoring reconciles with the certified quarter and final totals (non-drive scores accounted for explicitly); drive boundaries and team identities match the possession ledger; touchdowns and conversions have consistent associations; no unexplained regression, excess points, duplicate allocation or timing conflict. A final-total match alone is not enough.
- **A group is corroborated** when its game's drives are usable and, for every drive the group touches, CFBD's points for that team equal the candidate's allocated points. A group where CFBD matches the baseline, or where the drives are unusable, is not corroborated.
- **Gate:** corroborated groups / changed groups >= 25% across the historical corpus, reported by season, primary cause, channel and recovered points. At or above 25% the work continues to 5B. Below 25% the baseline is retained and work stops for review. This feasibility threshold never admits an unverified change.
- **Evidence retention:** exact CFBD responses with request, capture timestamp and SHA-256, for the games fetched only.

## Not frozen here (reported as found)

The number of changed groups, games and CFBD requests; baseline reproduction results; null-PPA exposure counts. None of these has been computed for the historical corpus.

## Port check against the 2026 investigation (added 2026-10-04; a clarification, not a change to any definition above)

`score_envelope_r1.py` was run on the saved 2026 weeks 0-4 inputs (`w4_byplay`, `w4_games`, `w4_game_outcomes`; 215 games, 430 team-games; 2026 only, excluded from the gate) and compared with the recorded investigation (decision packet items 16-26):

- Baseline ledger reasons match: 138 `score_regression_rollback` and 29 `exceeds_repaired_final` events in the baseline, and none of either under R1.
- Changed team-games at the observation level: 146, which is the recorded 145 plus the one team-game R1 leaves unresolved (New Mexico State, which the investigation script also excludes).
- Ledger-event view under the frozen group definition: 132 groups in 119 team-games (97 `dip_restore`, 19 `category_possession_reassignment`, 6 `incomplete_stream`, 4 `restoration_gt8`, 3 `final_cap`, 3 `other`); 10 recovery groups for +147 points across all categories and 122 attribution-only groups.
- The investigation's "channel A" was defined differently: a team-game whose points identity gap closes (or whose quarantine lifts) under R1, giving 11 team-games and +113 offensive points. The frozen 5A channel is per group and counts all categories, so its recovery counts (10 groups, +147) are not comparable to the 11 and +113 and must not be read as a discrepancy. 5A reports both: the frozen-group channels and, for continuity, the team-game identity-closure count.

## Amendment 1 (2026-10-04, after the first corroboration run): how checks 1 and 2 are computed

This amendment was made **after** the first corroboration run produced a zero, so it is a post-hoc change and is labelled as one. The gate threshold (25%), the group definition, the four checks, the corroboration rule and the requirement that every touched drive match are **unchanged**; only the computation of two checks changed.

- **First run (superseded, kept in `5a-data/corroboration_first_attempt_superseded.json`):** 23 of 8,936 games usable and **0 of 3,193 groups corroborated**.
- **Check 1 was implemented wrongly.** It compared the score at the start of the first drive of the next quarter with the cumulative quarter score. That is exact only at halftime: after a quarter begins, scoring can happen before the next drive starts, and a drive can span the boundary, so the Q1 and Q3 comparisons failed in about half of all games for a reason unrelated to data quality. **Now:** the opening score must be 0-0; the last drive's end scores must equal the certified final for both teams; and for each period 1 to 4 the score after the last drive that ends in or before that period must equal the cumulative line score, where a scoring drive is counted in the period it ends in. Points between drives (the next drive's start minus the previous end) are the explicit non-drive scores; in a game that has any, only halftime and the end of regulation are required to match.
- **Check 2 was implemented wrongly.** It required the set of CFBD regulation drives to equal the set of all ledger possessions. In 7,922 of the 8,799 failing games every CFBD drive was already in the ledger, and the ledger had about 11 extra possessions per game: return and other special-teams-only possessions that CFBD does not call drives. **Now:** every CFBD regulation drive must be a ledger possession (same drive number and offense), and every ledger regulation possession that carries eligible plays must be a CFBD drive. Strict equality is still computed and reported as a diagnostic (`c2_strict`; 104 games pass it).
- **Principle, not a target:** each correction was chosen from what the check is meant to establish (drive boundaries and team identities agree; quarter totals reconcile) before looking at how the gate would move. The gate under each reasonable variant is reported in the sizing report so the dependence on these choices can be judged.
- **Also clarified:** the corroboration script takes each group's channel and primary cause from the sizing run (which had the raw play stream for the `restoration_gt8` flag) and adds each group's touched drive numbers; the groups and ids are identical to the sizing run's.
