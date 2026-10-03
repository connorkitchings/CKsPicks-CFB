# Candidate D1 rule, frozen before the rating-level delta runs (2026-10-03)

Status: candidate for the Tier 1 delta only. It is not a decision and changes nothing in production. Evidence behind it:
`a1-findings.md` (dips are in the raw CFBD feed; 219 of 223 later restore; 6 of 215 games overshoot the final) and
`b-findings.md` (27 quarantined team-games, 3 silently lossy).

## Rule R1: "monotone envelope, capped at the game final, unresolved if the envelope does not reach the final"
Inputs per completed game and team: the team's running score s_t on every play row in ledger order
(`season, game_id, quarter, drive_number, play_number`), taken from `offense_score` when the team is the offense and from
`defense_score` when it is the defense; and its final score F from the game outcomes.
1. Envelope: e_t = min(F, max over u <= t of s_u). A decrease in s is therefore ignored (treated as provisional); the value
   is never allowed to exceed the final.
2. Replace `offense_score` and `defense_score` on each row with the envelope value for that row's offense and defense team.
3. Resolution test: the team-game is resolved only if the last envelope value equals F. If it falls short of F (for example
   New Mexico State W4: running maximum 12 against a final of 18) the team-game stays quarantined exactly as today.
4. Everything else in `build_possession_ledger` is unchanged: the 8-point increment limit, conversion handling, category rules,
   the `exceeds_repaired_final` cap, and the exclusion of overtime and garbage-time possessions.

## What it deliberately does not do
- It does not look at the cause of a dip (PAT credited early, reversed touchdown, provider glitch), so it cannot say which play
  a clipped overshoot point belonged to (Army 30 vs 24: the extra 6 are removed from the last events that reach 24).
- It does not change `ppp` or `epa_per_possession` definitions, the possession filter, or the zero-PPA fill (issue 3).
- It uses the game final, so it applies only to completed games before the cutoff (as the weekly cycle already requires).

## Delta specification (Tier 1)
- Inputs pinned to the served lineage: locked source lock `docs/plans/2026-09-29/v5-repair-2026-source-lock.json`, the signed
  measurement and rating manifests it references, the certified 276-row priors, the 2025 terminal table, the schedule.
  Priors and terminal are NOT changed (Tier 2, re-deriving the 2025 terminal and priors, is only scoped for the D4 contract).
- Everything runs in memory. Baseline = served observations. Candidate = served observations with the ppp-family rows of the
  affected team-games replaced by the R1 ledger result.
- Validation before the delta counts: the baseline run must reproduce the served ratings (Neon `v5_rating_snapshots`) within
  tolerance; otherwise the delta is not reported.
- Report: per-team offense, defense and overall rating change at the Week 5 cutoff, rank shifts, then margin and total movement
  for the 56 Week 5 games through the unchanged bridge if it can be applied in memory.
- Tier 2 is costed and framed only.

## Shadow check against CFBD `drives` (2026-10-03, read-only; no new scope)
Authorized as the single comparison that tests option (c) of D1. Data: CFBD `/drives` for 2026 weeks 0-4 (5 calls; 4,961 de-duplicated drives
in our 215 games, no null scores). Scratch scripts: `drives_oracle.py`, `drives_vs_ledger.py`, `delta_validated.py`; outputs `drives_oracle_teamgames.csv`,
`drives_vs_ledger_perdrive.csv`, `drives_vs_ledger_affected.csv`.
- **Is CFBD drives clean?** Not unconditionally. Drive scores are monotone in 383 of 430 team-games (47 are not), and in 36 team-games the sum of drive
  points exceeds the final (e.g. Purdue 78 vs 36, USC 51 vs 39, Miami 55 vs 45).
- **Where the play stream is bad, drives is bad too:** CFBD-clean in only **9 of the 30** affected team-games (27 quarantined + 3 silently short).
  It is not an independent oracle for the games that need one.
- **Per-drive agreement on CFBD-clean team-games (4,429 drives):** the baseline ledger equals CFBD on 98.1%, rule R1 on 97.9%. Where baseline and R1 differ on
  a CFBD-clean team-game (66 drives, channel B), CFBD agrees with the baseline on 36, with R1 on 28 and with neither on 2. R1's attribution changes are
  not supported by CFBD; if anything the baseline is closer.
- **The 3 "silently short" team-games** (Vanderbilt W3, Northern Illinois W3, New Mexico State W4) are CFBD-clean and the missing 7, 7 and 6 points are
  non-drive scores (defensive or special-teams touchdowns): CFBD drive points are 28, 10 and 12 against finals of 35, 17 and 18.
- **Circularity note:** R1 caps at the game final, so "ledger total equals the final" holds by construction for capped team-games; it is not independent
  validation of a recovery. The only independent corroboration available here is CFBD drives.
- **Rating effect of the corroborated recoveries only** (channel A intersected with CFBD-clean: Vanderbilt W3, Northern Illinois W3, Miami (OH) W4):
  1 team moves more than 0.05 overall (max 0.111), 2 teams move more than 5 ranks (max 13). The other 8 channel-A recoveries (UCF, Miami, Stanford, USC,
  Nebraska, Memphis, Army, Middle Tennessee), where CFBD drives is itself unclean, account for the larger movement (17 teams above 0.05, max 0.357, 13 teams above
  5 ranks, max 36).
- **Consequence:** option (c) fails as a general oracle; R1's channel B is unsupported; the evidence that supports a rebuild "now" rests on recoveries that no
  second source corroborates. A quarter-level check against the Silver `home_line_scores`/`away_line_scores` columns is a candidate second validator (not run).

## Shadow check 2: Silver quarter line scores (2026-10-03, read-only, one pass; supersedes the "Consequence" above)
Details in `quarter-scores-findings.md`. The quarter scores are a clean validator (sum equals the final in 430 of 430 team-games). R1 matches them in every quarter
for 8 of the 30 affected team-games (baseline 2); 8 of the 11 channel-A recoveries are quarter-corroborated, and 10 of 11 have at least one independent corroboration.
Rating effect of the quarter-corroborated recoveries: 18 teams above 0.05 overall (max 0.352), 13 teams above 5 ranks (max 36). The CFBD-drives conclusion that only 3
recoveries are corroborated was an artifact of drives being unclean exactly there. Channel B remains unvalidated (CFBD favours the baseline there). Candidate narrowed rule
V1: apply R1 only to a team-game whose rebuilt ledger reproduces the quarter line scores exactly; every other team-game keeps today's behaviour.
