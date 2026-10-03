# A1 findings: score-stream dips (read-only, 2026-10-03)

Inputs: certified w4 Silver set (byplay/games/game_outcomes/team_games) and the 2026 Bronze CFBD plays captures
(35 captures, latest per play; 58,379 plays, 331 games; 215 games overlap the Silver set).

## Reproduced baseline
- Silver: 133 of 430 team-games flagged (matches the documented week-5 figure), 223 drop events.

## L1 (null running score -> 0) is REFUTED as a cause of the dips
- Raw Bronze has 0 null `offenseScore` / `defenseScore` out of 58,379 plays.
- The raw feed itself contains the dips: 272 drop events in 158 team-games (45 drop-to-zero).
  Silver has 223 / 133 / 42; Silver is smaller only because its row filter removes ~3,000 non-play rows.
- Re-sorting chronologically does not remove them (wallclock order: 238 events, still 133 team-games;
  period/clock order: 257 events, 147 team-games). They are provider-side, not a sort artifact.
- `enrichment.py:269` fillna(0) on scores is currently harmless (nothing to fill), but stays a latent risk (L8).

## Silver drop taxonomy (223 events, 133 team-games)
| class | events | note |
|---|---|---|
| a. drop to exactly 0 | 42 | raw feed has the same resets |
| b. 1-2 point drop right after a scoring row | 31 | e.g. Vanderbilt 28 -> 27: TD row credits the PAT before the kick |
| c. other drop right after a scoring row | 15 | |
| d. adjacent to a Penalty row | 20 | |
| f. other (prev row not scoring, sizes 7/6/3/1) | 115 | TDs/FGs credited then reversed on later rows |
- Drop size mix: 7 (64), 3 (57), 1 (39), 6 (18), 2 (10), 8 (6).
- 219 of 223 dips are later restored to at least the pre-drop value.

## Final-score reconciliation (contradicts known_issues.md "final scores still reconcile exactly")
- For 6 of 215 games the maximum running score differs from the game final:
  Pittsburgh/UCF (UCF 13 vs 7), Michigan State/Toledo (21 vs 20), Boise State/Memphis (21 vs 20), Army/South Florida (Army 30 vs 24),
  Middle Tennessee/Nevada (30 vs 27), New Mexico State/New Mexico (12 vs 18).
- The 4 non-restored dips are in Toledo W1, Memphis W2, Army W2, New Mexico State W4.
- Implication for D1: "restored value is authoritative" is right for ~98% of dips but wrong in these 6 games, so any
  correction rule must be capped by / reconciled to the game final (the ledger's `exceeds_repaired_final` cap already does a version of this).

## Follow-up checks (same day)
- The 6 overshoot games show the identical maximum running score in raw Bronze: provider-side, not built by us.
- The 42 drop-to-zero events are transient glitches (e.g. Ohio State v Texas 401856682: 3, then 0 on the next rushes, later correct), in 32 games / 38 team-games, spread over weeks 0-4 (1/11/8/9/13). Mean value lost before the reset 6.4 points (max 21). All restore later.

## Still open for Phase A/B
- Which dip classes drive V5 quarantine vs rollback (ledger logic at possession_measurements.py:279-334).
- Kent State W4 / Air Force W2 / Army W2 specifics; per-game identity (B2).
- Committed `scripts/analysis/audit_score_stream.py` + test (not written yet).
