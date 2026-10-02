# Known Data Issues

Open and resolved data-quality issues that affect what the product shows. Add an entry when an issue is found; move it to **Resolved** with the fixing commit.

## Open

### 1. Play-by-play running score is not monotonic (opened 2026-10-02)

- **What:** each Silver `byplay` row carries a running score for both teams (`offense_score`, `defense_score`). For many team-games the score goes down from one row to the next, which cannot happen in football. Example (Vanderbilt, 2026): 28 to 27 after a blocked-punt touchdown row (Delaware, game 401856684), 35 to 28 after a fumble-return touchdown row (NC State, 401856695), and 15 to 12 on a penalty row with no scoring play nearby (Auburn, 401856698). Final scores still reconcile exactly.
- **How often:** about a third of team-games are flagged every week (`ppso_invalid_offenses` in the `publish_team_stats.py` report): week 1 7 of 16, week 2 36 of 102, week 3 72 of 200, week 4 98 of 314, week 5 133 of 430. The steady 31-36% rate suggests a systematic pattern in the feed, not random bad games.
- **Effect:** `true_drive_points` (`ratings/observations.py`) quarantines an offense in any game whose score stream decreases, so that game is dropped from `pts_per_scoring_opp`. Teams keep a value from their remaining games (thinner sample); a team with every game flagged shows "—" with no rank (Vanderbilt through week 4; about 4 offenses and 7 defenses at week 5). No other team-stats metric uses the score.
- **Not yet known:** whether the dips are in CFBD's feed or introduced by our Silver build (only the stored Silver copy was read); what causes them (a first guess: the touchdown row credits the extra point before the kick, and a reversed or mislogged touchdown is taken back on the next row; the Auburn dip is unexplained); whether V5 `ppp` / `non_offense_points` are affected (V5 uses its own score attribution and still shows a value for Vanderbilt).
- **Suggested next steps:** (1) compare the raw CFBD plays with Silver for the three Vanderbilt games and classify the dips; (2) have the publish step list flagged games per week and warn when the rate jumps; (3) check V5 `ppp` for the same games; (4) only then consider treating corrected dips as valid, which changes the metric definition and needs a contract.
- **Mitigation today:** the share card footnotes "—" as "not enough clean data". The matchup page shows the same "—" without a note.

### 2. V5 per-play companions still count returned punts

`team_possession_stats.epa_per_play` and `plays_per_possession` (stored, not shown) include CFBD `Punt Return` rows until the planned Silver and V5 rebuild. `ppp` and `epa_per_possession`, the only measures the ratings fit, are unaffected. See [team stats feeds ratings](../plans/2026-10-02/03-team-stats-feeds-ratings.md).

### 3. Zero-PPA plays that may be missing values

155 eligible non-punt plays in 2026 Silver have `ppa == 0` exactly, probably CFBD nulls turned into zeros by Silver's `fillna(0)` (`features/byplay/enrichment.py`). They sit inside every per-play PPA mean, including `ppa_per_play`. Decide at the Silver rebuild whether to treat them as nulls.

## Resolved

- **Returned punts counted as plays in team stats (2026-10-02):** CFBD `Punt Return` rows carried `st == 0` and passed the V5 filter. Fixed in `5acd051` (team stats excludes them; enrichment tags them as special teams for future builds). Production data republish pending (user-run).
