# D findings: zero-PPA plays (read-only, 2026-10-03)

Method: join Silver `byplay` (w4 set) to the raw Bronze CFBD plays on (game_id, drive_number, play_number) (0 duplicate keys
in Silver, 1 in raw, 0 Silver plays unmatched). Files: `d_zero_ppa_classified.csv`, `d_zero_ppa_simulation.csv`.

## Classification (issue 3)
- 26,260 eligible scrimmage plays; 155 have Silver `ppa == 0`.
- **All 155 (100%) are CFBD nulls turned into 0 by the `fillna(0)` in `features/byplay/enrichment.py`.** None is a genuine raw zero,
  and none is a build artifact. The 155 are also the only eligible plays with a null raw `ppa` (0.59%).
- By week 0-4: 2 / 17 / 27 / 67 / 42. By play type: Rush 41, Fumble Recovery (Opponent) 41, Pass Reception 26,
  Pass Incompletion 17, Interception 13, Fumble Recovery (Own) 8, Fumble 6, Pass Interception Return 2, Safety 1.

## Impact on the displayed team stats (D2 = treat as missing)
Rebuilt with those plays' `ppa` set to missing (local, `build_team_season_stats`, as_of_week 5, 276 team-role rows per metric):
| metric | rows changed | mean dv | max abs dv | rank moves > 5 | max abs rank move |
|---|---|---|---|---|---|
| ppa_per_play | 187 | +0.0007 | 0.0060 | 0 | 2 |
| epa_pass | 90 | +0.0007 | 0.0141 | 0 | 2 |
| epa_rush | 138 | +0.0004 | 0.0053 | 0 | 4 |
| early_down_epa | 155 | +0.0003 | 0.0073 | 0 | 2 |
Negligible for the web: no rank moves more than 4. (The team-stats means ignore NaN, so dropping the null plays barely changes them.)

## Impact on V5 (this is the part that matters)
- `ratings/possession_measurements.py` marks a team-game's EPA invalid when any eligible play has a null `ppa`
  (`ppa_invalid`, lines ~531, 642). The Silver zero-fill hides every null, so that path never fires and the 155 plays count as
  exactly 0 EPA in `eligible_epa` and `epa_per_possession`, which the ratings fit.
- **127 of 430 offense team-games (29.5%) contain at least one such play** (max 3 in one team-game).
- Most are turnover-type plays whose real EPA is strongly negative: reference mean `ppa` of non-null plays of the same type
  is -4.20 (Fumble Recovery, Opponent), -3.81 (Interception), -4.59 (Pass Interception Return), -1.03 (Fumble Recovery, Own),
  -0.78 (Pass Incompletion). Using those reference means, about **-232 EPA over the 155 plays is counted as 0**, i.e. the offense's
  `epa_per_possession` is overstated (and the opposing defense understated) by about 1.8 EPA per touched team-game.
- If D2 were implemented as "null" in Silver, the current V5 builder would quarantine EPA for those 127 team-games (29.5%),
  which is worse than the bias. So a V5-side fix needs a policy (impute by play-type reference vs quarantine) and its own contract
  and delta report: it moves `epa_per_possession`, one of the two fitted measures. Nothing was changed here.

## For the packet
- D2: for the displayed team stats, treating the nulls as missing is honest and costs nothing visible.
- For V5, the zero-fill is a real, one-directional bias (offenses look better after turnovers than they were) and belongs in the V5-rebuild
  contract together with the quarantine fix, not in a Silver-only change.
- D3 (Silver rebuild) therefore stays on the table for the punt-return tag and this null handling, but the V5 effect is only realised
  if V5 is rebuilt too (D4).

## Addendum (2026-10-03): why is `ppa` null on the 155 plays? Read-only; scratch `ppa_null_study.py`, `ppa_null_study2.py`, `ppa_null_study3.py`, `ppa_revisions.py`, `ppa_which_version.py`
Outputs: `d_ppa_null_rate_by_play_type.csv`, `d_ppa_null_causes.csv`, `d_ppa_null_plays_with_text.csv`, `d_ppa_revised_plays.csv`.

**Q1. Is there enough raw signal to compute or impute EPA ourselves?** The raw CFBD play record carries `down`, `distance`, `yardsToGoal`, `yardsGained`, `playText`, clock, period, scores and `scoring`, but no expected-points field other than `ppa` itself.
Classifying the 155 (first matching rule): **10** are "no play" (offsetting or nullifying penalty: nothing happened, so there is no EPA and arguably no play), **11** are
turnovers on kickoff or punt returns (no scrimmage start state), **12** are end-zone turnovers ending in a touchback, **75** have a missing start state in the feed (the feed gives a literal
0 for `down` or `yardsToGoal`, e.g. "run for 0 yds" at yards-to-goal 0), and **47** have a valid down and yards-to-goal (for example a 45-yard reception at USM21). So 108 of 155 (70%) have no valid pricing state or are not plays; they are
unpriceable by CFBD's own model, not data we dropped. The 47 could be priced with an expected-points model of our own, but CFBD's lookup is proprietary (its documentation says so), so we could not reproduce its scale, and building one would be new modelling.
The cheap alternative is the play-type reference mean (turnover-type plays about -4; see Q3), which is an estimate, not CFBD's value. By week: 2 / 17 / 27 / 67 / 42 (weeks 0-4).

**Q2. Systematic or sporadic?** Both. Null rate of raw `ppa` among eligible scrimmage plays by type (full table in the CSV):
| play type | plays | null | rate |
|---|---|---|---|
| Fumble Recovery (Opponent) | 127 | 41 | 32.3% |
| Fumble | 33 | 6 | 18.2% |
| Interception | 94 | 13 | 13.8% |
| Safety | 11 | 1 | 9.1% |
| Fumble Recovery (Own) | 205 | 8 | 3.9% |
| Pass Interception Return | 160 | 2 | 1.3% |
| Pass Incompletion | 4,305 | 17 | 0.4% |
| Pass Reception | 7,070 | 26 | 0.4% |
| Rush | 12,395 | 41 | 0.3% |
| Sack, Rushing/Passing Touchdown, Interception Return TD | 688 / 573 / 562 / 28 | 0 | 0% |
CFBD prices most turnover plays (68% of opponent fumble recoveries, 86% of interceptions), so the nulls are not a blanket "never priced" rule; they concentrate in situations with no valid start state: null interceptions are 85% touchbacks (vs 5% of priced ones);
null incompletions are 29% "no play" penalties (vs 0%); null receptions are 19% penalty and 35% out of bounds; null rushes have a mean yards-to-goal of 0.3 (vs 51.6) and 29% are kneel-downs. Nulls are also 45% last-play-of-drive (vs 17%).
Nearly all of the EPA bias comes from the turnover-type plays: about 70 of the 155 (41 + 13 + 8 + 6 + 2), worth roughly -240 EPA at the type reference means; the other 85 are near-neutral.

**Q3. Is "treat as missing" right, or does CFBD imply a value?** CFBD's own documentation (the glossary at `api.collegefootballdata.com/metrics-and-definitions` and the PPA methodology page) says PPA is the difference between the scoring expectation at the start and end of a play from a state defined by down, distance and field position,
that turnovers are "handled according to their resulting game state" (so a priced value is intended, and a null on a turnover is a provider gap, not a design choice), that the lookup table is proprietary, and that "null means the value is unavailable or not applicable. It should not be converted to zero without an explicit analytical reason."
It does not give a fixed value for a dead-ball turnover. So zero is specifically wrong; "missing" is right for no-plays and for plays without a start state; for the turnover plays it is the safe default but it biases means upward (the missing plays are the costly ones).

**Q4. Would a re-fetch fill them?** Unlikely. Across our 35 captures no play ever went from null to a value (0 of 155; 10 went from a value to null), and one targeted fresh pull of week 3 (13,321 plays) left all 67 of that week's null plays null (0 filled); of 9,951 non-null values compared, 1 changed.
So a re-pull is not worth doing for the nulls.

**Separate finding that surfaced (not part of the 155): CFBD revised turnover EPA in mid-September.** 682 plays (weeks 1-2 only, 179 games) changed their non-null `ppa` between our Sep 13 and Sep 20 captures, mean absolute change 2.1: e.g. an interception return -0.28 to -6.34. 305 are turnover plays; on eligible plays the means moved from -1.6 to -3.9 (interceptions), -1.6 to -4.4 (interception returns) and -2.1 to -4.8 (opponent fumble recoveries).
Silver holds the **corrected** value for all 418 revised plays in the w4 set (0 hold the old value; Silver equals the latest raw capture on 28,192 of 28,193 comparable rows), so Silver and the V5 measurements are not contaminated. The lesson: CFBD can revise `ppa` after capture, so the weekly cycle should refresh earlier weeks' plays before freezing (D9).

**What would change the D2 recommendation.** The earlier packet text said "impute by play-type reference vs quarantine, decided inside the D4 contract". The evidence now favors a split policy over either extreme: (i) exclude the no-plays (10) and the start-state-missing plays (75) from EPA sums and means, because there is nothing to price (and the no-plays are not plays); (ii) impute only the turnover-type plays that have a valid state with the same-type reference mean, since CFBD intends to price them and they carry almost all of the bias; (iii) do not quarantine the team-game's EPA. It is still an estimate in a fitted measure, so it needs the contract's own delta report, and imputed values should be flagged in the data. Zero-fill is not defensible under CFBD's own guidance.
