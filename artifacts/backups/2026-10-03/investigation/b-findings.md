# B findings: V5 impact and the D4 flip (read-only, 2026-10-03)

Source: Preview `team_game_measurements`, `team_possession_stats` (as_of_week 5), `games`/`game_results`. Weeks 0-4, 430 team-games.
Working files: `v5_measurements_ppp_family.csv`, `b2_quarantined_identity.csv`, `b3_s2_simulation.csv`.

## B1 inventory (corrects the 2026-10-03 audit figure)
- **27 of 430 team-games (6.3%)** have `ppp` / `offensive_possession_points` / `non_offense_points` marked
  `missing / unresolved_scoring_attribution` and `rating_usable = False`. They sit in 24 games and touch 24 teams
  (by week: 0:1, 1:5, 2:11, 3:5, 4:5). The earlier "129 measurements" counted measurement rows, not team-games.
- Silver's `pts_per_scoring_opp` flags 133 team-games (31%); the V5 ledger's rollback logic absorbs most dips and quarantines
  only these 27.
- Served `ppp` reconstructs exactly from the measurements (276/276 team-role rows, 0 difference): value = sum(numerator)/sum(denominator)
  over observed games; ranks reproduce too.

## B2 identity (final points vs what V5 attributed)
- Quarantined offense team-games: final points 899; stored `offensive_possession_points` numerators 234; stored non-offense points small.
  Final minus non-offense points (an upper bound; includes any garbage-time points) = 867.
- 10 of 27 have a stored numerator of exactly 0 although the team scored 319 points in total (e.g. USC 39 vs Fresno State,
  Ohio State 59 vs Kent State, Miami 45 vs Stanford, Notre Dame, James Madison 46). Stored numerators are unusable;
  lifting the quarantine "as is" would be wrong, a correction needs real attribution.
- Kent State W3 (59-3 loss, the 3 points): RESOLVED. It is not among the 27 (the Kent State quarantine is W4: stored 7, final 26).
  The 3 points are a field goal on a possession with no eligible plays, so they sit in `excluded_regulation_offense`,
  not in the offensive or non-offense numerators. By design, not a loss.

## B2 full identity (local rebuild of the scoring ledger from the w4 Silver set; no writes)
Method: `build_possession_ledger(byplay, population, scope="season_2026")` with canonical team names and the final-score
cap enabled; sum `score_increment` by team-game across all buckets and compare with the final score.
Files: `ledger_scoring_events_w4set.csv`, `b2_points_identity_all.csv`.
- The rebuild reproduces the served quarantine exactly: 27 of 27 team-games match, none extra, none missing.
- **403 of 430 team-games reconcile exactly** (ledger total = final score); 27 do not. Cross-tab:

  | | reconciles | does not |
  |---|---|---|
  | quarantined (27) | 3 | 24 |
  | observed (403) | 400 | 3 |

  The 27 non-reconciling are 24 quarantined plus 3 observed. It is a coincidence that this equals the 27 quarantined.
  The 3 quarantined games that reconcile are Army W2, Memphis W2 and Middle Tennessee W3: their ledger totals equal the
  final (24, 20, 27) and they are quarantined only by the final-score cap, because their running score overshoots the final.
- **3 team-games lose points silently while staying `observed`** (they feed `ppp` with understated numerators and fail the
  identity): Vanderbilt W3 vs NC State (ledger 28 vs final 35: the fumble-return touchdown row), Northern Illinois W3 (10 vs 17),
  New Mexico State W4 (6 vs 18). Total 26 points missing. The ledger's score-regression rollback removed events and the
  ledger total never reaches the final, so the points are not credited elsewhere.
- Bucket totals over all 430 team-games: eligible offense 9,491; non-offense 613; excluded-possession 474 (4.2% of all points);
  overtime 36; final points 11,273. The 474 excluded points are in neither `ppp` numerator by design.
- Correction of an earlier in-session reading: a first pass joined on raw Silver team names and showed "31 silent losses
  (644 points)". That was a name-canonicalization artifact (UTSA, Hawai'i, Southern Miss, UL Monroe, San Jose State),
  not a pipeline defect. Nothing from it was written to the docs.

## B3 simulation (raw aggregated `ppp`, not the opponent-adjusted/shrunk ratings)
Flip criterion: any team |ppp| move > 0.05 or rank move > 5.
| scenario | role | teams |dppp|>0.05 | teams |drank|>5 | max |dppp| | max |drank| |
|---|---|---|---|---|---|
| S1 stored numerators | offense | 24 | 56 | 1.37 | 70 |
| S1 stored numerators | defense | 25 | 40 | 1.61 | 56 |
| S2 final minus non-offense (upper bound) | offense | 23 | 14 | 1.32 | 68 |
| S2 final minus non-offense (upper bound) | defense | 24 | 22 | 1.64 | 44 |
- **The flip criterion is met at the raw level in both scenarios** => D4 defaults to NOW as a *proposal*, pending the rating-level delta report (the rating shift after opponent adjustment and prior shrinkage is smaller and unmeasured). D4 is not decided and the unified plan's working assumption is unchanged until it is recorded.
- Largest offense moves under S2: Wisconsin 1.68 -> 3.00 (rank 92 -> 24), Purdue 2.00 -> 2.74 (77 -> 38), Wake Forest 2.67 -> 3.15 (40 -> 15),
  James Madison (81 -> 57), North Dakota State (64 -> 41), Kent State 0.00 -> 1.18 (138 -> 121), Air Force (38 -> 28);
  downward: Florida Atlantic (18 -> 39), Utah (3 -> 10).
- **Selection bias:** the quarantined games average about 3.1 ppp (S2 upper bound) vs 2.15 league-wide, so excluding them biases
  affected offenses down and their opponents' defenses up.
- Caveat: these are the published raw `ppp` figures (what the matchup page and cards show). The ratings use opponent-adjusted,
  prior-shrunk values, so the rating impact is smaller; it has to be measured with the real rating code in a delta report.

## Consequences
- Stop condition in the unified plan is triggered: a fix moves `ppp` (the measure the ratings fit), so the work needs its own
  contract and a V5 delta report before any rebuild. Nothing here changes the served ratings or any frozen prediction.
- Open: A3 D1 rule choice, B2 identity for all 430 team-games from the observations dataset, rating-level delta.
