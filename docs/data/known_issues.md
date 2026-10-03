# Known Data Issues

Open and resolved data-quality issues that affect what the product shows. Add an entry when an issue is found; move it to **Resolved** with the fixing commit.

## Review and rerun together (decision 2026-10-02; unified 2026-10-03)

**Full workflow (phases, commands, decisions, stop conditions, definition of done): [unified data fix and matchup rollout](../plans/2026-10-03/01-unified-data-fix-and-matchup-rollout.md)** — it supersedes the earlier [review-and-rerun draft](../plans/2026-10-02/05-data-issues-review-and-rerun.md) and additionally gates the plan 03 Phase 2 rebuild (D4) and the 2025 matchup backfill (D5) so production data is written once. The summary below is the short form.

The open issues below touch the same aggregations, so they are reviewed first and the affected data is rerun **once**, not piecemeal. The **production republish of team stats is part of that batch and is on hold** until the review is done.

**Why batch:** production `team_season_stats` still holds the pre-fix conversion, explosive and turnover rates and has no `ppa_per_play`; Preview already has the punt fix. Republishing production now and again after the review would mean two production writes of the same tables, and the review may change the same metrics (for example `pts_per_scoring_opp` if the score-stream rule changes). The matchup page is closed in production (`CFB_MATCHUP_ENABLED` unset), so nothing user-visible waits on it. **Do not set `CFB_MATCHUP_ENABLED=1` in production until the batch below is done and production is republished.**

**Review (read-only), in order:**
1. Issue 1: compare raw CFBD plays with Silver for the three Vanderbilt games; classify the score dips; measure how many flagged team-games each cause explains.
2. Issue 1: check whether V5 `ppp` and `non_offense_points` are affected for the same games (Vanderbilt shows a value).
3. Hand-check the drive metrics not yet verified against the plays: `scoring_opp_rate`, `pts_per_scoring_opp`, `avg_start_field_pos` (two or three teams, including one with flagged games).
4. Issues 2 and 3: decide the `fillna(0)` PPA rule and whether the Silver rebuild happens in this batch.

**Decide (D1–D6 in the unified plan):** whether the score-stream rule changes (needs a contract), the zero-PPA rule, whether the Silver and V5 rebuild ([team stats feeds ratings, Phase 2](../plans/2026-10-02/03-team-stats-feeds-ratings.md)) runs now or later, whether the 2025 matchup backfill joins the batch, and when the matchup flag opens.

**Rerun together (after the decisions):**
1. Silver rebuild, only if decided (carries the enrichment fix and any `fillna` change).
2. Team stats weeks 1-5 on Preview (`publish_team_stats.py --diff`, review), then production (user-run: dry run with `--diff`, write, `verify_team_stats.py`). Week 6 stats follow the same path after Week 5 finals.
3. V5 measurements and ratings with a delta report, only if the Silver rebuild or a score rule changes them.
4. Matchup data (`publish_matchup_data.py`) re-pinned if the rating lineage changes.
5. Then open the matchup page in production.

**Done when:** `known_issues.md` shows every item below resolved or explicitly accepted, production and Preview team stats are identical in method, and the hand-checks pass.

## Open

### 1. Play-by-play running score is not monotonic (opened 2026-10-02)

- **What:** each Silver `byplay` row carries a running score for both teams (`offense_score`, `defense_score`). For many team-games the score goes down from one row to the next, which cannot happen in football. Example (Vanderbilt, 2026): 28 to 27 after a blocked-punt touchdown row (Delaware, game 401856684), 35 to 28 after a fumble-return touchdown row (NC State, 401856695), and 15 to 12 on a penalty row with no scoring play nearby (Auburn, 401856698). Final scores still reconcile exactly.
- **How often:** about a third of team-games are flagged every week (`ppso_invalid_offenses` in the `publish_team_stats.py` report): week 1 7 of 16, week 2 36 of 102, week 3 72 of 200, week 4 98 of 314, week 5 133 of 430. The steady 31-36% rate suggests a systematic pattern in the feed, not random bad games.
- **Effect:** `true_drive_points` (`ratings/observations.py`) quarantines an offense in any game whose score stream decreases, so that game is dropped from `pts_per_scoring_opp`. Teams keep a value from their remaining games (thinner sample); a team with every game flagged shows "—" with no rank (Vanderbilt through week 4; about 4 offenses and 7 defenses at week 5). No other team-stats metric uses the score.
- **Not yet known:** whether the dips are in CFBD's feed or introduced by our Silver build (only the stored Silver copy was read); what causes them (a first guess: the touchdown row credits the extra point before the kick, and a reversed or mislogged touchdown is taken back on the next row; the Auburn dip is unexplained); whether V5 `ppp` / `non_offense_points` are affected (V5 uses its own score attribution and still shows a value for Vanderbilt).
- **Suggested next steps:** (1) compare the raw CFBD plays with Silver for the three Vanderbilt games and classify the dips; (2) have the publish step list flagged games per week and warn when the rate jumps; (3) check V5 `ppp` for the same games; (4) only then consider treating corrected dips as valid, which changes the metric definition and needs a contract.
- **Part of the batch above:** steps 1, 2, 3 and the score-rule decision.
- **Week 5 audit update (2026-10-03):** the quarantine also empties V5 `ppp`, not just `pts_per_scoring_opp`: 129 `missing/unresolved_scoring_attribution` team-measurements for Week 5 teams, including Kent State W4 (7 offensive points quarantined → season offense `ppp` 0.00 despite 29 points scored), Air Force W2 (14) and Army W2 (24), leaving both one-game `ppp` samples. Kent State W3's 3 points appear in neither `offensive_possession_points` nor `non_offense_points` (garbage-time classification suspected; identity check pending). Investigation: [Week 5 data-issue investigation, Phases A–B](../plans/2026-10-03/02-week5-data-issue-investigation.md).
- **Mitigation today:** the share card footnotes "—" as "not enough clean data". The matchup page shows the same "—" without a note.

### 2. V5 per-play companions still count returned punts

`team_possession_stats.epa_per_play` and `plays_per_possession` (stored, not shown) include CFBD `Punt Return` rows until the planned Silver and V5 rebuild. `ppp` and `epa_per_possession`, the only measures the ratings fit, are unaffected. See [team stats feeds ratings](../plans/2026-10-02/03-team-stats-feeds-ratings.md). Part of the batch above (Silver and V5 rebuild decision).

### 3. Zero-PPA plays that may be missing values

155 eligible non-punt plays in 2026 Silver have `ppa == 0` exactly, probably CFBD nulls turned into zeros by Silver's `fillna(0)` (`features/byplay/enrichment.py`). They sit inside every per-play PPA mean, including `ppa_per_play`. Decide at the Silver rebuild whether to treat them as nulls (batch step 4).

### 4. Two Week 5 games have NULL venue city/state (opened 2026-10-03)

`game_venues` rows exist for 401858476 (Northwestern @ Penn State) and 401864515 (North Dakota State @ Wyoming) but `city` and `state` are NULL, so those cards render no location. Unknown whether CFBD returned nulls or the publisher dropped them; a full-2026 NULL scan is pending. Investigation and backfill path: [Week 5 data-issue investigation, Phase E](../plans/2026-10-03/02-week5-data-issue-investigation.md); the backfill rides the unified production batch.

### 5. Drive metrics keep overtime drives the V5 filter drops (opened 2026-10-03)

`avg_start_field_pos` (Silver, drive-based) counts overtime drives starting at the opponent's 25, so ranks are not comparable between teams with and without overtime games — e.g. Louisiana Tech defense 40.8, rank 138/138 at Week 5. The V5 play filter already excludes them. Harmonization rides the D3 Silver-rebuild decision: [Week 5 data-issue investigation, Phase C](../plans/2026-10-03/02-week5-data-issue-investigation.md).

## Resolved

- **Returned punts counted as plays in team stats (2026-10-02):** CFBD `Punt Return` rows carried `st == 0` and passed the V5 filter. Fixed in `5acd051` (team stats excludes them; enrichment tags them as special teams for future builds). Production data republish is on hold and bundled with the review above.
