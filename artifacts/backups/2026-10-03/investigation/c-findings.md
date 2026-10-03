# C findings: drive metrics and the overtime hypothesis (read-only, 2026-10-03)

Method: ran the project's own `build_team_season_stats` locally on the certified w4 Silver set (drives from `aggregate_drives`),
as_of_week 5, FBS teams = teams in the Silver games table. File: `c2_overtime_simulation.csv`.

## Reproduction of the published values
- 828 team-role-metric rows for `avg_start_field_pos`, `scoring_opp_rate`, `pts_per_scoring_opp` compared with Preview
  `team_season_stats`: **max |value difference| = 0.0** for all three metrics.
- **Rank divergence resolved (it was my comparison, not the publisher):** the earlier "98.7% equal" came from comparing
  `NaN != NaN`. Over all 3,036 team-role-metric rows (every metric, not just the three) there are **0 value mismatches and
  0 rank mismatches**; the 11 "mismatches" are `pts_per_scoring_opp` rows with a null value and a null rank on both sides
  (offense: Air Force, James Madison, Utah, Vanderbilt; defense: Air Force, East Carolina, Georgia Tech, Illinois,
  Old Dominion, South Carolina, Toledo). Publisher and rebuild agree; no rank issue.
- This confirms the stored values are computed as the code says. It is not an independent hand-check of the metric
  definitions; the committed `handcheck_team_stats.py` (plain recompute from plays for 2 clean and 2 flagged teams) is still owed.

## Issue 5 (overtime drives distort `avg_start_field_pos`): REFUTED
- 76 overtime plays (quarter >= 5) exist in the 215 games; **0 pass the eligibility filter** (`scrimmage_play_mask`).
- 20 overtime drives exist in the drive table (4 games, start yards-to-goal mostly 25); **0 survive** the inner merge with
  eligible plays (`data/team_stats.py`), so none reaches any drive metric.
- Removing overtime drives before the build changes **no team, role or metric** (0 changed values, 0 rank moves, for all three
  metrics). The harmonization the plan proposed (Task 1.6) is not needed for overtime.
- Louisiana Tech defense (40.8, rank 138): the value is real in the data. 28 opponent drives in 2 games (LSU 15 drives, mean 45.1;
  Baylor 13, mean 35.8); 28.6% of its defensive drives start past the opponent's own 50 vs 10.2% league-wide (league mean 29.2,
  sd of team defense means 3.95), with many starts after turnovers and short returns. It is a two-game sample, not an artifact.
- Structure note: CFBD puts the kickoff and the receiving team's drive under one `drive_number`; the kickoff row (kicking team as
  offense, `st=1`) forms its own group with no eligible plays and is dropped, so drive starts are the first eligible scrimmage play.

## Consequence for D3
- The overtime harmonization drops out of the Silver-rebuild case. The remaining Silver-rebuild drivers are the punt-return
  special-teams tag (issue 2) and the zero-PPA `fillna` rule (issue 3, Phase D, not yet measured). D3 cannot be recommended
  until Phase D lands.
