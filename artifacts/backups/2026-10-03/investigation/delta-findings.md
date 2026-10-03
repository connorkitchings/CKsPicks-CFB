# Rating-level delta (Tier 1) and the L5 correction (read-only, in memory, 2026-10-03)

Rule frozen in writing before the run: `d1-candidate-rule.md` (R1: monotone envelope capped at the game final; a team-game whose running
maximum is below the final stays quarantined). Inputs pinned to the served lineage (source lock
`docs/plans/2026-09-29/v5-repair-2026-source-lock.json`, signed measurement/rating manifests, certified 276-row priors, 2025 terminal table,
schedule). Priors and terminal are NOT changed. Scripts (scratch, not committed): `delta_build_candidate.py`, `delta_run_ratings.py`,
`delta_identity.py`, `delta_channels.py`. Outputs: `delta_ratings_week5.csv`, `delta_channels.csv`, `delta_identity_compare.csv`.

## Validation (the delta is only reported because these pass)
- Re-running the pinned measurement builder on the w4 Silver set reproduces the served observation frame exactly: 6,880 of 6,880 rows,
  0 mismatches on numerator, denominator and coverage status.
- Re-running `IntendedUpdate` on the served observations reproduces the served Week 5 ratings in Neon (`v5_rating_snapshots`) exactly:
  112 teams, 0 difference on offense, defense, overall and both variances.

## What R1 does to the ledger (points identity, 430 team-games)
| | baseline | R1 candidate |
|---|---|---|
| ledger total equals the final | 403 | **411** |
| quarantined (unresolved) team-games | 27 | **18** |
| observed but total != final | 3 | 1 |
| total above the final | 0 | 0 |
| improved / worsened vs baseline | | 8 / **0** |
- Gone under R1: all 138 `score_regression_rollback` events and all 29 `exceeds_repaired_final` flags.
- Remaining quarantines (18, all `impossible_score_increment`, a single-row score jump above 8): Stanford, Oregon, Louisville, Purdue,
  Wake Forest, Notre Dame, Texas Tech, Florida Atlantic (2 games), Air Force, North Dakota State, USC, Ohio State, Wisconsin, Old Dominion,
  Kent State, Utah, James Madison. They hold the largest missing totals (Wisconsin 35 points, Texas Tech 21, Stanford 14, ...).
  R1 does not address them; a second rule (provider lag: several scores appearing on one row) or the CFBD `drives` points is needed.
- New Mexico State W4 stays quarantined by rule (running maximum 12 against a final of 18).

## Rating delta at the Week 5 cutoff (138 teams; baseline overall-rating sd 0.558)
145 team-games' ppp-family rows change under R1. They split into two channels:
- **Channel A, points recovered** (11 team-games: quarantine lifted or the identity now closes; +113 offensive points in total).
- **Channel B, attribution only** (134 team-games that already reconciled to the final; R1 only changes which possessions get the points:
  mean change in offensive-possession points -1.29 per team-game, mean absolute 2.22, max 10, nonzero in 49% of them).
| channel | teams moved >0.05 (overall) | >0.10 | max | rank moves >5 | max rank move |
|---|---|---|---|---|---|
| A only | 18 | 14 | 0.367 | 15 | 36 |
| B only | 67 | 25 | 0.420 | 43 | 26 |
| A + B (R1 as specified) | 70 | 32 | 0.285 | 44 | 18 |
- The channels are not additive (largest gap 0.119 in an overall rating), because of opponent adjustment.
- Channel B cannot be validated: there is no ground truth for which drive scored which points. It is the larger source of movement, so
  R1 as specified is NOT a safe D4 input. Channel A is the defensible evidence.
- Largest movers (A + B), overall rating: Tennessee -0.285 (rank 16 to 34), Pittsburgh +0.281 (24 to 15), Notre Dame -0.250,
  UCF -0.217 (19 to 37), Middle Tennessee +0.177, Utah -0.169, Miami +0.168 (full table in `delta_ratings_week5.csv`).

## Week 5 margin and total movement (approximation, not the real bridge)
Method: ordinary least squares of the served Week 5 predictions on the four current ratings (home/away offense and defense). The margin fit is
excellent (R2 = 0.997); the total fit is poor (R2 = 0.824), so total movement is **inconclusive** and is not reported as evidence.
| channel | mean abs margin shift | max | games moving more than 1 point | spread side flips (vs stored lines) |
|---|---|---|---|---|
| A only | 1.13 | 7.90 | 16 of 56 | 4 |
| A + B | 1.78 | 6.85 | 35 of 56 | 3 |
Hypothetical only: no frozen prediction, selection or grade was changed.

## Conclusions for D4 (proposed, not decided) [REVISED the same day: see "Validation against CFBD drives" below; points 1 and 2 are weakened]
1. Even the defensible channel alone is material at the rating level: 18 teams move more than 0.05, 15 teams more than 5 ranks, and about
   16 of 56 Week 5 margins move by more than a point. The D4 flip criterion is met at the rating level, not just on raw ppp.
2. Do not adopt R1 as written. The rebuild contract should (a) recover only attribution that fails the points identity (channel A),
   or (b) validate the attribution against CFBD `drives` points (D1 option 3), which gives ground truth for channel B, and (c) deal with the 18
   jump-above-8 quarantines.
3. Tier 2 (not executed): re-deriving the 2025 terminal table and the priors. Costing/framing for the contract: needs R1-or-successor applied to the
   ~1,868 2025 team-games (and the earlier seasons in the terminal table), a rebuild of the terminal ratings and the 276-row priors (carryover rho 0.60), a
   new signed manifest chain and a delta against the served lineage; it touches every 2026 team with a quarantined 2025 game (92 teams, 11 with three or more).
   Not separable from this delta cheaply; the two channels (2026 restoration, poisoned-prior effect) are therefore reported as: 2026 restoration measured here,
   poisoned-prior effect unmeasured.

## L5 correction (away best-quote sort)
- Earlier statement ("selected point equals the consensus on every row, so L5 never changed a pick") was wrong; it compared two copies of the selected quote.
- Verified: of 70 games (weeks 0-5) whose quotes disagree, the stored line is the highest home line in all 70: the best line for 37 home picks, the worst for
  all 33 away picks (0.82 points given up on average). Side flips under the median line: 0. Weeks 0-4 spread record under the best line for each side:
  100-111-4 (one loss becomes a push) vs stored 100-112-3.

## Validation against CFBD drives (same day; supersedes the strength of conclusions 1 and 2)
Full detail in `d1-candidate-rule.md` ("Shadow check against CFBD drives"). Summary:
- CFBD drives is clean in only 9 of the 30 affected team-games and is not an unconditional oracle (47 of 430 team-games non-monotone; 36 over the final).
- Channel B (R1's attribution changes) is not supported: on CFBD-clean team-games CFBD agrees with the baseline on 36 of 66 differing drives and with R1 on 28.
- Only 3 of channel A's 11 recoveries are corroborated by CFBD (Vanderbilt W3, Northern Illinois W3, Miami (OH) W4); their rating effect is small
  (1 team above 0.05, max 0.111; 2 teams above 5 ranks, max 13). The movement in channel A comes mostly from the 8 recoveries that R1 forces to the game final
  (a cap, so "total equals the final" is true by construction, not independent evidence).
- Revised reading for D4: the rating-level flip is NOT met on independently corroborated evidence; it is met only if the unclean-drives recoveries are accepted.
  A rebuild "now" is not supported by this evidence alone.

## Addendum: Silver quarter line scores (same day; changes the reading above again)
Quarter line scores are a clean validator (430 of 430 sum to the final). R1 matches them in all quarters for 8 of 30 affected team-games; 8 of the 11 channel-A
recoveries are corroborated, and they carry almost all of the effect (18 teams above 0.05, max 0.352; 13 teams above 5 ranks, max 36). So the flip criterion is met on
independently corroborated evidence, and the "not met on corroborated evidence" reading in the section above was caused by the dirty drives validator. Channel B is still unsupported.
See `quarter-scores-findings.md`.
