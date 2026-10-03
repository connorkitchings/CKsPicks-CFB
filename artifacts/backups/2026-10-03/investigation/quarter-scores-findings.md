# Quarter line-score check (read-only, one pass, 2026-10-03)

Bounded as authorized: the 30 affected team-games only (27 quarantined + 3 silently short), recorded results, no rule edits. Expectation set first:
quarter granularity can corroborate per-quarter totals (recovery) but cannot settle which drive scored (attribution, channel B). Scratch:
`quarter_scores_check.py`, `delta_validated.py`; output `quarter_scores_affected.csv`.

## The validator is clean
- Silver `games` has `home_line_scores` / `away_line_scores` for all 215 completed 2026 games; the quarters sum to the final in **430 of 430** team-games.
  (The column is null on most non-2026 Silver rows; it is complete for the games used here.)

## Result on the affected set
- Rule R1's rebuilt ledger matches the line score in **every quarter** for 8 of the 30 team-games; the baseline ledger does for 2 (Memphis W2, Middle Tennessee W3).
  By quarter: 66 of 122 quarters match under R1 vs 55 under the baseline.
- Corroborated recoveries (channel A members that match all quarters): Vanderbilt W3, UCF W2, Stanford W1 (vs Miami), USC W1 (vs Fresno State), Nebraska W4,
  Memphis W2, Army W2, Middle Tennessee W3 = **8 of the 11**. Not corroborated by quarters: Miami W1 (R1 [15,13,14,3] vs [14,14,14,3]), Northern Illinois W3
  (R1 [16,0,0,1] vs [10,0,0,7]) and Miami (OH) W4 (R1 [2,12,7,3] vs [0,14,7,3]): R1 shifts points between quarters there. The other 19 affected
  team-games (the 18 single-row-jump quarantines and New Mexico State) fail the quarter test and stay unrecovered.
- Nature of the 8: UCF W2 (ledger 0, final 7), Stanford W1, USC W1 (39), Nebraska W4 are genuine recoveries of missing offensive points; Memphis W2 and
  Middle Tennessee W3 are baseline-correct ledgers quarantined only by the final-score cap (the quarter scores say the baseline was right);
  Army W2 had the right total but two touchdowns in the wrong quarters (R1 fixes the timing); Vanderbilt W3's recovered 7 is a non-offense touchdown (see below).
- Overlap with the CFBD-drives check: Vanderbilt is corroborated by both; drives corroborates Northern Illinois and Miami (OH) (quarters do not); quarters
  corroborate seven that drives could not (drives is itself unclean there). Ten of the 11 have at least one independent corroboration; only Miami W1 has none.

## Rating-level effect of the corroborated subsets (Tier 1, in memory, priors and terminal fixed)
| subset of channel A | teams moving >0.05 overall | >0.10 | max | rank moves >5 | max rank move |
|---|---|---|---|---|---|
| CFBD-corroborated only (3) | 1 | 1 | 0.111 | 2 | 13 |
| quarter-corroborated only (8) | **18** | 12 | 0.352 | 13 | 36 |
| either validator (10) | 18 | 13 | 0.362 | 12 | 36 |
| neither (1: Miami W1) | 3 | 1 | 0.244 | 1 | 6 |
So the earlier "only 3 recoveries are corroborated, small effect" (drives-based) was too pessimistic: the drive feed was dirty exactly where the recoveries are.
With the clean quarter validator, nearly the whole channel-A effect is corroborated.

## What this does not show
- It does not validate channel B (R1's attribution changes in the other 134 team-games): not checked (outside the authorized set), and quarter totals cannot resolve
  attribution. CFBD drives remains the only evidence on channel B and it favours the baseline (36 vs 28 of 66 differing drives).
- Quarter totals are insensitive to which drive scored within a quarter, and Memphis/Middle Tennessee/Vanderbilt are not "points recovered into ppp" in the same sense (see above).
- Stopped after one pass, as agreed.

## Where the non-offense gaps land (Vanderbilt W3, Northern Illinois W3, New Mexico State W4: missing 7, 7, 6)
CFBD drives shows these are defensive or special-teams scores (non-drive points). `non_offense_points` is NOT used by the ratings (the rating engine fits `ppp`
only). It is consumed by (1) the forecast offsets: `forecast/offsets.py` builds earlier-only per-team regulation non-offense translation offsets from the ledger's
`regulation_non_offense` events, so a lost event lowers that team's offset; and (2) the matchup page (`data/matchup_data.py`, `non_offense_points_per_game`).
The size of the effect on the Week 5 forecasts was not measured (6-7 points in one game of about four for three teams).
